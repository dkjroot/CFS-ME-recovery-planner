"""Roadmap and routine suggestions for the local planner."""

from datetime import date, timedelta


SUGGESTIONS = {
    'quiet-rest': ('Quiet rest', 'Rest', 'Set aside time with fewer demands. Choose quiet, low light or a comfortable place if that suits you.'),
    'essentials': ('One everyday task', 'Daily living', 'Pick an essential such as washing or preparing food. Plan it in parts or make room for help.'),
    'quiet-hobby': ('A quiet hobby', 'Thinking', 'Make room for something enjoyable you already know, such as reading, listening or drawing.'),
    'stretching': ('Familiar stretching', 'Movement', 'Add this if stretching already fits your plan. Use the version and limits you have chosen.'),
    'walking': ('Familiar walk', 'Movement', 'Add a walk if it already fits your plan, including time to rest and get back.'),
    'one-change': ('One change to review', 'Daily living', 'Choose one difference to discuss or track, such as splitting a task, changing its timing or swapping the format.'),
    'social': ('A call or visit', 'Social', 'Plan the length, breaks and a way to end early if you want to.'),
    'valued': ('Something you want to get back to', 'Daily living', 'Pick one part of a hobby, study, work or an outing. Include preparation, travel and time to rest.'),
    'help': ('Arrange help with an essential', 'Daily living', 'Choose a task someone else can take on, or move it to another day.'),
}
STAGES = (
    ('Make days steadier',
     'Build a day you can repeat. Start with rest, essentials and something you enjoy.',
     ('quiet-rest', 'essentials', 'quiet-hobby')),
    ('Review one change',
     'Keep the rest of the day familiar while you review one change and see how the days afterwards feel.',
     ('quiet-rest', 'one-change', 'stretching', 'walking')),
    ('Bring more of life back',
     'Make room for something that matters to you. Include the whole cost of the activity, including travel and social time.',
     ('quiet-rest', 'social', 'valued')),
)
STEP_BACK = ('quiet-rest', 'essentials', 'help')
KINDS = ('Rest', 'Daily living', 'Movement', 'Thinking', 'Social')
DEFAULT_REVIEW_DAYS = 7
MAX_ROUTINE = 12
LOW = {'crash', 'worse'}
FOLLOW_UP = 3
STEP_BACK_FOLLOW_UPS = 2


def above_plan(entry, activity=None):
    names = [item['name'] for item in entry.get('routine', {}).values()
             if item['kind'] != 'Rest' and item['planned'] is not None and item['minutes'] > item['planned']]
    if (entry.get('minutes') is not None and entry.get('planned') is not None
            and entry['minutes'] > entry['planned']):
        names.insert(0, activity or 'Chart activity')
    return names


def feedback(entries, feelings, today, activity):
    findings = {}
    for key, entry in entries.items():
        if not (entry.get('minutes') or any(item['minutes'] for item in entry.get('routine', {}).values())):
            continue
        day = date.fromisoformat(key)
        if not today - timedelta(days=16) <= day <= today:
            continue
        following = [day + timedelta(days=offset) for offset in range(1, FOLLOW_UP + 1)]
        low = next((later for later in following if feelings.get(later) in LOW), None)
        complete = all(later in feelings for later in following)
        status = 'low' if low else 'observed' if complete else 'pending' if following[-1] >= today else 'incomplete'
        findings[key] = {
            'status': status, 'days_until_low': (low - day).days if low else None,
            'check_again': following[-1].isoformat(), 'above_plan': above_plan(entry, activity),
        }
    return findings


def roadmap(state, today, entries):
    settings = state.get('guidance', {})
    stage = settings.get('stage', 0)
    interval = settings.get('interval', DEFAULT_REVIEW_DAYS)
    logged = {}
    for history in state['activities'].values():
        for key, entry in history.items():
            day = date.fromisoformat(key)
            if day <= today and logged.get(day) not in LOW:
                logged[day] = entry['feeling']
    start = (date.fromisoformat(settings['started']) + timedelta(days=1)
             if settings.get('started') else min(logged, default=today))
    latest_low = max((day for day, feeling in logged.items() if feeling in LOW), default=None)
    last_low = latest_low if latest_low is not None and latest_low >= start else None
    stable = sum(day >= start and (last_low is None or day > last_low) and feeling not in LOW
                 for day, feeling in logged.items())
    remaining = max(0, interval - stable)
    latest = max(logged, default=None)
    since_low = sum(day > latest_low for day in logged) if latest_low is not None else STEP_BACK_FOLLOW_UPS
    stepped_back = bool(state['plan'] and state['plan']['stepped_back'])
    setback = since_low < STEP_BACK_FOLLOW_UPS or stepped_back
    activity = state['plan']['activity'] if state['plan'] else None
    findings = feedback(entries, logged, today, activity)
    pending = [item for item in findings.values() if item['above_plan'] and item['status'] == 'pending']
    follow_up = max((date.fromisoformat(item['check_again']) for item in pending), default=None)
    review_items = list(dict.fromkeys(name for item in pending for name in item['above_plan']))
    missed = max((day for day, item in findings.items()
                  if item['above_plan'] and item['status'] == 'incomplete'), default=None)
    missing_follow_ups = 0
    if missed:
        missed_day = date.fromisoformat(missed)
        if missed_day >= start and (last_low is None or missed_day > last_low):
            observed_after = sum(day > missed_day and feeling not in LOW for day, feeling in logged.items())
            missing_follow_ups = max(0, FOLLOW_UP - observed_after)
            if missing_follow_ups:
                review_items = list(dict.fromkeys([*review_items, *findings[missed]['above_plan']]))
    if setback and latest_low:
        previous = [entries.get((latest_low - timedelta(days=offset)).isoformat(), {})
                    for offset in range(1, FOLLOW_UP + 1)]
        review_items = list(dict.fromkeys(name for item in previous for name in above_plan(item, activity)))
    ready = (not remaining and not setback and follow_up is None and not missing_follow_ups
             and latest is not None and latest >= today - timedelta(days=1))
    until_review = max(0, max(remaining, missing_follow_ups) - (start <= today and today not in logged))
    if setback or (not ready and not remaining and not follow_up and not missing_follow_ups):
        until_review = max(until_review, 1)
    earliest = today + timedelta(days=until_review)
    if follow_up:
        earliest = max(earliest, follow_up)

    stages = []
    for index, (title, description, options) in enumerate(STAGES):
        review = earliest + timedelta(days=interval * (index - stage - 1)) if index > stage else None
        stages.append({
            'title': title, 'description': description,
            'ideas': [SUGGESTIONS[key][0] for key in options],
            'review_date': review.isoformat() if review else None,
        })
    return {
        'stage': stage, 'interval': interval, 'stages': stages, 'ready': ready,
        'logged_days': min(stable, interval), 'remaining': remaining,
        'setback': setback, 'last_low': last_low.isoformat() if last_low else None,
        'follow_up': follow_up.isoformat() if follow_up else None, 'findings': findings,
        'review_items': review_items, 'missing_follow_ups': missing_follow_ups,
        'suggestions': [
            {'key': key, 'name': SUGGESTIONS[key][0], 'kind': SUGGESTIONS[key][1],
             'description': SUGGESTIONS[key][2]}
            for key in (STEP_BACK if setback else STAGES[stage][2])
        ],
        'kinds': KINDS,
    }
