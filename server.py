"""Share Your Story - Flask server with REST API."""

import logging
import os
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# Ensure the backend directory is on sys.path so 'storyteller' is importable
# (needed for Vercel where the working directory may not be backend/)
sys.path.insert(0, str(Path(__file__).resolve().parent))

from flask import Flask, jsonify, request, Response

from storyteller import db
from storyteller import conversation
from storyteller import tts
from storyteller import share as share_module

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024  # 25 MB upload limit
db.init_db()

# Load .env file from project root (no dependencies needed)
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    try:
        _env_text = _env_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        _env_text = ""
    for line in _env_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Support lines like "export KEY=VALUE"
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        # Remove inline comments from the value part: KEY=VALUE # comment
        if "#" in value:
            value, _ = value.split("#", 1)
        value = value.strip()
        # Strip surrounding single or double quotes
        if (len(value) >= 2) and ((value[0] == value[-1]) and value[0] in ("'", '"')):
            value = value[1:-1].strip()
        # Skip setting empty values so existing env vars / fallbacks still work
        if not key or not value:
            continue
        os.environ.setdefault(key, value)


def _is_allowed_origin(origin: str) -> bool:
    allowed_origins = [
        "https://deven367.github.io",
        "http://localhost:5173",
        "http://localhost:5050",
    ]
    if origin in allowed_origins:
        return True
    if origin.endswith(".vercel.app") and ("deven367" in origin or "claude-hack" in origin):
        return True
    return False


@app.before_request
def handle_preflight():
    """Handle CORS preflight requests before any route logic."""
    if request.method == "OPTIONS":
        response = Response("", status=204)
        origin = request.headers.get("Origin", "")
        if _is_allowed_origin(origin):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Headers"] = "Content-Type"
            response.headers["Access-Control-Allow-Methods"] = (
                "GET, POST, PUT, DELETE, OPTIONS"
            )
            response.headers["Access-Control-Max-Age"] = "86400"
        return response


@app.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin", "")
    if _is_allowed_origin(origin):
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = (
            "GET, POST, PUT, DELETE, OPTIONS"
        )
    return response


@app.route("/")
def index():
    return jsonify({"name": "Share Your Story API", "status": "ok"})


@app.route("/api/persons", methods=["GET"])
def get_persons():
    persons = db.get_all_persons()
    return jsonify(persons)


@app.route("/api/persons", methods=["POST"])
def create_person():
    data = request.json
    name = data.get("name", "").strip()
    age_group = data.get("age_group", "")
    if not name:
        return jsonify({"error": "Name is required"}), 400
    person_id = db.create_person(name, age_group)
    story_id = db.get_or_create_story(person_id, f"{name}'s Story")
    return jsonify({"person_id": person_id, "story_id": story_id})


@app.route("/api/persons/<int:person_id>", methods=["PUT"])
def update_person(person_id):
    data = request.json
    name = data.get("name", "").strip()
    if name:
        db.update_person(person_id, name)
        # Also update story title
        stories = db.get_stories_for_person(person_id)
        if stories:
            db.update_story(
                stories[0]["id"], f"{name}'s Story", stories[0].get("content", "")
            )
    return jsonify({"status": "ok"})


@app.route("/api/responses/<int:story_id>", methods=["GET"])
def get_responses(story_id):
    responses = db.get_questionnaire_responses(story_id)
    return jsonify(responses)


@app.route("/api/responses", methods=["POST"])
def save_response():
    data = request.json
    story_id = data.get("story_id")
    question = data.get("question", "").strip()
    answer = data.get("answer", "").strip()
    if not story_id or not question:
        return jsonify({"error": "story_id and question required"}), 400
    db.save_or_update_response(story_id, question, answer)
    return jsonify({"status": "ok"})


@app.route("/api/stories", methods=["GET"])
def get_all_stories():
    stories = db.get_all_stories()
    for story in stories:
        story["responses"] = db.get_questionnaire_responses(story["id"])
    return jsonify(stories)


@app.route("/api/stories/<int:story_id>", methods=["GET"])
def get_story(story_id):
    story = db.get_story(story_id)
    if not story:
        return jsonify({"error": "Story not found"}), 404
    story["responses"] = db.get_questionnaire_responses(story_id)
    return jsonify(story)


@app.route("/api/stories/<int:story_id>", methods=["PUT"])
def update_story(story_id):
    data = request.json
    title = data.get("title", "").strip()
    content = data.get("content", "")
    if not title:
        return jsonify({"error": "Title is required"}), 400
    db.update_story(story_id, title, content)
    return jsonify({"status": "ok"})


@app.route("/api/stories/<int:story_id>", methods=["DELETE"])
def delete_story(story_id):
    """Delete a story and all its conversations."""
    db.delete_story(story_id)
    return jsonify({"status": "ok"})


