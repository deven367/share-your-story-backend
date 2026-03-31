"""SQLite database layer for Share Your Story, powered by sqlite-utils."""

import json
from datetime import datetime, timezone
from pathlib import Path

import sqlite_utils

DB_PATH = Path(__file__).resolve().parent.parent / "stories.db"

PRESET_TAGS = [
    "childhood",
    "family",
    "friendship",
    "love",
    "loss",
    "hardships",
    "achievement",
    "career",
    "education",
    "travel",
    "war",
    "migration",
    "health",
    "faith",
    "humor",
    "adventure",
    "coming-of-age",
    "life-lesson",
    "turning-point",
    "gratitude",
]


def get_db() -> sqlite_utils.Database:
    db = sqlite_utils.Database(DB_PATH)
    db.execute("PRAGMA foreign_keys = ON")
    return db


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def init_db():
    db = get_db()

    db["persons"].create(
        {"id": int, "name": str, "age_group": str, "created_at": str},
        pk="id",
        if_not_exists=True,
    )

    db["stories"].create(
        {
            "id": int,
            "person_id": int,
            "title": str,
            "content": str,
            "created_at": str,
            "updated_at": str,
        },
        pk="id",
        foreign_keys=[("person_id", "persons")],
        if_not_exists=True,
    )

    db["tags"].create(
        {"id": int, "name": str},
        pk="id",
        if_not_exists=True,
    )
    if "idx_tags_name" not in {idx.name for idx in db["tags"].indexes}:
        db["tags"].create_index(["name"], unique=True, index_name="idx_tags_name", if_not_exists=True)

    db["story_tags"].create(
        {"story_id": int, "tag_id": int},
        pk=("story_id", "tag_id"),
        foreign_keys=[("story_id", "stories"), ("tag_id", "tags")],
        if_not_exists=True,
    )

    db["questionnaire_responses"].create(
        {
            "id": int,
            "story_id": int,
            "question": str,
            "answer": str,
            "created_at": str,
        },
        pk="id",
        foreign_keys=[("story_id", "stories")],
        if_not_exists=True,
    )

    # custom_chapters must be created before conversations (which has an FK to it)
    db["custom_chapters"].create(
        {
            "id": int,
            "story_id": int,
            "title": str,
            "sort_order": int,
            "created_at": str,
        },
        pk="id",
        foreign_keys=[("story_id", "stories")],
        if_not_exists=True,
    )

    db["conversations"].create(
        {
            "id": int,
            "story_id": int,
            "chapter_index": int,
            "custom_chapter_id": int,  # FK to custom_chapters; NULL for built-in chapters
            "title": str,          # optional custom name for this session
            "messages": str,       # JSON array of {role, content, timestamp}
            "extracted_answers": str,  # JSON object {question_id: answer_text}
            "status": str,         # "in_progress" or "completed"
            "created_at": str,
            "updated_at": str,
        },
        pk="id",
        foreign_keys=[("story_id", "stories"), ("custom_chapter_id", "custom_chapters")],
        if_not_exists=True,
    )
    # Add title column if upgrading from older schema
    if "title" not in {col.name for col in db["conversations"].columns}:
        db.execute("ALTER TABLE conversations ADD COLUMN title TEXT")
    # Add custom_chapter_id column if upgrading from older schema
    if "custom_chapter_id" not in {col.name for col in db["conversations"].columns}:
        db.execute("ALTER TABLE conversations ADD COLUMN custom_chapter_id INTEGER REFERENCES custom_chapters(id)")

    db["tags"].insert_all(
        [{"name": t} for t in PRESET_TAGS],
        ignore=True,
    )


# --- Person operations ---

def create_person(name: str, age_group: str) -> int:
    db = get_db()
    return db["persons"].insert(
        {"name": name, "age_group": age_group, "created_at": _now()},
    ).last_pk


def get_all_persons() -> list[dict]:
    db = get_db()
    return list(db["persons"].rows_where(order_by="name"))


def get_person(person_id: int) -> dict | None:
    db = get_db()
    try:
        return db["persons"].get(person_id)
    except sqlite_utils.db.NotFoundError:
        return None


def update_person(person_id: int, name: str):
    db = get_db()
    db["persons"].update(person_id, {"name": name})


# --- Story operations ---

def create_story(person_id: int, title: str, content: str, tag_names: list[str]) -> int:
    db = get_db()
    now = _now()
    story_id = db["stories"].insert(
        {
            "person_id": person_id,
            "title": title,
            "content": content,
            "created_at": now,
            "updated_at": now,
        },
    ).last_pk

    for tag_name in tag_names:
        tag_name = tag_name.strip().lower()
        if not tag_name:
            continue
        db["tags"].insert({"name": tag_name}, ignore=True)
        tag_row = list(db["tags"].rows_where("name = ?", [tag_name]))[0]
        db["story_tags"].insert(
            {"story_id": story_id, "tag_id": tag_row["id"]},
            ignore=True,
        )

    return story_id


