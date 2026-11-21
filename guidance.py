"""Recovery program stages, daily activity templates, and starting assessment."""

PHASES = {
    1: {
        'phase': 1,
        'name': 'Restore & Stabilize',
        'effort': '2–3 / 10',
        'description': (
            'Calm the push-crash cycle first. Focus on protected rest and light daily living '
            'without pushing into fatigue.'
        ),
    },
    2: {
        'phase': 2,
        'name': 'Rebuild & Strengthen',
        'effort': '3–4 / 10',
        'description': (
            'Gradually add gentle movement, cognitive time, and home tasks, holding each step '
            'steady before building further.'
        ),
    },
    3: {
        'phase': 3,
        'name': 'Re-integrate into Life',
        'effort': '4–6 / 10',
        'description': (
            'Expand into longer outings, hobbies, and everyday demands while adapting smoothly '
            'to how your body feels.'
        ),
    },
}

LEVELS = {
    1: {
        'level': 1,
        'phase': 1,
        'phase_name': PHASES[1]['name'],
        'title': 'Deep Rest & Micro-Movements',
        'summary': 'Stop energy drains and stabilize your baseline from home or bed.',
        'hold_days': 21,
        'effort_ceiling': '2 / 10',
        'activities': [
            {
                'id': 'rest',
                'label': 'Quiet rest',
                'category': 'Rest',
                'target': 'Scheduled low-stimulation rest blocks',
                'minutes': None,
                'optional': False,
            },
            {
                'id': 'household',
                'label': 'Basic essentials',
                'category': 'Household',
                'target': 'Sitting up for meals and personal care',
                'minutes': 10,
                'optional': False,
            },
            {
                'id': 'stretching',
                'label': 'Gentle reset',
                'category': 'Movement',
                'target': '3 min slow breathing or bed/chair mobility',
                'minutes': 3,
                'optional': True,
            },
            {
                'id': 'mental',
                'label': 'Calm reading or audio',
                'category': 'Cognitive',
                'target': '5 min easy reading or calm listening',
                'minutes': 5,
                'optional': True,
            },
        ],
    },
    2: {
        'level': 2,
        'phase': 1,
        'phase_name': PHASES[1]['name'],
        'title': 'Steady Home Rhythm',
        'summary': 'Keep days predictable with one small home task and brief mental focus.',
        'hold_days': 21,
        'effort_ceiling': '2–3 / 10',
        'activities': [
            {
                'id': 'rest',
                'label': 'Quiet rest',
                'category': 'Rest',
                'target': 'Two calm recharge breaks during the day',
                'minutes': None,
                'optional': False,
            },
            {
                'id': 'household',
                'label': 'Light household task',
                'category': 'Household',
                'target': 'One 10 min task (e.g. making tea or light tidy)',
                'minutes': 10,
                'optional': False,
            },
            {
                'id': 'stretching',
                'label': 'Gentle stretching',
                'category': 'Movement',
                'target': '5 min easy seated or floor stretches',
                'minutes': 5,
                'optional': True,
            },
            {
                'id': 'mental',
                'label': 'Reading & mental tasks',
                'category': 'Cognitive',
                'target': '10 min calm reading or light screen time',
                'minutes': 10,
                'optional': False,
            },
            {
                'id': 'social',
                'label': 'Short check-in',
                'category': 'Social',
                'target': '5 min message or brief chat with someone close',
                'minutes': 5,
                'optional': True,
            },
        ],
    },
    3: {
        'level': 3,
        'phase': 1,
        'phase_name': PHASES[1]['name'],
        'title': 'First Short Walks',
        'summary': 'Introduce very short flat walks while keeping the rest of the day light.',
        'hold_days': 21,
        'effort_ceiling': '3 / 10',
        'activities': [
            {
                'id': 'rest',
                'label': 'Quiet rest',
                'category': 'Rest',
                'target': 'Planned afternoon rest with low stimulation',
                'minutes': None,
                'optional': False,
            },
            {
                'id': 'household',
                'label': 'Light household work',
                'category': 'Household',
                'target': '15 min split into two small tasks',
                'minutes': 15,
                'optional': False,
            },
            {
                'id': 'walking',
                'label': 'Easy flat walk',
                'category': 'Movement',
                'target': '4 min gentle walk on flat ground',
                'minutes': 4,
                'optional': False,
            },
            {
                'id': 'stretching',
                'label': 'Gentle stretching',
                'category': 'Movement',
                'target': '5 min easy mobility or legs-up-wall',
                'minutes': 5,
                'optional': True,
            },
            {
                'id': 'mental',
                'label': 'Reading & mental tasks',
                'category': 'Cognitive',
                'target': '15 min reading, puzzles, or calm screen time',
                'minutes': 15,
                'optional': False,
            },
            {
                'id': 'social',
                'label': 'Brief chat',
                'category': 'Social',
                'target': '10 min calm call or conversation',
                'minutes': 10,
                'optional': True,
            },
        ],
    },
    4: {
        'level': 4,
        'phase': 1,
        'phase_name': PHASES[1]['name'],
        'title': 'Consistent Light Days',
        'summary': 'Hold a repeatable daily routine across movement, home, and thinking.',
        'hold_days': 24,
        'effort_ceiling': '3 / 10',
        'activities': [
            {
                'id': 'rest',
                'label': 'Quiet rest',
                'category': 'Rest',
                'target': 'Scheduled midday recharge break',
                'minutes': None,
                'optional': False,
            },
            {
                'id': 'household',
                'label': 'Household work',
                'category': 'Household',
                'target': '15 min light meal prep or tidying',
                'minutes': 15,
                'optional': False,
            },
            {
                'id': 'walking',
                'label': 'Gentle walk',
                'category': 'Movement',
                'target': '8 min unhurried walk (stop feeling fresh)',
                'minutes': 8,
                'optional': False,
            },
            {
                'id': 'stretching',
                'label': 'Mobility & movement snacks',
                'category': 'Movement',
                'target': '8 min light stretching or mini movements',
                'minutes': 8,
                'optional': True,
            },
            {
                'id': 'mental',
                'label': 'Reading & mental tasks',
                'category': 'Cognitive',
                'target': '20 min steady reading or gentle desk focus',
                'minutes': 20,
                'optional': False,
            },
            {
                'id': 'social',
                'label': 'Social connection',
                'category': 'Social',
                'target': '15 min call or relaxed catch-up at home',
                'minutes': 15,
                'optional': True,
            },
        ],
    },
    5: {
        'level': 5,
        'phase': 2,
        'phase_name': PHASES[2]['name'],
        'title': 'Daily Walking Rhythm',
        'summary': 'Transition into gentle reconditioning with steady 10–12 minute walks.',
        'hold_days': 24,
        'effort_ceiling': '3–4 / 10',
        'activities': [
            {
                'id': 'rest',
                'label': 'Quiet rest',
                'category': 'Rest',
                'target': 'Protected afternoon rest window',
                'minutes': None,
                'optional': False,
            },
            {
                'id': 'household',
                'label': 'Household work',
                'category': 'Household',
                'target': '20 min everyday home chores in paced chunks',
                'minutes': 20,
                'optional': False,
            },
            {
                'id': 'walking',
                'label': 'Daily walk',
                'category': 'Movement',
                'target': '12 min steady walk at an easy pace',
                'minutes': 12,
                'optional': False,
            },
            {
                'id': 'stretching',
                'label': 'Light strength & stretch',
                'category': 'Movement',
                'target': '10 min gentle mat/bodyweight mobility',
                'minutes': 10,
                'optional': True,
            },
            {
                'id': 'mental',
                'label': 'Reading & mental tasks',
                'category': 'Cognitive',
                'target': '25 min reading, writing, or focused tasks',
                'minutes': 25,
                'optional': False,
            },
            {
                'id': 'social',
                'label': 'Social time',
                'category': 'Social',
                'target': '20 min call or short visit with a break',
                'minutes': 20,
                'optional': True,
            },
        ],
    },
    6: {
        'level': 6,
        'phase': 2,
        'phase_name': PHASES[2]['name'],
        'title': 'Expanding Stamina',
        'summary': 'Build physical and mental stamina slowly while protecting recovery time.',
        'hold_days': 24,
        'effort_ceiling': '3–4 / 10',
        'activities': [
            {
                'id': 'rest',
                'label': 'Recharge rest',
                'category': 'Rest',
                'target': 'Scheduled midday breather',
                'minutes': None,
                'optional': False,
            },
            {
                'id': 'household',
                'label': 'Household work',
                'category': 'Household',
                'target': '30 min cooking, laundry, or home upkeep',
                'minutes': 30,
                'optional': False,
            },
            {
                'id': 'walking',
                'label': 'Steady walk',
                'category': 'Movement',
                'target': '15 min comfortable walk',
                'minutes': 15,
                'optional': False,
            },
            {
                'id': 'stretching',
                'label': 'Restorative strength & stretch',
                'category': 'Movement',
                'target': '12 min gentle strength & flexibility',
                'minutes': 12,
                'optional': True,
            },
            {
                'id': 'mental',
                'label': 'Reading & mental tasks',
                'category': 'Cognitive',
                'target': '35 min reading, planning, or creative focus',
                'minutes': 35,
                'optional': False,
            },
            {
                'id': 'social',
                'label': 'Call or visit',
                'category': 'Social',
                'target': '30 min relaxed conversation or visit',
                'minutes': 30,
                'optional': True,
            },
        ],
    },
    7: {
        'level': 7,
        'phase': 2,
        'phase_name': PHASES[2]['name'],
        'title': 'Active Home & Short Outings',
        'summary': 'Add 20-minute walks and brief local outings without next-day dips.',
        'hold_days': 28,
        'effort_ceiling': '4 / 10',
        'activities': [
            {
                'id': 'rest',
                'label': 'Recharge rest',
                'category': 'Rest',
                'target': 'Brief quiet break between active blocks',
                'minutes': None,
                'optional': False,
            },
            {
                'id': 'household',
                'label': 'Household work',
                'category': 'Household',
                'target': '40 min routine home tasks & meal prep',
                'minutes': 40,
                'optional': False,
            },
            {
                'id': 'walking',
                'label': 'Steady walk',
                'category': 'Movement',
                'target': '20 min walk (split into two if helpful)',
                'minutes': 20,
                'optional': False,
            },
            {
                'id': 'stretching',
                'label': 'Strength & mobility',
                'category': 'Movement',
                'target': '15 min light bodyweight & stretch routine',
                'minutes': 15,
                'optional': True,
            },
            {
                'id': 'mental',
                'label': 'Reading & mental tasks',
                'category': 'Cognitive',
                'target': '45 min study, reading, or computer work',
                'minutes': 45,
                'optional': False,
            },
            {
                'id': 'social',
                'label': 'Short local outing',
                'category': 'Social',
                'target': '35 min coffee, errand, or family time',
                'minutes': 35,
                'optional': True,
            },
        ],
    },
    8: {
        'level': 8,
        'phase': 2,
        'phase_name': PHASES[2]['name'],
        'title': 'Strong Foundation',
        'summary': 'Solidify everyday resilience before transitioning back into fuller life.',
        'hold_days': 28,
        'effort_ceiling': '4–5 / 10',
        'activities': [
            {
                'id': 'rest',
                'label': 'Flexible rest',
                'category': 'Rest',
                'target': 'Short recharge rest after busy blocks',
                'minutes': None,
                'optional': False,
            },
            {
                'id': 'household',
                'label': 'Household work',
                'category': 'Household',
                'target': '50 min daily chores & family routines',
                'minutes': 50,
                'optional': False,
            },
            {
                'id': 'walking',
                'label': 'Walk or light cardio',
                'category': 'Movement',
                'target': '25 min steady walk or gentle cycling',
                'minutes': 25,
                'optional': False,
            },
            {
                'id': 'stretching',
                'label': 'Strength & stretch',
                'category': 'Movement',
                'target': '20 min multi-joint strength & mobility',
                'minutes': 20,
                'optional': True,
            },
            {
                'id': 'mental',
                'label': 'Focused mental work',
                'category': 'Cognitive',
                'target': '60 min reading, admin, or hobby focus',
                'minutes': 60,
                'optional': False,
            },
            {
                'id': 'social',
                'label': 'Social or local outing',
                'category': 'Social',
                'target': '45–60 min social outing or family activity',
                'minutes': 50,
                'optional': True,
            },
        ],
    },
    9: {
        'level': 9,
        'phase': 3,
        'phase_name': PHASES[3]['name'],
        'title': 'Part-Time Rhythm',
        'summary': 'Combine regular errands, hobbies, and movement with flexible recovery breaks.',
        'hold_days': 28,
        'effort_ceiling': '4–5 / 10',
        'activities': [
            {
                'id': 'rest',
                'label': 'Recharge break',
                'category': 'Rest',
                'target': 'Optional breather as needed on fuller days',
                'minutes': None,
                'optional': False,
            },
            {
                'id': 'household',
                'label': 'Home & errands',
                'category': 'Household',
                'target': '60 min normal household work & local errands',
                'minutes': 60,
                'optional': False,
            },
            {
                'id': 'walking',
                'label': 'Cardio movement',
                'category': 'Movement',
                'target': '30 min walk, swim, or light cycle',
                'minutes': 30,
                'optional': False,
            },
            {
                'id': 'stretching',
                'label': 'Strength & flexibility',
                'category': 'Movement',
                'target': '25 min balanced strength & stretch session',
                'minutes': 25,
                'optional': True,
            },
            {
                'id': 'mental',
                'label': 'Cognitive & work blocks',
                'category': 'Cognitive',
                'target': '90 min reading, projects, or part-time work',
                'minutes': 90,
                'optional': False,
            },
            {
                'id': 'social',
                'label': 'Social life',
                'category': 'Social',
                'target': '60–90 min social or family outing',
                'minutes': 75,
                'optional': True,
            },
        ],
    },
    10: {
        'level': 10,
        'phase': 3,
        'phase_name': PHASES[3]['name'],
        'title': 'Growing Independence',
        'summary': 'Handle half-day commitments and fuller movement with confidence.',
        'hold_days': 28,
        'effort_ceiling': '5 / 10',
        'activities': [
            {
                'id': 'rest',
                'label': 'Mindful pause',
                'category': 'Rest',
                'target': 'Listen to your energy and pause when needed',
                'minutes': None,
                'optional': False,
            },
            {
                'id': 'household',
                'label': 'Full home & family tasks',
                'category': 'Household',
                'target': '75 min home, cooking, and shopping routines',
                'minutes': 75,
                'optional': False,
            },
            {
                'id': 'walking',
                'label': 'Active movement',
                'category': 'Movement',
                'target': '35 min brisk walk or enjoyable cardio',
                'minutes': 35,
                'optional': False,
            },
            {
                'id': 'stretching',
                'label': 'Strength & stretch',
                'category': 'Movement',
                'target': '25 min compound strength & mobility',
                'minutes': 25,
                'optional': True,
            },
            {
                'id': 'mental',
                'label': 'Sustained mental focus',
                'category': 'Cognitive',
                'target': '120 min work, study, or creative focus',
                'minutes': 120,
                'optional': False,
            },
            {
                'id': 'social',
                'label': 'Outings & events',
                'category': 'Social',
                'target': 'Half-day outing, meal out, or family event',
                'minutes': 90,
                'optional': True,
            },
        ],
    },
    11: {
        'level': 11,
        'phase': 3,
        'phase_name': PHASES[3]['name'],
        'title': 'Near-Normal Days',
        'summary': 'Maintain balanced energy across work, home, exercise, and social plans.',
        'hold_days': 30,
        'effort_ceiling': '5–6 / 10',
        'activities': [
            {
                'id': 'rest',
                'label': 'Evening wind-down',
                'category': 'Rest',
                'target': 'Consistent sleep routine and gentle downtime',
                'minutes': None,
                'optional': False,
            },
            {
                'id': 'household',
                'label': 'Everyday responsibilities',
                'category': 'Household',
                'target': '90 min full home & family flow',
                'minutes': 90,
                'optional': False,
            },
            {
                'id': 'walking',
                'label': 'Cardio & recreation',
                'category': 'Movement',
                'target': '40 min walk, hike, swim, or sport',
                'minutes': 40,
                'optional': False,
            },
            {
                'id': 'stretching',
                'label': 'Strength & mobility',
                'category': 'Movement',
                'target': '30 min full-body strength & stretching',
                'minutes': 30,
                'optional': True,
            },
            {
                'id': 'mental',
                'label': 'Half-day+ cognitive flow',
                'category': 'Cognitive',
                'target': '180 min work, study, or deep focus',
                'minutes': 180,
                'optional': False,
            },
            {
                'id': 'social',
                'label': 'Full social rhythm',
                'category': 'Social',
                'target': 'Unplanned social visits or longer drives',
                'minutes': 120,
                'optional': True,
            },
        ],
    },
    12: {
        'level': 12,
        'phase': 3,
        'phase_name': PHASES[3]['name'],
        'title': 'Normal Energy & Maintenance',
        'summary': 'Everyday living with lasting resilience and healthy boundaries.',
        'hold_days': 30,
        'effort_ceiling': 'Flexible',
        'activities': [
            {
                'id': 'rest',
                'label': 'Restorative sleep & downtime',
                'category': 'Rest',
                'target': 'Healthy boundaries and regular downtime',
                'minutes': None,
                'optional': False,
            },
            {
                'id': 'household',
                'label': 'Full daily living',
                'category': 'Household',
                'target': 'Normal household and family life',
                'minutes': 90,
                'optional': False,
            },
            {
                'id': 'walking',
                'label': 'Enjoyable movement',
                'category': 'Movement',
                'target': '45+ min walking, hiking, or chosen sport',
                'minutes': 45,
                'optional': False,
            },
            {
                'id': 'stretching',
                'label': 'Strength & flexibility',
                'category': 'Movement',
                'target': '30 min ongoing conditioning & stretch',
                'minutes': 30,
                'optional': True,
            },
            {
                'id': 'mental',
                'label': 'Full cognitive stamina',
                'category': 'Cognitive',
                'target': 'Normal work, reading, and mental focus',
                'minutes': 240,
                'optional': False,
            },
            {
                'id': 'social',
                'label': 'Social & travel freedom',
                'category': 'Social',
                'target': 'Full social calendar and longer trips',
                'minutes': 150,
                'optional': True,
            },
        ],
    },
}

