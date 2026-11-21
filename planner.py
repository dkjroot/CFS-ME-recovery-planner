"""Local guided recovery state, adaptive step-back logic, and trajectory projection."""

from datetime import date, timedelta
import json
from pathlib import Path
from threading import Lock
from uuid import uuid4

from guidance import (
    ACTIVITY_RATINGS,
    ASSESSMENT_QUESTIONS,
    BEYOND_PLAN_PRESETS,
    EFFORT_LEVELS,
    FACTORS,
    FEELINGS,
    LEVELS,
    PHASES,
    STABILIZATION_ACTIVITIES,
    evaluate_assessment,
    level_activities,
)

DATA_FILE = Path(__file__).resolve().parent / 'local_data' / 'planner.json'
SCHEMA_VERSION = 2
OPTIONAL_CATEGORIES = {'Movement', 'Cognitive', 'Social'}
LOW_FEELINGS = {'worse', 'crash'}
STEADY_FEELINGS = {'steady', 'worn'}
PEM_LOOKBACK_DAYS = 3
STABILIZE_STEADY_TARGET = 2
MAX_BEYOND_PLAN = 5


def clean_string(value, limit):
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError(f'Enter text of up to {limit} characters.')
    return value.strip()


def optional_minutes(value):
    if value is None:
        return None
    if type(value) is not int or not 0 <= value <= 1440:
        raise ValueError('Enter a whole number of minutes from 0 to 1440.')
    return value


def parse_level(value):
    if type(value) is not int or not 1 <= value <= 12:
        raise ValueError('Choose a recovery level from 1 to 12.')
    return value


def parse_hold_scale(value):
    if type(value) not in (int, float) or not 0.5 <= float(value) <= 2.0:
        raise ValueError('Choose a pace multiplier between 0.5 and 2.0.')
    return round(float(value), 2)


def scaled_hold_days(level, hold_scale):
    base = LEVELS[level]['hold_days']
    return max(7, round(base * hold_scale))


def blank_state():
    return {
        'version': SCHEMA_VERSION,
        'profile': None,
        'program': None,
        'history': [],
        'setbacks': [],
        'checkins': {},
    }


def normalize_state(raw):
    if not isinstance(raw, dict) or raw.get('version') != SCHEMA_VERSION:
        return blank_state()
    state = blank_state()
    state.update({
        'profile': raw.get('profile'),
        'program': raw.get('program'),
        'history': raw.get('history') or [],
        'setbacks': raw.get('setbacks') or [],
        'checkins': raw.get('checkins') or {},
    })
    return state


def inspect_prior_days(checkins, day, lookback=PEM_LOOKBACK_DAYS):
    """Look back 1..lookback days before `day` for unplanned stressors or overexertion."""
    beyond = []
    too_much = []
    factors = []
    for offset in range(1, lookback + 1):
        prior_key = (day - timedelta(days=offset)).isoformat()
        entry = checkins.get(prior_key)
        if not entry:
            continue
        for item in entry.get('beyond_plan', ()):
            beyond.append({
                'date': prior_key,
                'days_before': offset,
                'label': item['label'],
                'effort': item['effort'],
            })
        for act_id, rating in entry.get('activities', {}).items():
            if rating == 'too_much':
                too_much.append({'date': prior_key, 'days_before': offset, 'id': act_id})
        for factor in entry.get('factors', ()):
            if factor not in factors:
                factors.append(factor)

    today_entry = checkins.get(day.isoformat(), {})
    for factor in today_entry.get('factors', ()):
        if factor not in factors:
            factors.append(factor)

    external = bool(beyond) or any(f in ('illness', 'stress') for f in factors)
    return {
        'beyond_plan': beyond,
        'too_much': too_much,
        'factors': factors,
        'external_trigger': external,
    }