def get_stories_for_person(person_id: int) -> list[dict]:
    db = get_db()
    stories = list(
        db["stories"].rows_where("person_id = ?", [person_id], order_by="-created_at")
    )
    for story in stories:
        story["tags"] = _get_tags_for_story(db, story["id"])
    return stories


def get_all_stories() -> list[dict]:
    db = get_db()
    stories = list(db.execute("""
        SELECT s.*, p.name as person_name
        FROM stories s
        JOIN persons p ON s.person_id = p.id
        ORDER BY s.created_at DESC
    """).fetchall())
    columns = ["id", "person_id", "title", "content", "created_at", "updated_at", "person_name"]
    stories = [dict(zip(columns, row)) for row in stories]
    for story in stories:
        story["tags"] = _get_tags_for_story(db, story["id"])
    return stories


def get_story(story_id: int) -> dict | None:
    db = get_db()
    rows = list(db.execute("""
        SELECT s.*, p.name as person_name
        FROM stories s
        JOIN persons p ON s.person_id = p.id
        WHERE s.id = ?
    """, [story_id]).fetchall())
    if not rows:
        return None
    columns = ["id", "person_id", "title", "content", "created_at", "updated_at", "person_name"]
    story = dict(zip(columns, rows[0]))
    story["tags"] = _get_tags_for_story(db, story_id)
    return story


def update_story(story_id: int, title: str, content: str):
    db = get_db()
    db["stories"].update(story_id, {"title": title, "content": content, "updated_at": _now()})


def delete_story(story_id: int):
    """Delete a story and all related data."""
    db = get_db()
    db["conversations"].delete_where("story_id = ?", [story_id])
    db["questionnaire_responses"].delete_where("story_id = ?", [story_id])
    db["story_tags"].delete_where("story_id = ?", [story_id])
    db["custom_chapters"].delete_where("story_id = ?", [story_id])
    db["stories"].delete(story_id)


def rename_conversation(conversation_id: int, title: str):
    db = get_db()
    db["conversations"].update(conversation_id, {"title": title})


def delete_conversation(conversation_id: int):
    """Delete a single conversation session."""
    db = get_db()
    db["conversations"].delete(conversation_id)


def get_or_create_story(person_id: int, title: str) -> int:
    """Get the first story for a person, or create one."""
    db = get_db()
    rows = list(db["stories"].rows_where("person_id = ?", [person_id], order_by="id", limit=1))
    if rows:
        return rows[0]["id"]
    now = _now()
    return db["stories"].insert({
        "person_id": person_id, "title": title, "content": "",
        "created_at": now, "updated_at": now,
    }).last_pk


# --- Tag operations ---

def _get_tags_for_story(db: sqlite_utils.Database, story_id: int) -> list[str]:
    rows = db.execute("""
        SELECT t.name FROM tags t
        JOIN story_tags st ON t.id = st.tag_id
        WHERE st.story_id = ?
        ORDER BY t.name
    """, [story_id]).fetchall()
    return [r[0] for r in rows]


def get_tags_for_story(story_id: int) -> list[str]:
    return _get_tags_for_story(get_db(), story_id)


def get_all_tags() -> list[str]:
    db = get_db()
    return [row["name"] for row in db["tags"].rows_where(order_by="name")]


def get_stories_by_tag(tag_name: str) -> list[dict]:
    db = get_db()
    rows = db.execute("""
        SELECT s.*, p.name as person_name
        FROM stories s
        JOIN persons p ON s.person_id = p.id
        JOIN story_tags st ON s.id = st.story_id
        JOIN tags t ON st.tag_id = t.id
        WHERE t.name = ?
        ORDER BY s.created_at DESC
    """, [tag_name]).fetchall()
    columns = ["id", "person_id", "title", "content", "created_at", "updated_at", "person_name"]
    stories = [dict(zip(columns, row)) for row in rows]
    for story in stories:
        story["tags"] = _get_tags_for_story(db, story["id"])
    return stories


# --- Questionnaire operations ---

def save_questionnaire_responses(story_id: int, responses: list[dict]):
    db = get_db()
    now = _now()
    db["questionnaire_responses"].insert_all([
        {
            "story_id": story_id,
            "question": resp["question"],
            "answer": resp.get("answer", ""),
            "created_at": now,
        }
        for resp in responses
    ])


def get_questionnaire_responses(story_id: int) -> list[dict]:
    db = get_db()
    return list(
        db["questionnaire_responses"].rows_where(
            "story_id = ?", [story_id], order_by="id"
        )
    )


def save_or_update_response(story_id: int, question: str, answer: str):
    """Upsert a single questionnaire response."""
    db = get_db()
    existing = list(db["questionnaire_responses"].rows_where(
        "story_id = ? AND question = ?", [story_id, question]
    ))
    if existing:
        db["questionnaire_responses"].update(existing[0]["id"], {"answer": answer})
    else:
        db["questionnaire_responses"].insert({
            "story_id": story_id, "question": question,
            "answer": answer, "created_at": _now(),
        })