@app.route("/api/conversations/<int:conversation_id>", methods=["PUT"])
def rename_conversation(conversation_id):
    data = request.json or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    db.rename_conversation(conversation_id, title)
    return jsonify({"status": "ok"})


@app.route("/api/conversations/<int:conversation_id>", methods=["DELETE"])
def delete_conversation(conversation_id):
    """Delete a single conversation session."""
    db.delete_conversation(conversation_id)
    return jsonify({"status": "ok"})


# --- Custom chapters ---


@app.route("/api/stories/<int:story_id>/custom-chapters", methods=["GET"])
def get_custom_chapters(story_id):
    chapters = db.get_custom_chapters(story_id)
    return jsonify(chapters)


@app.route("/api/stories/<int:story_id>/custom-chapters", methods=["POST"])
def create_custom_chapter(story_id):
    data = request.json or {}
    title = data.get("title", "New Chapter").strip()
    chapter = db.create_custom_chapter(story_id, title)
    return jsonify(chapter)


@app.route("/api/custom-chapters/<int:chapter_id>", methods=["PUT"])
def update_custom_chapter(chapter_id):
    data = request.json or {}
    title = data.get("title", "").strip()
    if not title:
        return jsonify({"error": "title is required"}), 400
    db.update_custom_chapter(chapter_id, title)
    return jsonify({"status": "ok"})


@app.route("/api/custom-chapters/<int:chapter_id>", methods=["DELETE"])
def delete_custom_chapter(chapter_id):
    db.delete_custom_chapter(chapter_id)
    return jsonify({"status": "ok"})


# --- Conversation / Chat endpoints ---


@app.route("/api/chapters", methods=["GET"])
def get_chapters():
    """Return chapter metadata for all chapters."""
    chapters = []
    for i in range(conversation.get_chapter_count()):
        chapters.append(conversation.get_chapter_info(i))
    return jsonify(chapters)


@app.route("/api/chat", methods=["POST"])
def chat():
    """Send a message in a chapter conversation. Returns AI response."""
    data = request.json
    story_id = data.get("story_id")
    chapter_index = data.get("chapter_index")
    conversation_id = data.get("conversation_id")
    message = data.get("message", "").strip()
    person_name = data.get("person_name", "Friend")
    custom_chapter_title = data.get("custom_chapter_title")  # set for freeform stories
    custom_chapter_id = data.get(
        "custom_chapter_id"
    )  # PK of custom_chapters row, if applicable
    language = data.get("language", "en")  # UI language for multilingual support

    if story_id is None or chapter_index is None:
        return jsonify({"error": "story_id and chapter_index required"}), 400

    # Load specific conversation or latest for chapter
    conv = None
    if conversation_id:
        conv = db.get_conversation_by_id(conversation_id)
        if conv and (
            conv["story_id"] != story_id or conv["chapter_index"] != chapter_index
        ):
            return jsonify(
                {"error": "conversation does not belong to this story/chapter"}
            ), 400
    if not conv:
        conv = db.get_conversation(story_id, chapter_index)

    if conv:
        messages = conv["messages"]
        extracted = conv["extracted_answers"]
        conv_id = conv["id"]
    else:
        messages = []
        extracted = {}
        conv_id = None

    # Gather context from previous sessions in this chapter
    prior_stories = []
    all_sessions = db.get_chapter_conversations(story_id, chapter_index)
    if conv_id:
        for sess in all_sessions:
            if sess["id"] != conv_id:
                for k, v in sess["extracted_answers"].items():
                    prior_stories.append(v)

    # For guided chapters, treat non-first stories as open-ended
    # For guided chapters, treat *new* non-first sessions as open-ended
    effective_custom_title = custom_chapter_title
    # Only infer open-ended/freeform mode when creating a new conversation,
    # not when resuming an existing one. If there are already prior sessions
    # for this chapter, use the chapter title as the custom title for the
    # new session so it is handled as an open-ended retelling.
    if effective_custom_title is None and not conv_id and all_sessions:
        chapter_info = conversation.get_chapter_info(chapter_index)
        if chapter_info:
            effective_custom_title = chapter_info.get("title")

    # If no messages yet, generate opening message from AI
    if not messages and not message:
        opening = conversation.get_opening_message(
            chapter_index,
            person_name,
            prior_context=prior_stories,
            custom_chapter_title=effective_custom_title,
            language=language,
        )
        messages = [{"role": "assistant", "content": opening, "timestamp": ""}]
        if conv_id:
            db.update_conversation(conv_id, messages, extracted)
        else:
            conv_id = db.create_conversation(
                story_id,
                chapter_index,
                messages,
                extracted,
                custom_chapter_id=custom_chapter_id,
            )
        return jsonify(
            {
                "ai_message": opening,
                "messages": messages,
                "extracted_answers": extracted,
                "chapter_info": conversation.get_chapter_info(chapter_index),
                "conversation_id": conv_id,
            }
        )

    if not message:
        return jsonify({"error": "message is required"}), 400

    # Get AI response
    ai_response, updated_messages = conversation.chat(
        person_name,
        chapter_index,
        messages,
        message,
        prior_context=prior_stories,
        custom_chapter_title=effective_custom_title,
        language=language,
    )

    # Extract answers from the updated conversation
    effective_index = -1 if effective_custom_title is not None else chapter_index
    extracted = conversation.extract_answers(effective_index, updated_messages)

    # Save to DB
    chapter_info = conversation.get_chapter_info(chapter_index)
    if conv_id:
        db.update_conversation(conv_id, updated_messages, extracted)
    else:
        conv_id = db.create_conversation(
            story_id,
            chapter_index,
            updated_messages,
            extracted,
            custom_chapter_id=custom_chapter_id,
        )

    return jsonify(
        {
            "ai_message": ai_response,
            "messages": updated_messages,
            "extracted_answers": extracted,
            "chapter_info": chapter_info,
            "conversation_id": conv_id,
            "status": "in_progress",
        }
    )


