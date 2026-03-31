"""Tests for storyteller.db — CRUD operations on persons, stories, tags, and questionnaire responses."""

import storyteller.db as db


class TestPersonOperations:
    def test_create_and_get_person(self):
        pid = db.create_person("Alice", "Adult (30-49)")
        person = db.get_person(pid)
        assert person is not None
        assert person["name"] == "Alice"
        assert person["age_group"] == "Adult (30-49)"

    def test_get_all_persons_sorted_by_name(self):
        db.create_person("Zara", "Senior (65+)")
        db.create_person("Alice", "Teenager (13-19)")
        persons = db.get_all_persons()
        names = [p["name"] for p in persons]
        assert names == ["Alice", "Zara"]

    def test_get_nonexistent_person_returns_none(self):
        assert db.get_person(9999) is None

    def test_update_person_name(self):
        pid = db.create_person("Bob", "Young Adult (20-29)")
        db.update_person(pid, "Robert")
        person = db.get_person(pid)
        assert person["name"] == "Robert"


class TestStoryOperations:
    def test_create_story_with_tags(self):
        pid = db.create_person("Carol", "Adult (30-49)")
        sid = db.create_story(pid, "My Journey", "Once upon a time...", ["travel", "adventure"])
        story = db.get_story(sid)
        assert story is not None
        assert story["title"] == "My Journey"
        assert story["content"] == "Once upon a time..."
        assert set(story["tags"]) == {"travel", "adventure"}

    def test_create_story_creates_custom_tags(self):
        pid = db.create_person("Dan", "Senior (65+)")
        db.create_story(pid, "Custom", "text", ["brand-new-tag"])
        tags = db.get_all_tags()
        assert "brand-new-tag" in tags

    def test_create_story_ignores_blank_tags(self):
        pid = db.create_person("Eve", "Teenager (13-19)")
        sid = db.create_story(pid, "Title", "body", ["family", "", "  "])
        tags = db.get_tags_for_story(sid)
        assert tags == ["family"]

    def test_get_stories_for_person(self):
        pid = db.create_person("Frank", "Adult (30-49)")
        db.create_story(pid, "Story A", "aaa", ["childhood"])
        db.create_story(pid, "Story B", "bbb", ["career"])
        stories = db.get_stories_for_person(pid)
        assert len(stories) == 2
        titles = {s["title"] for s in stories}
        assert titles == {"Story A", "Story B"}

    def test_get_all_stories_includes_person_name(self):
        pid = db.create_person("Grace", "Young Adult (20-29)")
        db.create_story(pid, "Title", "content", [])
        stories = db.get_all_stories()
        assert any(s["person_name"] == "Grace" for s in stories)

    def test_update_story(self):
        pid = db.create_person("Hank", "Adult (30-49)")
        sid = db.create_story(pid, "Old Title", "old body", [])
        db.update_story(sid, "New Title", "new body")
        story = db.get_story(sid)
        assert story["title"] == "New Title"
        assert story["content"] == "new body"

    def test_get_nonexistent_story_returns_none(self):
        assert db.get_story(9999) is None

    def test_get_or_create_story_creates_when_missing(self):
        pid = db.create_person("Iris", "Mature Adult (50-64)")
        sid = db.get_or_create_story(pid, "Iris's Story")
        assert sid is not None
        story = db.get_story(sid)
        assert story["title"] == "Iris's Story"

    def test_get_or_create_story_returns_existing(self):
        pid = db.create_person("Jack", "Senior (65+)")
        sid1 = db.get_or_create_story(pid, "Jack's Story")
        sid2 = db.get_or_create_story(pid, "Different Title")
        assert sid1 == sid2


class TestTagOperations:
    def test_preset_tags_created_on_init(self):
        tags = db.get_all_tags()
        for preset in ["childhood", "family", "friendship", "love", "loss"]:
            assert preset in tags

    def test_get_stories_by_tag(self):
        pid = db.create_person("Kate", "Adult (30-49)")
        db.create_story(pid, "Story 1", "content", ["humor"])
        db.create_story(pid, "Story 2", "content", ["humor", "family"])
        db.create_story(pid, "Story 3", "content", ["family"])

        humor_stories = db.get_stories_by_tag("humor")
        assert len(humor_stories) == 2
        assert all("humor" in s["tags"] for s in humor_stories)

    def test_get_stories_by_nonexistent_tag(self):
        stories = db.get_stories_by_tag("nonexistent-tag-xyz")
        assert stories == []