def compute_benchmarks(checkins, today):
    """Evaluate 3-day outcomes for all logged beyond-plan activities."""
    items = []
    for day_key in sorted(checkins.keys(), reverse=True):
        entry = checkins[day_key]
        beyond_list = entry.get('beyond_plan') or []
        if not beyond_list:
            continue
        day = date.fromisoformat(day_key)
        low_hit = None
        if entry.get('feeling') in LOW_FEELINGS:
            low_hit = (0, entry['feeling'])
        else:
            for offset in range(1, PEM_LOOKBACK_DAYS + 1):
                later = day + timedelta(days=offset)
                if later > today:
                    break
                later_entry = checkins.get(later.isoformat())
                if later_entry and later_entry.get('feeling') in LOW_FEELINGS:
                    low_hit = (offset, later_entry['feeling'])
                    break

        window_end = day + timedelta(days=PEM_LOOKBACK_DAYS)
        logged_follow_ups = sum(
            1 for offset in range(1, PEM_LOOKBACK_DAYS + 1)
            if (day + timedelta(days=offset)).isoformat() in checkins
        )

        if low_hit is not None:
            days_later, low_feeling = low_hit
            outcome = 'not_ready'
            if days_later == 0:
                outcome_text = f"{FEELINGS[low_feeling]} the same day — above current capacity"
            else:
                unit = 'day' if days_later == 1 else 'days'
                outcome_text = f"{FEELINGS[low_feeling]} {days_later} {unit} later — not ready for this yet"
        elif today < window_end:
            outcome = 'watching'
            outcome_text = f'Watching 3-day response (until {window_end.isoformat()})'
        elif logged_follow_ups >= 2:
            outcome = 'tolerated'
            outcome_text = 'Handled well across the next 3 days'
        else:
            outcome = 'incomplete'
            outcome_text = 'Following days unlogged'

        for bp in beyond_list:
            items.append({
                'id': bp['id'],
                'date': day_key,
                'label': bp['label'],
                'effort': bp['effort'],
                'minutes': bp.get('minutes'),
                'outcome': outcome,
                'outcome_text': outcome_text,
            })
    return items


def stabilizing_streak(checkins, stabilizing_since, today):
    """Count consecutive steady check-ins strictly after `stabilizing_since`."""
    if not stabilizing_since:
        return 0
    since_day = date.fromisoformat(stabilizing_since)
    count = 0
    cursor = today
    # Walk backward from today through consecutive logged days after stabilizing_since,
    # allowing today to be unlogged yet if yesterday was steady.
    if cursor.isoformat() not in checkins:
        cursor -= timedelta(days=1)
    while cursor > since_day:
        entry = checkins.get(cursor.isoformat())
        if not entry:
            break
        if entry['feeling'] == 'steady':
            count += 1
            cursor -= timedelta(days=1)
        else:
            break
    return count


