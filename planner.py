"""Local records and descriptive activity projections."""

from datetime import date, timedelta
import json
from pathlib import Path
from statistics import median
from threading import Lock
from uuid import uuid4

from guidance import KINDS, MAX_ROUTINE, STAGES, SUGGESTIONS, above_plan, roadmap


DATA_FILE = Path(__file__).resolve().parent / 'local_data' / 'planner.json'
CHECK_INS = {'better', 'usual', 'worse', 'crash'}
LOW = {'worse', 'crash'}
LOOKBACK = 3
HISTORY = 14
HORIZON = 7


def minutes(value, *, optional=False):
    if optional and value is None:
        return None
    if type(value) is not int or not 0 <= value <= 1440:
        raise ValueError('Enter a whole number of minutes from 0 to 1440.')
    return value


def string(value, limit):
    if not isinstance(value, str) or len(value) > limit:
        raise ValueError(f'Enter text of up to {limit} characters.')
    return value.strip()


def saved_limit(plan):
    return plan['step_back'] if plan['stepped_back'] else plan['limit']


def activity_entries(state):
    plan = state['plan']
    key = plan['activity'].casefold() if plan else ''
    entries = {
        day: {**entry, 'minutes': None, 'planned': None}
        for other_key, history in state['activities'].items() if other_key != key
        for day, entry in history.items()
    }
    entries.update(state['activities'].get(key, {}))
    return entries


def change_routine(state, payload):
    routine = state.setdefault('routine', {})
    operation = payload.get('operation')
    if operation in ('remove', 'edit'):
        key = payload.get('id')
        if not isinstance(key, str) or key not in routine:
            raise ValueError('That routine item has changed. Reload the planner.')
        if operation == 'remove':
            del routine[key]
        else:
            routine[key]['planned'] = minutes(payload.get('planned'), optional=True)
        return
    if operation != 'add':
        raise ValueError('Choose what to change in your routine.')
    if len(routine) >= MAX_ROUTINE:
        raise ValueError(f'Your routine can hold up to {MAX_ROUTINE} items.')
    suggestion = payload.get('suggestion')
    if suggestion is not None:
        if not isinstance(suggestion, str) or suggestion not in SUGGESTIONS:
            raise ValueError('Choose a suggested activity.')
        name, kind, _ = SUGGESTIONS[suggestion]
    else:
        name = string(payload.get('name'), 60)
        kind = payload.get('kind')
    if not name or kind not in KINDS:
        raise ValueError('Enter an activity name and choose its type.')
    picked = [item['name'].casefold() for item in routine.values()]
    if state['plan']:
        picked.append(state['plan']['activity'].casefold())
    if name.casefold() in picked:
        raise ValueError('That activity is already in your plan.')
    routine[uuid4().hex] = {
        'name': name, 'kind': kind, 'planned': minutes(payload.get('planned'), optional=True),
        'suggestion': suggestion,
    }


def logged_routine(routine, previous, values):
    if not isinstance(values, dict) or len(values) > MAX_ROUTINE * 2:
        raise ValueError('Check the minutes for your routine.')
    result = previous.copy()
    for key, value in values.items():
        original = previous.get(key)
        item = original or routine.get(key)
        if not item:
            raise ValueError('Your routine changed. Reload the planner before saving.')
        actual = minutes(value, optional=True)
        if actual is None:
            result.pop(key, None)
        else:
            result[key] = {'name': item['name'], 'kind': item['kind'],
                           'planned': item['planned'], 'minutes': actual}
    return result


def change_roadmap(state, payload, today):
    settings = state.setdefault('guidance', {})
    direction = payload.get('direction')
    if direction == 'interval':
        interval = payload.get('interval')
        if type(interval) is not int or not 2 <= interval <= 30:
            raise ValueError('Choose a review interval from 2 to 30 check-ins.')
        settings['interval'] = interval
        return
    stage = settings.get('stage', 0)
    if direction == 'next' and stage < len(STAGES) - 1 and roadmap(state, today, activity_entries(state))['ready']:
        settings['stage'] = stage + 1
    elif direction == 'back' and stage > 0:
        settings['stage'] = stage - 1
    else:
        raise ValueError('This roadmap change is unavailable. Review your recent check-ins.')
    settings['started'] = today.isoformat()