STABILIZATION_ACTIVITIES = [
    {
        'id': 'rest',
        'label': 'Quiet rest & low stimulation',
        'category': 'Rest',
        'target': 'Prioritize quiet horizontal rest without screens',
        'minutes': None,
        'optional': False,
    },
    {
        'id': 'nourish',
        'label': 'Meals & hydration',
        'category': 'Rest',
        'target': 'Gentle regular meals and steady fluids',
        'minutes': None,
        'optional': False,
    },
    {
        'id': 'reset',
        'label': 'Calming nervous-system reset',
        'category': 'Movement',
        'target': '5 min slow breathing or legs up the wall',
        'minutes': 5,
        'optional': True,
    },
    {
        'id': 'household',
        'label': 'Bare-minimum essentials only',
        'category': 'Household',
        'target': 'Only essential self-care; pause extra chores and walks',
        'minutes': None,
        'optional': False,
    },
]

FEELINGS = {
    'steady': 'Steady / Good',
    'worn': 'A bit worn',
    'worse': 'Worse',
    'crash': 'Crash',
}

ACTIVITY_RATINGS = {
    'skipped': 'Skipped',
    'too_much': 'Too much',
    'just_right': 'Just right',
    'could_do_more': 'Could do more',
}

FACTORS = {
    'sleep': 'Poor sleep',
    'stress': 'High stress',
    'food': 'Light meals',
    'cycle': 'Hormonal cycle',
    'illness': 'Cold / virus',
}

