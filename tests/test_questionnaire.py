"""Tests for storyteller.questionnaire — adaptive question generation."""

from storyteller.questionnaire import (
    AGE_GROUPS,
    BASE_QUESTIONS,
    TAG_ADAPTIVE_QUESTIONS,
    get_adaptive_questions,
)


def test_age_groups_has_five_entries():
    assert len(AGE_GROUPS) == 5


def test_base_questions_are_nonempty():
    assert len(BASE_QUESTIONS) >= 3
    assert all(q.endswith("?") for q in BASE_QUESTIONS)


def test_no_tags_returns_only_base_questions():
    questions = get_adaptive_questions([])
    assert questions == BASE_QUESTIONS


def test_single_known_tag_appends_extra_questions():
    questions = get_adaptive_questions(["childhood"])
    assert len(questions) == len(BASE_QUESTIONS) + len(TAG_ADAPTIVE_QUESTIONS["childhood"])
    for q in TAG_ADAPTIVE_QUESTIONS["childhood"]:
        assert q in questions


def test_multiple_tags_accumulate():
    questions = get_adaptive_questions(["war", "loss"])
    expected_count = (
        len(BASE_QUESTIONS)
        + len(TAG_ADAPTIVE_QUESTIONS["war"])
        + len(TAG_ADAPTIVE_QUESTIONS["loss"])
    )
    assert len(questions) == expected_count


def test_unknown_tag_adds_nothing():
    questions = get_adaptive_questions(["nonexistent-tag"])
    assert questions == BASE_QUESTIONS


def test_base_questions_always_come_first():
    questions = get_adaptive_questions(["career"])
    for i, bq in enumerate(BASE_QUESTIONS):
        assert questions[i] == bq


def test_every_tag_category_has_questions():
    for tag, qs in TAG_ADAPTIVE_QUESTIONS.items():
        assert len(qs) >= 1, f"Tag '{tag}' has no adaptive questions"