class TestQuestionnaireResponses:
    def test_save_and_get_responses(self):
        pid = db.create_person("Leo", "Young Adult (20-29)")
        sid = db.create_story(pid, "Title", "content", [])
        db.save_questionnaire_responses(sid, [
            {"question": "Q1?", "answer": "A1"},
            {"question": "Q2?", "answer": "A2"},
        ])
        responses = db.get_questionnaire_responses(sid)
        assert len(responses) == 2
        assert responses[0]["question"] == "Q1?"
        assert responses[0]["answer"] == "A1"

    def test_save_response_without_answer_defaults_to_empty(self):
        pid = db.create_person("Mia", "Teenager (13-19)")
        sid = db.create_story(pid, "Title", "content", [])
        db.save_questionnaire_responses(sid, [{"question": "Q?"}])
        responses = db.get_questionnaire_responses(sid)
        assert responses[0]["answer"] == ""

    def test_save_or_update_response_creates_new(self):
        pid = db.create_person("Nate", "Adult (30-49)")
        sid = db.create_story(pid, "Title", "content", [])
        db.save_or_update_response(sid, "Favorite color?", "Blue")
        responses = db.get_questionnaire_responses(sid)
        assert len(responses) == 1
        assert responses[0]["answer"] == "Blue"

    def test_save_or_update_response_updates_existing(self):
        pid = db.create_person("Olivia", "Senior (65+)")
        sid = db.create_story(pid, "Title", "content", [])
        db.save_or_update_response(sid, "Favorite color?", "Blue")
        db.save_or_update_response(sid, "Favorite color?", "Green")
        responses = db.get_questionnaire_responses(sid)
        assert len(responses) == 1
        assert responses[0]["answer"] == "Green"


# ---------------------------------------------------------------------------
# New: multi-session conversation CRUD
# ---------------------------------------------------------------------------

def _make_story() -> tuple[int, int]:
    """Helper: returns (person_id, story_id)."""
    pid = db.create_person("TestUser", "Adult (30-49)")
    sid = db.create_story(pid, "My Story", "", [])
    return pid, sid


class TestConversationCRUD:
    def test_create_and_get_conversation_by_id(self):
        _, sid = _make_story()
        cid = db.create_conversation(sid, 0)
        conv = db.get_conversation_by_id(cid)
        assert conv is not None
        assert conv["story_id"] == sid
        assert conv["chapter_index"] == 0
        assert conv["messages"] == []
        assert conv["extracted_answers"] == {}

    def test_create_conversation_with_messages(self):
        _, sid = _make_story()
        msgs = [{"role": "assistant", "content": "Hello!", "timestamp": ""}]
        cid = db.create_conversation(sid, 1, messages=msgs, extracted_answers={"q1": "a1"})
        conv = db.get_conversation_by_id(cid)
        assert conv["messages"] == msgs
        assert conv["extracted_answers"] == {"q1": "a1"}

    def test_get_conversation_by_id_nonexistent_returns_none(self):
        assert db.get_conversation_by_id(9999) is None

    def test_update_conversation(self):
        _, sid = _make_story()
        cid = db.create_conversation(sid, 0)
        new_msgs = [{"role": "user", "content": "Hi", "timestamp": ""}]
        db.update_conversation(cid, new_msgs, {"q": "answer"}, status="completed")
        conv = db.get_conversation_by_id(cid)
        assert conv["messages"] == new_msgs
        assert conv["extracted_answers"] == {"q": "answer"}
        assert conv["status"] == "completed"

    def test_rename_conversation(self):
        _, sid = _make_story()
        cid = db.create_conversation(sid, 0)
        db.rename_conversation(cid, "My Session Title")
        conv = db.get_conversation_by_id(cid)
        assert conv["title"] == "My Session Title"

    def test_delete_conversation(self):
        _, sid = _make_story()
        cid = db.create_conversation(sid, 0)
        db.delete_conversation(cid)
        assert db.get_conversation_by_id(cid) is None

    def test_get_chapter_conversations_ordered_oldest_first(self):
        _, sid = _make_story()
        cid1 = db.create_conversation(sid, 2)
        cid2 = db.create_conversation(sid, 2)
        cid3 = db.create_conversation(sid, 2)
        sessions = db.get_chapter_conversations(sid, 2)
        assert [s["id"] for s in sessions] == [cid1, cid2, cid3]

    def test_get_chapter_conversations_empty_for_unknown_chapter(self):
        _, sid = _make_story()
        assert db.get_chapter_conversations(sid, 99) == []

    def test_get_chapter_conversations_isolates_by_chapter(self):
        _, sid = _make_story()
        db.create_conversation(sid, 0)
        db.create_conversation(sid, 1)
        ch0 = db.get_chapter_conversations(sid, 0)
        ch1 = db.get_chapter_conversations(sid, 1)
        assert len(ch0) == 1
        assert len(ch1) == 1

    def test_multi_session_accumulates(self):
        _, sid = _make_story()
        db.create_conversation(sid, 0)
        db.create_conversation(sid, 0)
        sessions = db.get_chapter_conversations(sid, 0)
        assert len(sessions) == 2

    def test_create_conversation_with_custom_chapter_id(self):
        _, sid = _make_story()
        chapter = db.create_custom_chapter(sid, "My Custom Chapter")
        cid = db.create_conversation(sid, -1, custom_chapter_id=chapter["id"])
        conv = db.get_conversation_by_id(cid)
        assert conv["custom_chapter_id"] == chapter["id"]

    def test_create_conversation_without_custom_chapter_id_is_null(self):
        _, sid = _make_story()
        cid = db.create_conversation(sid, 0)
        conv = db.get_conversation_by_id(cid)
        assert conv["custom_chapter_id"] is None