# --- Conversation operations ---

def _parse_conversation_row(row: dict) -> dict:
    row["messages"] = json.loads(row["messages"]) if row["messages"] else []
    row["extracted_answers"] = json.loads(row["extracted_answers"]) if row["extracted_answers"] else {}
    return row


def get_conversation(story_id: int, chapter_index: int) -> dict | None:
    """Get the latest conversation session for a chapter."""
    db = get_db()
    rows = list(db["conversations"].rows_where(
        "story_id = ? AND chapter_index = ?", [story_id, chapter_index],
        order_by="-id", limit=1,
    ))
    if not rows:
        return None
    return _parse_conversation_row(rows[0])


def get_conversation_by_id(conversation_id: int) -> dict | None:
    db = get_db()
    try:
        row = db["conversations"].get(conversation_id)
        return _parse_conversation_row(row)
    except sqlite_utils.db.NotFoundError:
        return None


def get_chapter_conversations(story_id: int, chapter_index: int) -> list[dict]:
    """Get all conversation sessions for a chapter, ordered oldest first."""
    db = get_db()
    rows = list(db["conversations"].rows_where(
        "story_id = ? AND chapter_index = ?", [story_id, chapter_index],
        order_by="id",
    ))
    return [_parse_conversation_row(row) for row in rows]


def get_all_conversations(story_id: int) -> list[dict]:
    db = get_db()
    rows = list(db["conversations"].rows_where(
        "story_id = ?", [story_id], order_by="chapter_index, id"
    ))
    return [_parse_conversation_row(row) for row in rows]


def create_conversation(
    story_id: int,
    chapter_index: int,
    messages: list[dict] | None = None,
    extracted_answers: dict | None = None,
    status: str = "in_progress",
    custom_chapter_id: int | None = None,
) -> int:
    """Always creates a new conversation session."""
    db = get_db()
    now = _now()
    row: dict = {
        "story_id": story_id,
        "chapter_index": chapter_index,
        "messages": json.dumps(messages or []),
        "extracted_answers": json.dumps(extracted_answers or {}),
        "status": status,
        "created_at": now,
        "updated_at": now,
    }
    if custom_chapter_id is not None:
        row["custom_chapter_id"] = custom_chapter_id
    return db["conversations"].insert(row).last_pk


def update_conversation(
    conversation_id: int,
    messages: list[dict],
    extracted_answers: dict,
    status: str = "in_progress",
):
    db = get_db()
    try:
        db["conversations"].update(conversation_id, {
            "messages": json.dumps(messages),
            "extracted_answers": json.dumps(extracted_answers),
            "status": status,
            "updated_at": _now(),
        })
    except sqlite_utils.db.NotFoundError:
        raise ValueError(f"Conversation {conversation_id} not found — it may have been deleted.")


def save_conversation(
    story_id: int,
    chapter_index: int,
    messages: list[dict],
    extracted_answers: dict,
    status: str = "in_progress",
) -> int:
    """Legacy upsert — updates latest session or creates first one."""
    db = get_db()
    existing = list(db["conversations"].rows_where(
        "story_id = ? AND chapter_index = ?", [story_id, chapter_index],
        order_by="-id", limit=1,
    ))
    if existing:
        update_conversation(existing[0]["id"], messages, extracted_answers, status)
        return existing[0]["id"]
    else:
        return create_conversation(story_id, chapter_index, messages, extracted_answers, status)


# --- Custom chapter operations ---

def get_custom_chapters(story_id: int) -> list[dict]:
    db = get_db()
    return list(db["custom_chapters"].rows_where(
        "story_id = ?", [story_id], order_by="sort_order, id"
    ))


def create_custom_chapter(story_id: int, title: str) -> dict:
    db = get_db()
    existing = list(db["custom_chapters"].rows_where("story_id = ?", [story_id]))
    sort_order = max((c["sort_order"] for c in existing), default=-1) + 1
    row_id = db["custom_chapters"].insert({
        "story_id": story_id,
        "title": title,
        "sort_order": sort_order,
        "created_at": _now(),
    }).last_pk
    try:
        return db["custom_chapters"].get(row_id)
    except sqlite_utils.db.NotFoundError:
        return {"id": row_id, "story_id": story_id, "title": title, "sort_order": sort_order}


def update_custom_chapter(chapter_id: int, title: str):
    db = get_db()
    db["custom_chapters"].update(chapter_id, {"title": title})


def delete_custom_chapter(chapter_id: int):
    db = get_db()
    # Delete conversations linked to this custom chapter via the explicit FK column
    db["conversations"].delete_where("custom_chapter_id = ?", [chapter_id])
    db["custom_chapters"].delete(chapter_id)