@app.route("/api/conversations/<int:story_id>/<chapter_index>/new", methods=["POST"])
def new_conversation_session(story_id, chapter_index):
    """Start a new conversation session within a chapter."""
    chapter_index = int(chapter_index)
    data = request.json or {}
    person_name = data.get("person_name", "Friend")
    custom_chapter_title = data.get("custom_chapter_title")
    custom_chapter_id = data.get("custom_chapter_id")
    language = data.get("language", "en")

    # Gather context from all existing sessions in this chapter
    prior_stories = []
    all_sessions = db.get_chapter_conversations(story_id, chapter_index)
    for sess in all_sessions:
        for k, v in sess["extracted_answers"].items():
            prior_stories.append(v)

    # For guided chapters with existing stories, treat new stories as open-ended
    effective_custom_title = custom_chapter_title
    if effective_custom_title is None and len(all_sessions) > 0:
        chapter_info = conversation.get_chapter_info(chapter_index)
        if chapter_info:
            effective_custom_title = chapter_info.get("title")

    opening = conversation.get_opening_message(
        chapter_index,
        person_name,
        prior_context=prior_stories,
        custom_chapter_title=effective_custom_title,
        language=language,
    )
    messages = [{"role": "assistant", "content": opening, "timestamp": ""}]
    conv_id = db.create_conversation(
        story_id, chapter_index, messages, {}, custom_chapter_id=custom_chapter_id
    )

    return jsonify(
        {
            "ai_message": opening,
            "messages": messages,
            "extracted_answers": {},
            "chapter_info": conversation.get_chapter_info(chapter_index),
            "conversation_id": conv_id,
            "session_number": len(all_sessions) + 1,
        }
    )


@app.route("/api/conversations/<int:story_id>", methods=["GET"])
def get_conversations(story_id):
    """Get all chapter conversations for a story (progress overview)."""
    convs = db.get_all_conversations(story_id)
    # Group by chapter for summary
    chapters = {}
    for conv in convs:
        ci = conv["chapter_index"]
        if ci not in chapters:
            chapters[ci] = {"sessions": 0, "total_messages": 0, "total_answers": 0}
        chapters[ci]["sessions"] += 1
        chapters[ci]["total_messages"] += len(conv["messages"])
        chapters[ci]["total_answers"] += len(conv["extracted_answers"])

    result = []
    for ci, info in sorted(chapters.items()):
        chapter_info = conversation.get_chapter_info(ci)
        result.append(
            {
                "chapter_index": ci,
                "chapter_info": chapter_info,
                "message_count": info["total_messages"],
                "answers_count": info["total_answers"],
                "session_count": info["sessions"],
                "status": "in_progress"
                if info["total_messages"] > 0
                else "not_started",
            }
        )
    return jsonify(result)