def adaptive_resume_plan(state, today):
    """Recommend which level and cushion to resume at after stabilization."""
    program = state['program']
    profile = state['profile']
    setbacks = state['setbacks']
    trigger = program.get('stabilizing_trigger') or {}
    from_level = program['level']
    crash_key = trigger.get('date') or program.get('stabilizing_since') or today.isoformat()
    crash_day = date.fromisoformat(crash_key)
    level_started = date.fromisoformat(program['level_started'])
    days_at_level = max(0, (crash_day - level_started).days)
    external = bool(trigger.get('external_trigger'))

    recent_setbacks = [
        sb for sb in setbacks
        if 0 <= (crash_day - date.fromisoformat(sb['crash_date'])).days <= 28
    ]
    repeat_after_drop = any(
        0 <= (crash_day - date.fromisoformat(sb['resumed_date'])).days <= 21
        and sb['resumed_level'] >= from_level - 1
        for sb in setbacks
    )

    if repeat_after_drop or len(recent_setbacks) >= 1:
        recommended = max(1, from_level - 2) if from_level >= 3 else 1
        cushion_pct = 15
        extra_hold = 7
        reason = (
            f'Because another setback happened soon after a previous drop, stepping back to '
            f'Level {recommended} with a 15% lighter routine and 7 extra steady days gives your '
            f'body a softer rebuild.'
        )
    elif external and days_at_level >= 7:
        recommended = from_level
        cushion_pct = 0
        extra_hold = 3
        triggers = [b['label'] for b in trigger.get('beyond_plan', ())] + [
            FACTORS[f] for f in trigger.get('factors', ()) if f in ('illness', 'stress')
        ]
        detail = ', '.join(dict.fromkeys(triggers)) or 'an extra stressor'
        reason = (
            f'You held Level {from_level} steadily for {days_at_level} days before {detail}. '
            f'You can resume at Level {from_level} (or choose Level {max(1, from_level - 1)} for extra margin).'
        )
    else:
        recommended = max(1, from_level - 1)
        cushion_pct = 0
        extra_hold = 0
        if recommended == from_level:
            reason = 'You are already at Level 1. Resume with the gentle foundation routine and protect rest.'
        else:
            reason = (
                f'Stepping back from Level {from_level} to Level {recommended} eases the daily load '
                f'back into a comfortable baseline before moving forward again.'
            )

    hold_scale = profile.get('hold_scale', 1.0)
    return {
        'recommended_level': recommended,
        'from_level': from_level,
        'cushion_pct': cushion_pct,
        'extra_hold_days': extra_hold,
        'hold_days': scaled_hold_days(recommended, hold_scale) + extra_hold,
        'days_at_level': days_at_level,
        'external_trigger': external,
        'reason': reason,
    }