class TestDeleteStoryCascades:
    def test_delete_story_removes_conversations(self):
        _, sid = _make_story()
        db.create_conversation(sid, 0)
        db.create_conversation(sid, 1)
        db.delete_story(sid)
        assert db.get_story(sid) is None
        # All conversations for the story are gone
        assert db.get_all_conversations(sid) == []

    def test_delete_story_removes_questionnaire_responses(self):
        _, sid = _make_story()
        db.save_questionnaire_responses(sid, [{"question": "Q?", "answer": "A"}])
        db.delete_story(sid)
        assert db.get_questionnaire_responses(sid) == []

    def test_delete_story_removes_custom_chapters(self):
        _, sid = _make_story()
        db.create_custom_chapter(sid, "My Custom Chapter")
        db.delete_story(sid)
        assert db.get_custom_chapters(sid) == []

    def test_delete_story_does_not_affect_other_stories(self):
        pid = db.create_person("Shared Person", "Adult (30-49)")
        sid1 = db.create_story(pid, "Story 1", "", [])
        sid2 = db.create_story(pid, "Story 2", "", [])
        db.create_conversation(sid1, 0)
        db.delete_story(sid1)
        assert db.get_story(sid2) is not None


# ---------------------------------------------------------------------------
# New: custom chapter CRUD
# ---------------------------------------------------------------------------

class TestCustomChapterCRUD:
    def test_create_and_get_custom_chapters(self):
        _, sid = _make_story()
        chapter = db.create_custom_chapter(sid, "My Custom Chapter")
        assert chapter["title"] == "My Custom Chapter"
        assert chapter["story_id"] == sid
        chapters = db.get_custom_chapters(sid)
        assert len(chapters) == 1
        assert chapters[0]["title"] == "My Custom Chapter"

    def test_create_multiple_chapters_sorted_by_sort_order(self):
        _, sid = _make_story()
        db.create_custom_chapter(sid, "Alpha")
        db.create_custom_chapter(sid, "Beta")
        db.create_custom_chapter(sid, "Gamma")
        chapters = db.get_custom_chapters(sid)
        titles = [c["title"] for c in chapters]
        assert titles == ["Alpha", "Beta", "Gamma"]
        orders = [c["sort_order"] for c in chapters]
        assert orders == sorted(orders)

    def test_get_custom_chapters_empty_for_story_with_none(self):
        _, sid = _make_story()
        assert db.get_custom_chapters(sid) == []

    def test_update_custom_chapter_title(self):
        _, sid = _make_story()
        chapter = db.create_custom_chapter(sid, "Original")
        db.update_custom_chapter(chapter["id"], "Updated")
        chapters = db.get_custom_chapters(sid)
        assert chapters[0]["title"] == "Updated"

    def test_delete_custom_chapter_removes_it(self):
        _, sid = _make_story()
        chapter = db.create_custom_chapter(sid, "To Delete")
        db.delete_custom_chapter(chapter["id"])
        assert db.get_custom_chapters(sid) == []

    def test_delete_custom_chapter_cascades_to_conversations(self):
        _, sid = _make_story()
        chapter = db.create_custom_chapter(sid, "Chapter With Conversations")
        cid = db.create_conversation(sid, -1, custom_chapter_id=chapter["id"])
        db.delete_custom_chapter(chapter["id"])
        # Conversation should be deleted
        assert db.get_conversation_by_id(cid) is None

    def test_delete_custom_chapter_does_not_delete_builtin_conversations(self):
        """Deleting a custom chapter must not affect built-in chapter conversations."""
        _, sid = _make_story()
        builtin_cid = db.create_conversation(sid, 0)  # chapter_index=0, no custom_chapter_id
        chapter = db.create_custom_chapter(sid, "Custom")
        db.delete_custom_chapter(chapter["id"])
        # Built-in conversation must survive
        assert db.get_conversation_by_id(builtin_cid) is not None

    def test_delete_custom_chapter_does_not_delete_other_custom_chapters_conversations(self):
        """Deleting one custom chapter must not touch another custom chapter's conversations."""
        _, sid = _make_story()
        ch1 = db.create_custom_chapter(sid, "Chapter 1")
        ch2 = db.create_custom_chapter(sid, "Chapter 2")
        cid1 = db.create_conversation(sid, -1, custom_chapter_id=ch1["id"])
        cid2 = db.create_conversation(sid, -1, custom_chapter_id=ch2["id"])
        db.delete_custom_chapter(ch1["id"])
        assert db.get_conversation_by_id(cid1) is None
        assert db.get_conversation_by_id(cid2) is not None