def activity_view(plan, entries, today):
    days = {date.fromisoformat(day): entry for day, entry in entries.items()}
    start = today - timedelta(days=HISTORY - 1)
    history = [
        {'date': day.isoformat(), **days[day]}
        for day in sorted(days) if start <= day <= today
    ]
    lows = []
    for item in reversed(history):
        if item['feeling'] not in LOW:
            continue
        day = date.fromisoformat(item['date'])
        prior = []
        for offset in range(1, LOOKBACK + 1):
            earlier = day - timedelta(days=offset)
            prior.append({'date': earlier.isoformat(), **days.get(earlier, {})})
        lows.append({'date': item['date'], 'feeling': item['feeling'], 'prior': prior})

    recent = [days.get(today - timedelta(days=offset), {}) for offset in range(LOOKBACK)]
    recent_lows = [low for low in lows
                   if date.fromisoformat(low['date']) > today - timedelta(days=LOOKBACK)]
    review = bool(recent_lows)
    above_before_low = any(above_plan(entry) for low in recent_lows for entry in low['prior'])
    values = []
    for day, entry in days.items():
        if not start <= day <= today - timedelta(days=LOOKBACK):
            continue
        following = [days.get(day + timedelta(days=offset), {}) for offset in range(1, LOOKBACK + 1)]
        if (entry['minutes'] is not None
                and entry['feeling'] in CHECK_INS - LOW
                and all(item.get('feeling') in CHECK_INS - LOW for item in following)):
            values.append(entry['minutes'])

    paused = plan['stepped_back'] or review
    # A descriptive carry-forward estimate, separate from either saved limit.
    projection = median(values) if len(values) >= 3 and recent[0] and not paused else None
    return {
        'plan': plan, 'history': history, 'lows': lows, 'review': review,
        'paused': paused, 'projection': projection, 'sample_size': len(values),
        'above_before_low': above_before_low,
        'start': start.isoformat(), 'end': (today + timedelta(days=HORIZON)).isoformat(),
    }


class PlannerStore:
    lock = Lock()

    def __init__(self, path=DATA_FILE):
        self.path = path

    def load(self):
        try:
            with self.path.open(encoding='utf-8') as record:
                return json.load(record)
        except FileNotFoundError:
            return {'plan': None, 'activities': {}}

    def save(self, state):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = self.path.with_suffix('.tmp')
        try:
            temporary.write_text(json.dumps(state, ensure_ascii=False), encoding='utf-8')
            temporary.replace(self.path)
        finally:
            temporary.unlink(missing_ok=True)

    def view(self, state, today):
        plan = state['plan']
        entries = activity_entries(state)
        result = activity_view(plan or {'stepped_back': False}, entries, today)
        return {'today': today.isoformat(), 'roadmap': roadmap(state, today, entries),
                'routine': state.get('routine', {}), **result, 'plan': plan}

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
        plan = state['plan']
        if action == 'roadmap':
            change_roadmap(state, payload, today)
            return
        if action == 'routine':
            change_routine(state, payload)
            return
        if action == 'plan':
            activity = string(payload.get('activity'), 60)
            if not activity:
                raise ValueError('Enter an activity name.')
            limit = minutes(payload.get('limit'))
            step_back = minutes(payload.get('step_back'), optional=True)
            if step_back is not None and step_back > limit:
                raise ValueError('The step-back limit must be at or below the usual limit.')
            stepped_back = bool(plan and plan['stepped_back']
                                and plan['activity'].casefold() == activity.casefold())
            if stepped_back and step_back is None:
                raise ValueError('Keep a step-back limit while the lower plan is active.')
            state['plan'] = {
                'activity': activity, 'limit': limit, 'step_back': step_back,
                'stepped_back': stepped_back, 'rest': string(payload.get('rest', ''), 300),
            }
            return
        activity = plan['activity'] if plan else None
        if payload.get('activity') != activity:
            raise ValueError('The active plan changed. Refresh the page and try again.')
        if action == 'mode':
            active = payload.get('stepped_back')
            if not plan or type(active) is not bool or (active and plan['step_back'] is None):
                raise ValueError('Save a step-back limit first.')
            plan['stepped_back'] = active
            return

        try:
            raw_day = payload.get('date')
            day = date.fromisoformat(raw_day)
            if raw_day != day.isoformat() or day > today or day < date(1900, 1, 1):
                raise ValueError
        except (TypeError, ValueError):
            raise ValueError('Enter a date from today or earlier.') from None
        feeling = payload.get('feeling')
        if not isinstance(feeling, str) or feeling not in CHECK_INS:
            raise ValueError('Choose how you felt that day.')
        key = activity.casefold() if activity else ''
        entries = state['activities'].setdefault(key, {})
        previous = entries.get(raw_day)
        planned = previous['planned'] if previous else (saved_limit(plan) if plan and day == today else None)
        previous_routine = (previous or {}).get('routine')
        if previous is None:
            previous_routine = next((history[raw_day].get('routine', {})
                                     for history in state['activities'].values() if raw_day in history), {})
        routine = logged_routine(state.get('routine', {}), previous_routine or {},
                                 payload.get('routine', {}))
        entries[raw_day] = {
            'minutes': minutes(payload.get('minutes'), optional=True),
            'feeling': feeling, 'context': string(payload.get('context', ''), 300),
            'planned': planned, 'routine': routine,
        }
