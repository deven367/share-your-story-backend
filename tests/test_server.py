"""Tests for the Flask API endpoints defined in server.py."""

import json
from unittest.mock import patch

import storyteller.db as db


class TestPersonEndpoints:
    def test_create_person(self, client):
        resp = client.post("/api/persons", json={"name": "Alice", "age_group": "Adult (30-49)"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert "person_id" in data
        assert "story_id" in data

    def test_create_person_missing_name(self, client):
        resp = client.post("/api/persons", json={"name": "", "age_group": "Adult (30-49)"})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_get_persons(self, client):
        client.post("/api/persons", json={"name": "Bob", "age_group": "Senior (65+)"})
        resp = client.get("/api/persons")
        assert resp.status_code == 200
        persons = resp.get_json()
        assert any(p["name"] == "Bob" for p in persons)

    def test_update_person(self, client):
        create_resp = client.post("/api/persons", json={"name": "Carl", "age_group": "Teenager (13-19)"})
        person_id = create_resp.get_json()["person_id"]
        resp = client.put(f"/api/persons/{person_id}", json={"name": "Carlos"})
        assert resp.status_code == 200

        persons = client.get("/api/persons").get_json()
        assert any(p["name"] == "Carlos" for p in persons)


class TestStoryEndpoints:
    def _create_person(self, client):
        resp = client.post("/api/persons", json={"name": "Tester", "age_group": "Adult (30-49)"})
        data = resp.get_json()
        return data["person_id"], data["story_id"]

    def test_get_all_stories(self, client):
        self._create_person(client)
        resp = client.get("/api/stories")
        assert resp.status_code == 200
        stories = resp.get_json()
        assert isinstance(stories, list)
        assert len(stories) >= 1

    def test_get_single_story(self, client):
        _, story_id = self._create_person(client)
        resp = client.get(f"/api/stories/{story_id}")
        assert resp.status_code == 200
        story = resp.get_json()
        assert story["id"] == story_id

    def test_get_nonexistent_story(self, client):
        resp = client.get("/api/stories/99999")
        assert resp.status_code == 404

    def test_update_story(self, client):
        _, story_id = self._create_person(client)
        resp = client.put(f"/api/stories/{story_id}", json={"title": "Updated", "content": "New content"})
        assert resp.status_code == 200
        story = client.get(f"/api/stories/{story_id}").get_json()
        assert story["title"] == "Updated"
        assert story["content"] == "New content"

    def test_update_story_missing_title(self, client):
        _, story_id = self._create_person(client)
        resp = client.put(f"/api/stories/{story_id}", json={"title": "", "content": "body"})
        assert resp.status_code == 400

    def test_delete_story(self, client):
        _, story_id = self._create_person(client)
        resp = client.delete(f"/api/stories/{story_id}")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "ok"
        assert client.get(f"/api/stories/{story_id}").status_code == 404

    def test_delete_story_cascades_to_conversations(self, client):
        _, story_id = self._create_person(client)
        db.create_conversation(story_id, 0)
        client.delete(f"/api/stories/{story_id}")
        assert db.get_all_conversations(story_id) == []

    def test_delete_story_cascades_to_custom_chapters(self, client):
        _, story_id = self._create_person(client)
        db.create_custom_chapter(story_id, "My Custom Chapter")
        client.delete(f"/api/stories/{story_id}")
        assert db.get_custom_chapters(story_id) == []


class TestResponseEndpoints:
    def _create_person_and_story(self, client):
        resp = client.post("/api/persons", json={"name": "Respondent", "age_group": "Adult (30-49)"})
        return resp.get_json()["story_id"]

    def test_save_and_get_responses(self, client):
        story_id = self._create_person_and_story(client)
        client.post("/api/responses", json={
            "story_id": story_id,
            "question": "What happened?",
            "answer": "Everything.",
        })
        resp = client.get(f"/api/responses/{story_id}")
        assert resp.status_code == 200
        responses = resp.get_json()
        assert len(responses) == 1
        assert responses[0]["question"] == "What happened?"

    def test_save_response_missing_question(self, client):
        resp = client.post("/api/responses", json={"story_id": 1, "question": "", "answer": "x"})
        assert resp.status_code == 400

    def test_save_response_missing_story_id(self, client):
        resp = client.post("/api/responses", json={"question": "Q?", "answer": "A"})
        assert resp.status_code == 400

    def test_upsert_response(self, client):
        story_id = self._create_person_and_story(client)
        client.post("/api/responses", json={
            "story_id": story_id,
            "question": "Color?",
            "answer": "Blue",
        })
        client.post("/api/responses", json={
            "story_id": story_id,
            "question": "Color?",
            "answer": "Red",
        })
        responses = client.get(f"/api/responses/{story_id}").get_json()
        color_answers = [r for r in responses if r["question"] == "Color?"]
        assert len(color_answers) == 1
        assert color_answers[0]["answer"] == "Red"


# ---------------------------------------------------------------------------
# New: conversation session endpoints
# ---------------------------------------------------------------------------

class TestConversationEndpoints:
    def _setup(self, client):
        resp = client.post("/api/persons", json={"name": "ConvTester", "age_group": "Adult (30-49)"})
        data = resp.get_json()
        return data["story_id"]

    def test_get_conversation_for_empty_chapter(self, client):
        story_id = self._setup(client)
        resp = client.get(f"/api/conversations/{story_id}/0")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "not_started"
        assert data["sessions"] == []
        assert data["latest"]["messages"] == []
        assert data["latest"]["conversation_id"] is None

    def test_get_conversation_with_sessions(self, client):
        story_id = self._setup(client)
        cid = db.create_conversation(story_id, 0, messages=[{"role": "assistant", "content": "Hi"}])
        resp = client.get(f"/api/conversations/{story_id}/0")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "in_progress"
        assert len(data["sessions"]) == 1
        assert data["latest"]["conversation_id"] == cid

    def test_get_conversation_latest_is_most_recent(self, client):
        story_id = self._setup(client)
        db.create_conversation(story_id, 0)
        cid2 = db.create_conversation(story_id, 0)
        data = client.get(f"/api/conversations/{story_id}/0").get_json()
        assert data["latest"]["conversation_id"] == cid2

    def test_rename_conversation(self, client):
        story_id = self._setup(client)
        cid = db.create_conversation(story_id, 0)
        resp = client.put(f"/api/conversations/{cid}", json={"title": "My Session"})
        assert resp.status_code == 200
        conv = db.get_conversation_by_id(cid)
        assert conv["title"] == "My Session"

    def test_rename_conversation_missing_title(self, client):
        story_id = self._setup(client)
        cid = db.create_conversation(story_id, 0)
        resp = client.put(f"/api/conversations/{cid}", json={"title": ""})
        assert resp.status_code == 400

    def test_delete_conversation(self, client):
        story_id = self._setup(client)
        cid = db.create_conversation(story_id, 0)
        resp = client.delete(f"/api/conversations/{cid}")
        assert resp.status_code == 200
        assert db.get_conversation_by_id(cid) is None

    def test_get_all_conversations_summary(self, client):
        story_id = self._setup(client)
        db.create_conversation(story_id, 0, messages=[{"role": "assistant", "content": "Hi"}])
        db.create_conversation(story_id, 1)
        resp = client.get(f"/api/conversations/{story_id}")
        assert resp.status_code == 200
        result = resp.get_json()
        chapter_indices = [item["chapter_index"] for item in result]
        assert 0 in chapter_indices
        assert 1 in chapter_indices


# ---------------------------------------------------------------------------
# New: custom chapter endpoints
# ---------------------------------------------------------------------------

class TestCustomChapterEndpoints:
    def _setup(self, client):
        resp = client.post("/api/persons", json={"name": "ChapterTester", "age_group": "Adult (30-49)"})
        return resp.get_json()["story_id"]

    def test_get_custom_chapters_empty(self, client):
        story_id = self._setup(client)
        resp = client.get(f"/api/stories/{story_id}/custom-chapters")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_create_custom_chapter(self, client):
        story_id = self._setup(client)
        resp = client.post(f"/api/stories/{story_id}/custom-chapters", json={"title": "My Chapter"})
        assert resp.status_code == 200
        chapter = resp.get_json()
        assert chapter["title"] == "My Chapter"
        assert chapter["story_id"] == story_id

    def test_create_custom_chapter_default_title(self, client):
        story_id = self._setup(client)
        resp = client.post(f"/api/stories/{story_id}/custom-chapters", json={})
        assert resp.status_code == 200
        assert resp.get_json()["title"] == "New Chapter"

    def test_get_custom_chapters_lists_all(self, client):
        story_id = self._setup(client)
        client.post(f"/api/stories/{story_id}/custom-chapters", json={"title": "Alpha"})
        client.post(f"/api/stories/{story_id}/custom-chapters", json={"title": "Beta"})
        resp = client.get(f"/api/stories/{story_id}/custom-chapters")
        titles = [c["title"] for c in resp.get_json()]
        assert titles == ["Alpha", "Beta"]

    def test_update_custom_chapter(self, client):
        story_id = self._setup(client)
        chapter = client.post(f"/api/stories/{story_id}/custom-chapters", json={"title": "Old"}).get_json()
        resp = client.put(f"/api/custom-chapters/{chapter['id']}", json={"title": "New"})
        assert resp.status_code == 200
        chapters = client.get(f"/api/stories/{story_id}/custom-chapters").get_json()
        assert chapters[0]["title"] == "New"

    def test_update_custom_chapter_missing_title(self, client):
        story_id = self._setup(client)
        chapter = client.post(f"/api/stories/{story_id}/custom-chapters", json={"title": "A"}).get_json()
        resp = client.put(f"/api/custom-chapters/{chapter['id']}", json={"title": ""})
        assert resp.status_code == 400

    def test_delete_custom_chapter(self, client):
        story_id = self._setup(client)
        chapter = client.post(f"/api/stories/{story_id}/custom-chapters", json={"title": "ToDelete"}).get_json()
        resp = client.delete(f"/api/custom-chapters/{chapter['id']}")
        assert resp.status_code == 200
        chapters = client.get(f"/api/stories/{story_id}/custom-chapters").get_json()
        assert chapters == []

    def test_delete_custom_chapter_cascades_to_conversations(self, client):
        story_id = self._setup(client)
        chapter = client.post(f"/api/stories/{story_id}/custom-chapters", json={"title": "C"}).get_json()
        cid = db.create_conversation(story_id, -1, custom_chapter_id=chapter["id"])
        client.delete(f"/api/custom-chapters/{chapter['id']}")
        assert db.get_conversation_by_id(cid) is None


# ---------------------------------------------------------------------------
# New: TTS and transcribe endpoints
# ---------------------------------------------------------------------------

class TestTTSEndpoint:
    def test_tts_returns_audio(self, client):
        with patch("storyteller.tts.synthesize", return_value=b"\xff\xfb\x90mp3-data") as mock_synth:
            resp = client.post("/api/tts", json={"text": "Hello world"})
        assert resp.status_code == 200
        assert resp.content_type == "audio/mpeg"
        assert resp.data == b"\xff\xfb\x90mp3-data"
        mock_synth.assert_called_once_with("Hello world", voice_id=None)

    def test_tts_passes_voice_id(self, client):
        with patch("storyteller.tts.synthesize", return_value=b"audio") as mock_synth:
            client.post("/api/tts", json={"text": "Hi", "voice_id": "custom-voice"})
        mock_synth.assert_called_once_with("Hi", voice_id="custom-voice")

    def test_tts_missing_text_returns_400(self, client):
        resp = client.post("/api/tts", json={})
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_tts_empty_text_returns_400(self, client):
        resp = client.post("/api/tts", json={"text": "   "})
        assert resp.status_code == 400

    def test_tts_non_json_content_type_returns_415(self, client):
        resp = client.post("/api/tts", data="not json", content_type="text/plain")
        assert resp.status_code == 415

    def test_tts_empty_body_returns_400(self, client):
        resp = client.post("/api/tts", json={})
        assert resp.status_code == 400

    def test_tts_error_returns_500(self, client):
        from storyteller.tts import TTSError
        with patch("storyteller.tts.synthesize", side_effect=TTSError("API down")):
            resp = client.post("/api/tts", json={"text": "Hello"})
        assert resp.status_code == 500
        assert "error" in resp.get_json()


class TestTranscribeEndpoint:
    def test_transcribe_returns_text(self, client):
        from io import BytesIO
        with patch("storyteller.tts.transcribe", return_value="Hello world") as mock_t:
            resp = client.post(
                "/api/transcribe",
                data={"audio": (BytesIO(b"fake-audio"), "recording.webm")},
                content_type="multipart/form-data",
            )
        assert resp.status_code == 200
        assert resp.get_json()["text"] == "Hello world"
        mock_t.assert_called_once()

    def test_transcribe_missing_audio_returns_400(self, client):
        resp = client.post("/api/transcribe", data={}, content_type="multipart/form-data")
        assert resp.status_code == 400
        assert "error" in resp.get_json()

    def test_transcribe_error_returns_500(self, client):
        from io import BytesIO
        from storyteller.tts import TTSError
        with patch("storyteller.tts.transcribe", side_effect=TTSError("STT failed")):
            resp = client.post(
                "/api/transcribe",
                data={"audio": (BytesIO(b"audio"), "audio.webm")},
                content_type="multipart/form-data",
            )
        assert resp.status_code == 500
        assert "error" in resp.get_json()