def compute_program_status(state, today):
    """Compute steady streak, step-up readiness, stabilization state, and active daily activities."""
    profile = state['profile']
    program = state['program']
    checkins = state['checkins']
    today_key = today.isoformat()
    level = program['level']
    hold_days = program['hold_days']
    level_started = program['level_started']
    disabled = tuple(profile.get('disabled_categories', ()))

    if program['mode'] == 'stabilizing':
        steady_streak = stabilizing_streak(checkins, program.get('stabilizing_since'), today)
        resume_plan = adaptive_resume_plan(state, today)
        ready_to_resume = steady_streak >= STABILIZE_STEADY_TARGET
        activities = list(STABILIZATION_ACTIVITIES)
        return {
            'mode': 'stabilizing',
            'level': level,
            'hold_days': hold_days,
            'steady_days': 0,
            'remaining_days': 0,
            'stabilize_steady_days': steady_streak,
            'stabilize_target': STABILIZE_STEADY_TARGET,
            'ready_to_resume': ready_to_resume,
            'resume_recommendation': resume_plan,
            'step_up_ready': False,
            'pending_watch': None,
            'hold_note': None,
            'activities': activities,
            'cushion_pct': program.get('cushion_pct', 0),
        }

    # Active mode: count steady/worn days logged at this active level since level_started and after any dip.
    last_dip = max(
        (d for d, entry in checkins.items()
         if level_started <= d <= today_key
         and entry.get('level') == level
         and entry.get('mode', 'active') == 'active'
         and entry['feeling'] in LOW_FEELINGS),
        default=None,
    )
    steady_days = sum(
        1 for d, entry in checkins.items()
        if level_started <= d <= today_key
        and entry.get('level') == level
        and entry.get('mode', 'active') == 'active'
        and (last_dip is None or d > last_dip)
        and entry['feeling'] in STEADY_FEELINGS
    )
    remaining_days = max(0, hold_days - steady_days)

    # Check if an unplanned event or "too much" rating in the last 3 days is still within its 3-day PEM window.
    pending_watch = None
    for offset in range(0, PEM_LOOKBACK_DAYS):
        d = today - timedelta(days=offset)
        entry = checkins.get(d.isoformat())
        if not entry:
            continue
        flagged = [bp['label'] for bp in entry.get('beyond_plan', ())]
        for act_id, rating in entry.get('activities', {}).items():
            if rating == 'too_much':
                flagged.append(act_id)
        if flagged:
            watch_until = d + timedelta(days=PEM_LOOKBACK_DAYS)
            if today < watch_until:
                pending_watch = {
                    'date': d.isoformat(),
                    'watch_until': watch_until.isoformat(),
                    'items': list(dict.fromkeys(flagged)),
                }
                break

    step_up_ready = level < 12 and steady_days >= hold_days and pending_watch is None

    # Boredom / hold reassurance once past halfway through the hold window.
    hold_note = None
    if level < 12 and not step_up_ready and steady_days >= max(3, hold_days // 2):
        recent_entries = [
            entry for d, entry in checkins.items()
            if level_started <= d <= today_key and (last_dip is None or d > last_dip)
        ]
        if any('could_do_more' in entry.get('activities', {}).values() for entry in recent_entries) or steady_days >= hold_days // 2:
            hold_note = (
                f'Feeling steady or restless here is normal. Holding Level {level} for {remaining_days} more '
                f'steady {"day" if remaining_days == 1 else "days"} gives your body time to consolidate before stepping up.'
            )

    activities = level_activities(
        level,
        cushion_pct=program.get('cushion_pct', 0),
        disabled_categories=disabled,
    )
    return {
        'mode': 'active',
        'level': level,
        'hold_days': hold_days,
        'steady_days': min(steady_days, hold_days),
        'remaining_days': remaining_days,
        'stabilize_steady_days': 0,
        'stabilize_target': STABILIZE_STEADY_TARGET,
        'ready_to_resume': False,
        'resume_recommendation': None,
        'step_up_ready': step_up_ready,
        'pending_watch': pending_watch,
        'hold_note': hold_note,
        'activities': activities,
        'cushion_pct': program.get('cushion_pct', 0),
    }


def build_trajectory(state, status, today):
    """Build actual history curve, projected recovery curve to Level 12, and 12-level milestones."""
    profile = state['profile']
    program = state['program']
    checkins = state['checkins']
    hold_scale = profile.get('hold_scale', 1.0)
    disabled = tuple(profile.get('disabled_categories', ()))
    today_key = today.isoformat()

    history = list(state.get('history', ()))
    actual_points = [
        {
            'date': item['date'],
            'level': item['level'],
            'event': item['event'],
            'note': item.get('note', ''),
        }
        for item in history
    ]
    if not actual_points or actual_points[-1]['date'] != today_key or actual_points[-1]['level'] != program['level']:
        actual_points.append({
            'date': today_key,
            'level': program['level'],
            'event': 'stabilizing' if program['mode'] == 'stabilizing' else 'current',
            'note': '',
        })

    # Daily feeling markers along the actual trajectory for chart annotations.
    daily_markers = [
        {
            'date': d,
            'level': entry['level'],
            'feeling': entry['feeling'],
        }
        for d, entry in sorted(checkins.items())
        if d <= today_key
    ]

    # Projected curve starting from today out to Level 12.
    projected_points = [{'date': today_key, 'level': program['level']}]
    projected_dates = {}

    if program['level'] < 12:
        if status['mode'] == 'stabilizing':
            rec = status['resume_recommendation']
            stab_left = max(0, STABILIZE_STEADY_TARGET - status['stabilize_steady_days'])
            resume_day = today + timedelta(days=stab_left)
            resume_level = rec['recommended_level']
            projected_points.append({'date': resume_day.isoformat(), 'level': resume_level})
            cursor = resume_day + timedelta(days=rec['hold_days'])
            next_lvl = resume_level + 1
        else:
            rem = status['remaining_days']
            if status['pending_watch']:
                watch_end = date.fromisoformat(status['pending_watch']['watch_until'])
                rem = max(rem, (watch_end - today).days)
            cursor = today + timedelta(days=rem)
            next_lvl = program['level'] + 1

        for lvl in range(next_lvl, 13):
            projected_dates[lvl] = cursor.isoformat()
            projected_points.append({'date': cursor.isoformat(), 'level': lvl})
            if lvl < 12:
                cursor += timedelta(days=scaled_hold_days(lvl, hold_scale))
        estimated_full_date = projected_dates[12]
    else:
        estimated_full_date = program['level_started']

    # Determine completion dates for levels already passed.
    completed_dates = {}
    for item in history:
        if item['event'] == 'advance':
            completed_dates[item['level'] - 1] = item['date']

    milestones = []
    for lvl in range(1, 13):
        spec = LEVELS[lvl]
        if lvl < program['level']:
            m_status = 'completed'
            m_date = completed_dates.get(lvl)
        elif lvl == program['level']:
            m_status = 'current'
            m_date = program['level_started']
        else:
            m_status = 'upcoming'
            m_date = projected_dates.get(lvl)
        milestones.append({
            'level': lvl,
            'phase': spec['phase'],
            'phase_name': spec['phase_name'],
            'title': spec['title'],
            'summary': spec['summary'],
            'hold_days': scaled_hold_days(lvl, hold_scale),
            'effort_ceiling': spec['effort_ceiling'],
            'activities': level_activities(lvl, disabled_categories=disabled),
            'status': m_status,
            'date': m_date,
        })

    return {
        'actual_points': actual_points,
        'daily_markers': daily_markers,
        'projected_points': projected_points,
        'projected_dates': projected_dates,
        'estimated_full_recovery_date': estimated_full_date,
        'milestones': milestones,
    }


def recent_lows_summary(checkins, today):
    """Return recent worse/crash days paired with their 1-3 day lookback context."""
    lows = []
    for d in sorted(checkins.keys(), reverse=True):
        entry = checkins[d]
        if entry['feeling'] not in LOW_FEELINGS:
            continue
        day = date.fromisoformat(d)
        if (today - day).days > 30:
            continue
        prior = inspect_prior_days(checkins, day)
        lows.append({
            'date': d,
            'feeling': entry['feeling'],
            'level': entry['level'],
            **prior,
        })
    return lows[:10]


class PlannerStore:
    lock = Lock()

    def __init__(self, path=DATA_FILE):
        self.path = path

    def load(self):
        try:
            with self.path.open(encoding='utf-8') as record:
                return normalize_state(json.load(record))
        except FileNotFoundError:
            return blank_state()

    def save(self, state):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = self.path.with_suffix('.tmp')
        try:
            temporary.write_text(json.dumps(state, ensure_ascii=False), encoding='utf-8')
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def view(self, state, today):
        today_key = today.isoformat()
        if not state.get('profile') or not state.get('program'):
            return {
                'today': today_key,
                'onboarded': False,
                'profile': None,
                'program': None,
                'assessment_questions': ASSESSMENT_QUESTIONS,
                'phases': PHASES,
                'levels': LEVELS,
                'feelings': FEELINGS,
                'activity_ratings': ACTIVITY_RATINGS,
                'factors': FACTORS,
                'beyond_plan_presets': BEYOND_PLAN_PRESETS,
                'checkins': {},
                'benchmarks': [],
                'recent_lows': [],
                'trajectory': None,
            }

        status = compute_program_status(state, today)
        trajectory = build_trajectory(state, status, today)
        benchmarks = compute_benchmarks(state['checkins'], today)
        lows = recent_lows_summary(state['checkins'], today)
        profile = state['profile']
        current_spec = LEVELS[status['level']]
        next_spec = LEVELS.get(status['level'] + 1)

        return {
            'today': today_key,
            'onboarded': True,
            'profile': profile,
            'program': {
                **state['program'],
                **status,
                'phase': current_spec['phase'],
                'phase_name': current_spec['phase_name'],
                'title': current_spec['title'],
                'summary': current_spec['summary'],
                'effort_ceiling': current_spec['effort_ceiling'],
                'next_level': {
                    'level': next_spec['level'],
                    'phase_name': next_spec['phase_name'],
                    'title': next_spec['title'],
                    'summary': next_spec['summary'],
                } if next_spec else None,
            },
            'phases': PHASES,
            'levels': LEVELS,
            'assessment_questions': ASSESSMENT_QUESTIONS,
            'feelings': FEELINGS,
            'activity_ratings': ACTIVITY_RATINGS,
            'factors': FACTORS,
            'beyond_plan_presets': BEYOND_PLAN_PRESETS,
            'checkins': state['checkins'],
            'benchmarks': benchmarks,
            'recent_lows': lows,
            'trajectory': trajectory,
        }

    def read(self):
        with self.lock:
            return self.view(self.load(), date.today())

    def update(self, action, payload):
        today = date.today()
        with self.lock:
            state = self.load()
            self.apply(state, action, payload, today)
            self.save(state)
            return self.view(state, today)

    def apply(self, state, action, payload, today):
        if action == 'assessment':
            self._apply_assessment(state, payload, today)
        elif action == 'checkin':
            self._apply_checkin(state, payload, today)
        elif action == 'decision':
            self._apply_decision(state, payload, today)
        elif action == 'preferences':
            self._apply_preferences(state, payload, today)
        else:
            raise ValueError('Unknown planner action.')

    def _apply_assessment(self, state, payload, today):
        answers = payload.get('answers')
        result = evaluate_assessment(answers)
        chosen = payload.get('starting_level')
        level = result['recommended_level'] if chosen is None else parse_level(chosen)
        hold_scale = parse_hold_scale(payload.get('hold_scale', 1.0))
        today_key = today.isoformat()
        existing_profile = state.get('profile') or {}
        disabled = existing_profile.get('disabled_categories', [])
        first_time = state.get('profile') is None

        state['profile'] = {
            'onboarded_at': existing_profile.get('onboarded_at', today_key),
            'assessment': {
                'answers': answers,
                'recommended_level': result['recommended_level'],
                'chosen_level': level,
            },
            'disabled_categories': disabled,
            'hold_scale': hold_scale,
        }
        state['program'] = {
            'level': level,
            'level_started': today_key,
            'hold_days': scaled_hold_days(level, hold_scale),
            'cushion_pct': 0,
            'mode': 'active',
            'stabilizing_since': None,
            'stabilizing_trigger': None,
            'pending_resume': None,
        }
        event = 'start' if first_time else 'adjust'
        note = f'Started at Level {level}' if first_time else f'Re-assessed to Level {level}'
        state['history'].append({
            'date': today_key,
            'level': level,
            'event': event,
            'note': note,
        })

    def _apply_checkin(self, state, payload, today):
        if not state.get('profile') or not state.get('program'):
            raise ValueError('Complete the starting assessment first.')

        raw_day = payload.get('date')
        try:
            day = date.fromisoformat(raw_day)
            if raw_day != day.isoformat() or day > today or day < date(1900, 1, 1):
                raise ValueError
        except (TypeError, ValueError):
            raise ValueError('Enter a valid date from today or earlier.') from None

        feeling = payload.get('feeling')
        if not isinstance(feeling, str) or feeling not in FEELINGS:
            raise ValueError('Choose how you felt today.')

        program = state['program']
        checkins = state['checkins']
        existing = checkins.get(raw_day)
        day_level = existing['level'] if existing else program['level']
        day_mode = existing['mode'] if existing else program['mode']

        valid_activity_ids = {
            item['id'] for item in (
                STABILIZATION_ACTIVITIES if day_mode == 'stabilizing'
                else LEVELS[day_level]['activities']
            )
        }
        raw_activities = payload.get('activities', {})
        if not isinstance(raw_activities, dict):
            raise ValueError('Invalid activity feedback.')
        activities = {}
        for act_id, rating in raw_activities.items():
            if act_id not in valid_activity_ids:
                raise ValueError(f'Unknown activity: {act_id}.')
            if rating not in ACTIVITY_RATINGS:
                raise ValueError('Choose a valid rating for each activity.')
            activities[act_id] = rating

        raw_factors = payload.get('factors', [])
        if not isinstance(raw_factors, list):
            raise ValueError('Invalid energy factors.')
        factors = []
        for factor in raw_factors:
            if not isinstance(factor, str) or factor not in FACTORS:
                raise ValueError('Choose valid energy factors.')
            if factor not in factors:
                factors.append(factor)

        raw_beyond = payload.get('beyond_plan', [])
        if not isinstance(raw_beyond, list) or len(raw_beyond) > MAX_BEYOND_PLAN:
            raise ValueError(f'Log up to {MAX_BEYOND_PLAN} unplanned activities per day.')
        beyond_plan = []
        for item in raw_beyond:
            if not isinstance(item, dict):
                raise ValueError('Invalid unplanned activity.')
            label = clean_string(item.get('label'), 60)
            if not label:
                raise ValueError('Enter a name for the unplanned activity.')
            effort = item.get('effort', 'medium')
            if effort not in EFFORT_LEVELS:
                raise ValueError('Choose light, medium, or heavy effort.')
            mins = optional_minutes(item.get('minutes'))
            item_id = item.get('id') if isinstance(item.get('id'), str) and item.get('id') else uuid4().hex[:12]
            beyond_plan.append({
                'id': item_id,
                'label': label,
                'effort': effort,
                'minutes': mins,
            })

        note = clean_string(payload.get('note', ''), 300)
        checkins[raw_day] = {
            'feeling': feeling,
            'level': day_level,
            'mode': day_mode,
            'activities': activities,
            'factors': factors,
            'beyond_plan': beyond_plan,
            'note': note,
        }

        # Check stabilization trigger for check-ins at or after current level_started while active.
        level_started = date.fromisoformat(program['level_started'])
        if program['mode'] == 'active' and day >= level_started:
            triggered_reason = None
            if feeling == 'crash':
                triggered_reason = 'crash'
            elif feeling == 'worse':
                prev_day = next(
                    (
                        d for d in sorted(checkins.keys(), reverse=True)
                        if level_started.isoformat() <= d < raw_day
                        and (day - date.fromisoformat(d)).days <= 2
                    ),
                    None,
                )
                if prev_day and checkins[prev_day]['feeling'] == 'worse':
                    triggered_reason = 'two_worse'

            if triggered_reason:
                prior = inspect_prior_days(checkins, day)
                program['mode'] = 'stabilizing'
                program['stabilizing_since'] = raw_day
                program['stabilizing_trigger'] = {
                    'date': raw_day,
                    'reason': triggered_reason,
                    **prior,
                }
                program['pending_resume'] = None
                if not any(
                    h['date'] == raw_day and h['event'] == 'crash'
                    for h in state['history']
                ):
                    state['history'].append({
                        'date': raw_day,
                        'level': program['level'],
                        'event': 'crash',
                        'note': 'Entered stabilization mode',
                    })
        elif program['mode'] == 'stabilizing' and feeling == 'crash' and raw_day > (program.get('stabilizing_since') or ''):
            program['stabilizing_since'] = raw_day
            if not any(h['date'] == raw_day and h['event'] == 'crash' for h in state['history']):
                state['history'].append({
                    'date': raw_day,
                    'level': program['level'],
                    'event': 'crash',
                    'note': 'Continued stabilization',
                })

    def _apply_decision(self, state, payload, today):
        if not state.get('profile') or not state.get('program'):
            raise ValueError('Complete the starting assessment first.')
        program = state['program']
        profile = state['profile']
        hold_scale = profile.get('hold_scale', 1.0)
        choice = payload.get('choice')
        today_key = today.isoformat()
        status = compute_program_status(state, today)

        if choice == 'advance':
            if program['mode'] != 'active' or program['level'] >= 12 or not status['step_up_ready']:
                raise ValueError('This level is not ready to advance yet.')
            next_lvl = program['level'] + 1
            program['level'] = next_lvl
            program['level_started'] = today_key
            program['hold_days'] = scaled_hold_days(next_lvl, hold_scale)
            program['cushion_pct'] = 0
            state['history'].append({
                'date': today_key,
                'level': next_lvl,
                'event': 'advance',
                'note': f'Stepped up to Level {next_lvl}',
            })
        elif choice == 'hold_five':
            if program['mode'] != 'active' or program['level'] >= 12:
                raise ValueError('Cannot extend hold right now.')
            program['hold_days'] += 5
        elif choice == 'resume':
            if program['mode'] != 'stabilizing':
                raise ValueError('Not currently in stabilization mode.')
            rec = adaptive_resume_plan(state, today)
            override = payload.get('level')
            target_level = rec['recommended_level'] if override is None else parse_level(override)
            # Only apply cushion/extra hold automatically when following recommendation or stepping back further.
            if override is None or target_level <= rec['recommended_level']:
                cushion_pct = rec['cushion_pct']
                extra_hold = rec['extra_hold_days']
            else:
                cushion_pct = 0
                extra_hold = 0
            trigger = program.get('stabilizing_trigger') or {}
            state['setbacks'].append({
                'crash_date': trigger.get('date') or program.get('stabilizing_since') or today_key,
                'from_level': program['level'],
                'resumed_date': today_key,
                'resumed_level': target_level,
                'external_trigger': bool(trigger.get('external_trigger')),
                'days_at_level': rec['days_at_level'],
                'cushion_pct': cushion_pct,
            })
            program['mode'] = 'active'
            program['level'] = target_level
            program['level_started'] = today_key
            program['hold_days'] = scaled_hold_days(target_level, hold_scale) + extra_hold
            program['cushion_pct'] = cushion_pct
            program['stabilizing_since'] = None
            program['stabilizing_trigger'] = None
            program['pending_resume'] = None
            state['history'].append({
                'date': today_key,
                'level': target_level,
                'event': 'resume',
                'note': f'Resumed at Level {target_level}',
            })
        elif choice == 'set_level':
            target_level = parse_level(payload.get('level'))
            program['mode'] = 'active'
            program['level'] = target_level
            program['level_started'] = today_key
            program['hold_days'] = scaled_hold_days(target_level, hold_scale)
            program['cushion_pct'] = 0
            program['stabilizing_since'] = None
            program['stabilizing_trigger'] = None
            program['pending_resume'] = None
            state['history'].append({
                'date': today_key,
                'level': target_level,
                'event': 'adjust',
                'note': f'Adjusted to Level {target_level}',
            })
        else:
            raise ValueError('Choose a valid roadmap action.')

    def _apply_preferences(self, state, payload, today):
        if not state.get('profile') or not state.get('program'):
            raise ValueError('Complete the starting assessment first.')
        profile = state['profile']
        program = state['program']

        if 'disabled_categories' in payload:
            raw_disabled = payload['disabled_categories']
            if not isinstance(raw_disabled, list):
                raise ValueError('Invalid disabled categories.')
            cleaned = []
            for cat in raw_disabled:
                if not isinstance(cat, str) or cat not in OPTIONAL_CATEGORIES:
                    raise ValueError('Only optional activity categories can be turned off.')
                if cat not in cleaned:
                    cleaned.append(cat)
            profile['disabled_categories'] = cleaned

        if 'hold_scale' in payload:
            new_scale = parse_hold_scale(payload['hold_scale'])
            old_scale = profile.get('hold_scale', 1.0)
            profile['hold_scale'] = new_scale
            if new_scale != old_scale:
                program['hold_days'] = scaled_hold_days(program['level'], new_scale)

        if 'hold_days' in payload and payload['hold_days'] is not None:
            hd = payload['hold_days']
            if type(hd) is not int or not 7 <= hd <= 90:
                raise ValueError('Choose a level hold window between 7 and 90 days.')
            program['hold_days'] = hd