EFFORT_LEVELS = ('light', 'medium', 'heavy')

BEYOND_PLAN_PRESETS = (
    'Long drive',
    'Medical appointment',
    'Family event',
    'Errands / shopping',
    'Visitors',
)

ASSESSMENT_QUESTIONS = [
    {
        'id': 'upright',
        'prompt': 'On a typical day right now, how much time can you spend up and out of bed?',
        'options': [
            {'value': 0, 'label': 'Mostly resting or in bed (only up briefly)'},
            {'value': 1, 'label': 'A few hours up around the house with lots of rest'},
            {'value': 2, 'label': 'Half the day up, resting between blocks'},
            {'value': 3, 'label': 'Up most of the day with an afternoon rest'},
            {'value': 4, 'label': 'Up all day with normal short breaks'},
        ],
    },
    {
        'id': 'walk_10',
        'prompt': 'If you did a gentle 10-minute flat walk today, how would you likely feel tomorrow or the day after?',
        'options': [
            {'value': 0, 'label': 'I cannot attempt a 10-minute walk right now'},
            {'value': 1, 'label': 'I would likely crash or flare up 1–3 days later'},
            {'value': 2, 'label': 'I could do it once, but not every day'},
            {'value': 3, 'label': 'I could walk 10 minutes daily if I do little else'},
            {'value': 4, 'label': 'I can walk 10+ minutes daily alongside other tasks'},
        ],
    },
    {
        'id': 'household',
        'prompt': 'How do everyday household tasks (showering, making a meal, light tidying) affect you?',
        'options': [
            {'value': 0, 'label': 'Even basic self-care takes almost everything I have'},
            {'value': 1, 'label': 'I can manage one very small task before needing to lie down'},
            {'value': 2, 'label': 'I can manage 15–20 minutes of light chores if paced'},
            {'value': 3, 'label': 'I handle most daily home tasks with a planned break'},
            {'value': 4, 'label': 'I manage normal home work and short errands reliably'},
        ],
    },
    {
        'id': 'mental',
        'prompt': 'How long can you read, follow a conversation, or focus on a screen before brain fog sets in?',
        'options': [
            {'value': 0, 'label': 'Under 5 minutes — screens and reading overwhelm quickly'},
            {'value': 1, 'label': 'About 10–15 minutes at a time'},
            {'value': 2, 'label': 'About 25–30 minutes calmly'},
            {'value': 3, 'label': 'Around 45–60 minutes with breaks'},
            {'value': 4, 'label': '90+ minutes comfortably'},
        ],
    },
    {
        'id': 'stability',
        'prompt': 'How steady have your days felt over the past two weeks?',
        'options': [
            {'value': 0, 'label': 'Crashing often — stuck in push-and-crash swings'},
            {'value': 1, 'label': 'Frequent ups and downs with unpredictable lows'},
            {'value': 2, 'label': 'Mostly steady with occasional small dips'},
            {'value': 3, 'label': 'Steady for the past two weeks or longer'},
            {'value': 4, 'label': 'Very steady and clearly ready for more'},
        ],
    },
]


