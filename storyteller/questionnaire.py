"""Adaptive questionnaire logic for story follow-ups."""

AGE_GROUPS = [
    "Teenager (13-19)",
    "Young Adult (20-29)",
    "Adult (30-49)",
    "Mature Adult (50-64)",
    "Senior (65+)",
]

BASE_QUESTIONS = [
    "What period of your life does this story come from?",
    "Who are the key people involved in this story?",
    "Where did this take place?",
    "How did this experience change you?",
    "What would you want someone to learn from this story?",
]

TAG_ADAPTIVE_QUESTIONS = {
    "childhood": [
        "How old were you when this happened?",
        "What is your fondest memory from that time?",
    ],
    "family": [
        "Which family members were most important in this story?",
        "How did this shape your family relationships?",
    ],
    "hardships": [
        "What helped you get through this difficult time?",
        "What strength did you discover in yourself?",
    ],
    "war": [
        "How did the conflict affect your daily life?",
        "What moments of humanity did you witness during this time?",
    ],
    "career": [
        "What motivated you to pursue this path?",
        "What was your biggest professional challenge?",
    ],
    "love": [
        "How did you meet this person?",
        "What is the most important thing love has taught you?",
    ],
    "loss": [
        "How do you keep their memory alive?",
        "What helped you cope with the loss?",
    ],
    "travel": [
        "What surprised you most about this place?",
        "How did this journey change your perspective?",
    ],
    "achievement": [
        "What obstacles did you overcome to reach this goal?",
        "Who supported you along the way?",
    ],
    "migration": [
        "What did you leave behind?",
        "How did you build a new sense of home?",
    ],
    "education": [
        "Who was the most influential teacher or mentor?",
        "What lesson extends beyond the classroom?",
    ],
    "health": [
        "How did this health experience change your outlook on life?",
        "What support system helped you through it?",
    ],
    "turning-point": [
        "What made you realize this was a turning point?",
        "What would have happened if you'd made a different choice?",
    ],
}


def get_adaptive_questions(selected_tags: list[str]) -> list[str]:
    """Build a question list that adapts based on selected tags."""
    questions = list(BASE_QUESTIONS)
    for tag in selected_tags:
        extra = TAG_ADAPTIVE_QUESTIONS.get(tag, [])
        questions.extend(extra)
    return questions