@app.route("/api/conversations/<int:story_id>/<chapter_index>", methods=["GET"])
def get_conversation(story_id, chapter_index):
    """Get all conversation sessions for a chapter."""
    chapter_index = int(chapter_index)

    sessions = db.get_chapter_conversations(story_id, chapter_index)
    if not sessions:
        return jsonify(
            {
                "sessions": [],
                "latest": {
                    "messages": [],
                    "extracted_answers": {},
                    "conversation_id": None,
                },
                "status": "not_started",
                "chapter_info": conversation.get_chapter_info(chapter_index),
            }
        )

    latest = sessions[-1]
    return jsonify(
        {
            "sessions": [
                {
                    "conversation_id": s["id"],
                    "title": s.get("title"),
                    "messages": s["messages"],
                    "message_count": len(s["messages"]),
                    "answers_count": len(s["extracted_answers"]),
                    "extracted_answers": s["extracted_answers"],
                    "created_at": s.get("created_at", ""),
                }
                for s in sessions
            ],
            "latest": {
                "messages": latest["messages"],
                "extracted_answers": latest["extracted_answers"],
                "conversation_id": latest["id"],
            },
            "status": "in_progress",
            "chapter_info": conversation.get_chapter_info(chapter_index),
        }
    )


@app.route("/api/transcribe", methods=["POST"])
def transcribe():
    """Transcribe an audio file to text using ElevenLabs Scribe."""
    if "audio" not in request.files:
        return jsonify({"error": "No audio file provided"}), 400

    audio_file = request.files["audio"]
    audio_data = audio_file.read()

    try:
        text = tts.transcribe(audio_data, filename=audio_file.filename or "audio.webm")
        return jsonify({"text": text})
    except tts.TTSError as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tts", methods=["POST"])
def text_to_speech():
    """Convert text to speech via ElevenLabs. Returns MP3 audio."""
    data = request.json
    text = (data.get("text") or "").strip() if data else ""
    if not text:
        return jsonify({"error": "text is required"}), 400

    voice_id = data.get("voice_id") if data else None

    try:
        audio_bytes = tts.synthesize(text, voice_id=voice_id)
        return Response(audio_bytes, mimetype="audio/mpeg")
    except tts.TTSError as e:
        return jsonify({"error": str(e)}), 500


# --- Share / Export endpoints ---


def _collect_conversations(story_id: int) -> list[dict]:
    """Return all conversations for a story, enriched with chapter title."""
    convs = db.get_all_conversations(story_id)
    result = []
    for conv in convs:
        chapter_info = conversation.get_chapter_info(conv["chapter_index"])
        result.append(
            {
                **conv,
                "chapter_title": chapter_info.get("title") if chapter_info else None,
            }
        )
    return result


@app.route("/api/stories/<int:story_id>/share/summary", methods=["GET"])
def get_share_summary(story_id):
    """Return AI-generated social summary for a story."""
    story = db.get_story(story_id)
    if not story:
        return jsonify({"error": "Story not found"}), 404
    convs = _collect_conversations(story_id)
    if not convs:
        return jsonify({"error": "No content to summarize"}), 400
    person_name = story.get("person_name") or "Unknown"
    summary = share_module.generate_summary(convs, person_name)
    return jsonify({"summary": summary})


@app.route("/api/stories/<int:story_id>/share/audiobook", methods=["POST"])
def download_audiobook(story_id):
    """Generate and return a full MP3 audiobook of the story."""
    story = db.get_story(story_id)
    if not story:
        return jsonify({"error": "Story not found"}), 404
    convs = _collect_conversations(story_id)
    if not convs:
        return jsonify({"error": "No content to narrate"}), 400

    person_name = story.get("person_name") or "Unknown"
    data = request.json or {}
    voice_id = data.get("voice_id") or None

    try:
        mp3_bytes = share_module.generate_audiobook(convs, person_name, voice_id=voice_id)
    except tts.TTSError as e:
        return jsonify({"error": str(e)}), 500

    safe_name = person_name.replace(" ", "_")
    return Response(
        mp3_bytes,
        mimetype="audio/mpeg",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}_Story.mp3"'
        },
    )


@app.route("/api/stories/<int:story_id>/share/reel", methods=["POST"])
def download_reel(story_id):
    """Generate and return a 9:16 MP4 reel for Instagram/YouTube Shorts."""
    story = db.get_story(story_id)
    if not story:
        return jsonify({"error": "Story not found"}), 404
    convs = _collect_conversations(story_id)
    if not convs:
        return jsonify({"error": "No content to share"}), 400

    person_name = story.get("person_name") or "Unknown"
    data = request.json or {}
    voice_id = data.get("voice_id") or None
    summary = (
        data.get("summary") or share_module.generate_summary(convs, person_name)
    )

    try:
        audio_bytes = share_module.synthesize_summary(
            summary, person_name, voice_id=voice_id
        )
        video_bytes = share_module.generate_reel(summary, audio_bytes, person_name)
    except (tts.TTSError, Exception) as e:
        logger.error("Reel generation failed: %s", e)
        return jsonify({"error": str(e)}), 500

    safe_name = person_name.replace(" ", "_")
    return Response(
        video_bytes,
        mimetype="video/mp4",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}_Reel.mp4"'
        },
    )


if __name__ == "__main__":
    app.run(debug=True, port=5050)
