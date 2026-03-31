"""LLM integration for title and tag generation, powered by the `llm` package."""

import json
import logging

import llm

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "qwen3.5:2b"

_TITLE_PROMPT = """You are a story title generator. Given a personal story, produce a single short, evocative title (5-10 words). Return ONLY the title text, nothing else."""

_TAGS_PROMPT = """You are a story tag classifier. Given a personal story, select the most relevant tags from this list:

{available_tags}

Rules:
- Pick 2-5 tags that best describe the story's themes
- You may also suggest up to 2 NEW tags not in the list, if warranted
- Return a JSON array of lowercase tag strings, e.g. ["childhood", "family", "new-tag"]
- Return ONLY the JSON array, no other text"""


def _get_model(model_id: str = DEFAULT_MODEL) -> llm.Model:
    return llm.get_model(model_id)


def is_available(model_id: str = DEFAULT_MODEL) -> bool:
    """Check if the model is accessible."""
    try:
        _get_model(model_id)
        return True
    except llm.UnknownModelError:
        return False


def generate_title(story_content: str, model_id: str = DEFAULT_MODEL) -> str | None:
    """Generate a title for a story using the configured LLM."""
    try:
        model = _get_model(model_id)
        response = model.prompt(
            story_content[:3000],
            system=_TITLE_PROMPT,
            think=False,
        )
        title = response.text().strip().strip('"').strip("'")
        if title:
            return title
    except Exception as e:
        logger.warning("LLM title generation failed: %s", e)
    return None


def generate_tags(
    story_content: str,
    available_tags: list[str],
    model_id: str = DEFAULT_MODEL,
) -> list[str] | None:
    """Generate tag suggestions for a story using the configured LLM."""
    system = _TAGS_PROMPT.format(available_tags=", ".join(available_tags))
    try:
        model = _get_model(model_id)
        response = model.prompt(
            story_content[:3000],
            system=system,
            think=False,
        )
        raw = response.text().strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        tags = json.loads(raw)
        if isinstance(tags, list):
            return [t.strip().lower() for t in tags if isinstance(t, str) and t.strip()]
    except Exception as e:
        logger.warning("LLM tag generation failed: %s", e)
    return None