def level_activities(level, *, cushion_pct=0, disabled_categories=()):
    """Return the pre-populated daily activity plan for a given level."""
    spec = LEVELS[level]
    disabled = set(disabled_categories)
    items = []
    for item in spec['activities']:
        if item['optional'] and item['category'] in disabled:
            continue
        entry = dict(item)
        if cushion_pct and entry['minutes'] is not None:
            scaled = max(1, round(entry['minutes'] * (100 - cushion_pct) / 100))
            entry['minutes'] = scaled
            entry['target'] = f"{scaled} min (gentler {cushion_pct}% cushion) — {entry['target']}"
        items.append(entry)
    return items


def evaluate_assessment(answers):
    """Recommend a conservative starting level (1..12) from the 5 onboarding answers."""
    if not isinstance(answers, dict):
        raise ValueError('Answer all five assessment questions.')
    required = [question['id'] for question in ASSESSMENT_QUESTIONS]
    scores = {}
    for key in required:
        val = answers.get(key)
        if type(val) is not int or not 0 <= val <= 4:
            raise ValueError('Choose one option for each starting question.')
        scores[key] = val

    capacities = [scores['upright'], scores['walk_10'], scores['household'], scores['mental']]
    limiting = min(capacities)
    average = sum(capacities) / len(capacities)
    weighted = 0.55 * limiting + 0.45 * average

    # Map weighted 0..4 capacity score conservatively onto levels 1..10.
    raw = round(1 + weighted * 2.25)

    # Specific walking / upright guardrails so a 10-min walk crash never lands in Phase 2+.
    if scores['walk_10'] == 0 or scores['upright'] == 0:
        raw = min(raw, 2)
    elif scores['walk_10'] == 1:
        raw = min(raw, 3)
    elif scores['walk_10'] == 2:
        raw = min(raw, 5)
    elif scores['walk_10'] == 3:
        raw = min(raw, 7)

    # Stability discount: unstable weeks start lower to build a foundation first.
    stability = scores['stability']
    if stability == 0:
        raw -= 2
    elif stability == 1:
        raw -= 1
    elif stability == 4 and limiting >= 3:
        raw += 1

    recommended = max(1, min(10, raw))
    spec = LEVELS[recommended]
    phase = PHASES[spec['phase']]

    if stability <= 1:
        stability_note = (
            'Because your recent days have felt up and down, this starts gently so you can '
            'settle into a steady rhythm without triggering a crash.'
        )
    elif scores['walk_10'] <= 1:
        stability_note = (
            'Starting in Phase 1 keeps movement brief and restorative while your body builds '
            'the stability needed for daily short walks.'
        )
    else:
        stability_note = (
            'This starting level matches your current capacity with a safety margin so you can '
            'hold steady days before stepping up.'
        )

    return {
        'recommended_level': recommended,
        'phase': spec['phase'],
        'phase_name': phase['name'],
        'title': spec['title'],
        'summary': stability_note,
        'level_preview': {
            **spec,
            'activities': level_activities(recommended),
        },
    }
