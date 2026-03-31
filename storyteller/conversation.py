"""Conversational interview engine powered by Claude via llm-anthropic."""

import json
import logging
import random
from datetime import datetime, timezone

import llm

logger = logging.getLogger(__name__)

MODEL_ID = "anthropic/claude-sonnet-4-6"

# Map of language codes to their full names for system prompts
LANGUAGE_NAMES = {
    "en": "English", "es": "Spanish", "fr": "French", "de": "German",
    "it": "Italian", "pt": "Portuguese", "nl": "Dutch", "pl": "Polish",
    "sv": "Swedish", "da": "Danish", "fi": "Finnish", "no": "Norwegian",
    "ro": "Romanian", "el": "Greek", "cs": "Czech", "sk": "Slovak",
    "bg": "Bulgarian", "hr": "Croatian", "hu": "Hungarian", "uk": "Ukrainian",
    "ru": "Russian", "tr": "Turkish", "ar": "Arabic", "hi": "Hindi",
    "ta": "Tamil", "zh": "Chinese", "ja": "Japanese", "ko": "Korean",
    "id": "Indonesian", "ms": "Malay", "fil": "Filipino", "vi": "Vietnamese",
    "th": "Thai",
}


def _language_instruction(language: str) -> str:
    """Return a system prompt instruction for responding in the given language."""
    if not language or language == "en":
        return ""
    lang_name = LANGUAGE_NAMES.get(language, language)
    return f"\n\nIMPORTANT: You MUST respond in {lang_name}. The user's interface is set to {lang_name}, so all your messages — questions, follow-ups, everything — must be written in {lang_name}. Do NOT respond in English."

# Chapter data mirrored from frontend — questions the AI should cover per chapter.
CHAPTERS = [
    {
        "id": "childhood",
        "title": "Childhood",
        "subtitle": "Where your story starts and the early days",
        "questions": [
            {"id": "birthday", "text": "When is your birthday?"},
            {"id": "birthplace", "text": "Where were you born?"},
            {"id": "named_after", "text": "Were you named after anyone special?"},
            {"id": "baby_stories", "text": "What stories has your family told about you as a baby?"},
            {"id": "earliest_memory", "text": "What is your earliest childhood memory?"},
            {"id": "hometown", "text": "Where did you grow up?"},
            {"id": "nickname", "text": "Did you have a nickname?"},
            {"id": "best_friend", "text": "Who was your best friend growing up?"},
            {"id": "fav_candy", "text": "What was your favorite candy or treat?"},
            {"id": "kid_personality", "text": "What were you like as a kid?"},
            {"id": "miss_childhood", "text": "What do you miss most about being a kid?"},
        ],
    },
    {
        "id": "school",
        "title": "School Days",
        "subtitle": "Lessons learned, not all from books",
        "questions": [
            {"id": "enjoy_school", "text": "Did you enjoy school?"},
            {"id": "fav_subject", "text": "Favorite and least favorite subjects?"},
            {"id": "school_activities", "text": "What activities did you participate in?"},
            {"id": "grades", "text": "What kind of student were you?"},
            {"id": "teacher_impact", "text": "Was there a teacher who changed your life?"},
            {"id": "school_advice", "text": "Knowing what you know now, what would you tell your student self?"},
        ],
    },
    {
        "id": "teenage",
        "title": "The Teenage Years",
        "subtitle": "Finding out who you were going to be",
        "questions": [
            {"id": "teen_style", "text": "How did you dress and style your hair as a teenager?"},
            {"id": "teen_weekend", "text": "What was a typical weekend night like?"},
            {"id": "teen_friends", "text": "Big group or a few close friends?"},
            {"id": "first_car", "text": "What kind of car did you learn to drive?"},
            {"id": "teen_personality", "text": "What were you like during your teen years?"},
            {"id": "teen_advice", "text": "What advice would you give your teenage self?"},
        ],
    },
    {
        "id": "parents",
        "title": "Mom & Dad",
        "subtitle": "The people who shaped you",
        "questions": [
            {"id": "describe_mother", "text": "Three words to describe your mother?"},
            {"id": "describe_father", "text": "Three words to describe your father?"},
            {"id": "parents_meet", "text": "How did your parents meet?"},
            {"id": "family_traditions", "text": "What family traditions do you remember?"},
            {"id": "like_parents", "text": "How are you most like your parents? Least like them?"},
        ],
    },
    {
        "id": "love",
        "title": "Love & Romance",
        "subtitle": "Matters of the heart",
        "questions": [
            {"id": "first_crush", "text": "Who was your biggest crush?"},
            {"id": "first_kiss", "text": "How old were you for your first kiss?"},
            {"id": "romantic_memory", "text": "What is your most romantic memory?"},
            {"id": "love_lesson", "text": "What is the most important thing love has taught you?"},
            {"id": "relationship_qualities", "text": "What matters most in a relationship?"},
        ],
    },
    {
        "id": "career",
        "title": "Work & Dreams",
        "subtitle": "The paths taken and not taken",
        "questions": [
            {"id": "childhood_dream", "text": "What did you want to be when you grew up?"},
            {"id": "first_job", "text": "What was your very first job?"},
            {"id": "favorite_job", "text": "What was your favorite job and why?"},
            {"id": "dream_profession", "text": "If you could do anything, what would it be?"},
            {"id": "never_do_jobs", "text": "Three jobs you would never do?"},
        ],
    },
    {
        "id": "adventures",
        "title": "Adventures",
        "subtitle": "The places and moments that changed everything",
        "questions": [
            {"id": "fav_travel", "text": "What is your favorite travel memory?"},
            {"id": "dream_vacation", "text": "What is your fantasy vacation?"},
            {"id": "always_packs", "text": "What do you always bring on a trip?"},
            {"id": "most_impulsive", "text": "What is the most impulsive thing you ever did?"},
        ],
    },
    {
        "id": "parent_hood",
        "title": "Becoming a Parent",
        "subtitle": "The chapter that changed everything",
        "questions": [
            {"id": "first_parent_age", "text": "How old were you when you first became a parent?"},
            {"id": "first_told", "text": "Who was the first person you told?"},
            {"id": "sang_to_kids", "text": "Was there a song you would sing to your children?"},
            {"id": "parenting_advice", "text": "What advice would you give yourself as a new parent?"},
            {"id": "fav_kid_memory", "text": "What is your favorite memory of your children?"},
        ],
    },
    {
        "id": "favorites",
        "title": "Favorites & Quirks",
        "subtitle": "The little things that make you, you",
        "questions": [
            {"id": "ice_cream", "text": "Favorite ice cream flavor?"},
            {"id": "coffee", "text": "How do you like your coffee?"},
            {"id": "favorite_season", "text": "Favorite season and why?"},
            {"id": "last_meal", "text": "What would you pick as your last meal?"},
            {"id": "autobiography_title", "text": "What would be the title of your autobiography?"},
            {"id": "perfect_day", "text": "What does a perfect day look like for you?"},
        ],
    },
    {
        "id": "reflections",
        "title": "Looking Back",
        "subtitle": "Wisdom, wonder, and what matters most",
        "questions": [
            {"id": "proudest", "text": "What are you most proud of?"},
            {"id": "biggest_regret", "text": "What is your biggest regret?"},
            {"id": "modern_surprise", "text": "What about the modern world surprises you most?"},
            {"id": "lesson_to_share", "text": "What would you want someone to learn from your story?"},
        ],
    },
]


def _build_freeform_system_prompt(person_name: str, extracted_answers: dict, language: str = "en") -> str:
    bonus_stories = {k: v for k, v in extracted_answers.items() if k.startswith("_")}

    prompt = f"""You are having a conversation with {person_name}. They want to tell a story — it could be about anything. Your job is to listen and help them tell it well.

This is completely open-ended. No topics, no questions, no agenda. Just follow wherever they take it.

How to talk:
- Sound like a normal person. No flowery language.
- NEVER use phrases like "That's wonderful!", "What a beautiful memory!", "Thank you for sharing that."
- Keep responses to 1-2 sentences.
- If they're telling a story, engage with it. Ask about the people, the details, how they felt. Stay in their story.
- If they pause, you can ask what happened next, or what that meant to them.
- Talk like a friend at a kitchen table, not like an interviewer."""

    if bonus_stories:
        prompt += "\n\nStories shared so far:\n"
        for key, value in bonus_stories.items():
            prompt += f"- {value[:200]}\n"

    prompt += _language_instruction(language)
    return prompt


def _build_freeform_extraction_prompt() -> str:
    return """Extract the stories from this conversation. Capture each distinct story, memory, or anecdote as a separate entry. Use keys like "_story_1", "_story_2", etc. Write each as a narrative paragraph in the person's voice, cleaned up for readability.

Also extract a "title" key — a short, natural title for the overall story (3-8 words).

Return ONLY a JSON object. No other text.

Example output: {"title": "The Summer We Built the Treehouse", "_story_1": "It was the summer of '78 and my dad decided we were going to build a treehouse. None of us knew what we were doing.", "_story_2": "My sister fell out of that treehouse three times before we finished it. She still has the scar on her knee."}"""


def _build_system_prompt(
    chapter_index: int,
    person_name: str,
    extracted_answers: dict,
    prior_context: list[str] | None = None,
    language: str = "en",
) -> str:
    if chapter_index == -1:
        return _build_freeform_system_prompt(person_name, extracted_answers, language=language)

    chapter = CHAPTERS[chapter_index]
    questions = chapter["questions"]

    answered_ids = set(k for k in extracted_answers.keys() if not k.startswith("_"))
    unanswered = [q for q in questions if q["id"] not in answered_ids]
    answered = [q for q in questions if q["id"] in answered_ids]
    bonus_stories = {k: v for k, v in extracted_answers.items() if k.startswith("_")}

    prompt = f"""You are helping {person_name} tell the story of their life. Right now you're talking about "{chapter['title']}" — {chapter['subtitle']}.

This is a conversation, not a questionnaire. Let {person_name} lead. If they want to tell a long story, let them talk. If they go on tangents, follow — tangents are often where the real story lives. Your job is to be a good listener and help them go deeper into what matters to them.

IMPORTANT — do not steer the conversation toward your question list. If {person_name} is in the middle of a story, stay with that story. Ask about details, people, feelings, what happened next. Do NOT change the subject to try to "cover" a question. The questions below are only there so you have something to fall back on during a lull — they are not goals to accomplish.

How to talk:
- Sound like a normal person. No flowery language. No "So let's go back to where it all started" or "the world you were born into." Just talk plainly.
- NEVER use phrases like "That's wonderful!", "What a beautiful memory!", "Thank you for sharing that." These are fake and people can tell.
- Keep responses to 1-2 sentences. You're not giving a speech.
- If they're telling a story, engage with it. Ask about the people, the details, how they felt. Stay in their story.
- If there's a natural pause and they seem done with a thread, you can gently open a new one.
- If they give a short answer, you can invite more ("What was that like?") but don't push.
- If they want to skip something, just move on.
- Talk like a friend at a kitchen table, not like an interviewer on a podcast.

Background topics for this chapter (use ONLY during natural lulls, never interrupt a story for these):
"""

    for q in questions:
        status = "(covered)" if q["id"] in answered_ids else ""
        prompt += f"- {q['text']} {status}\n"

    if answered:
        prompt += "\nWhat's been shared in this conversation:\n"
        for q in answered:
            prompt += f"- {q['text']}: {extracted_answers[q['id']]}\n"

    if bonus_stories:
        prompt += "\nStories shared in this conversation:\n"
        for key, value in bonus_stories.items():
            prompt += f"- {value[:200]}\n"

    if prior_context:
        prompt += "\nFrom previous conversations in this chapter (don't repeat, but you can reference):\n"
        for ctx in prior_context[:10]:
            prompt += f"- {ctx[:150]}\n"

    prompt += f"""
{person_name}'s story is bigger than any list of questions. If they share memories, feelings, or stories that don't map to a specific question, that's some of the best material for their book. Let the conversation breathe.

{person_name} can always come back to this chapter to add more stories. There's no rush."""

    if not unanswered:
        prompt += f"\n\nYou've touched on the main topics for this chapter, but {person_name} may have more to say. Stay open. If the conversation winds down naturally, you can mention they could move to the next chapter or start a new story whenever they're ready."

    prompt += _language_instruction(language)
    return prompt


def _build_extraction_prompt(chapter_index: int) -> str:
    if chapter_index == -1:
        return _build_freeform_extraction_prompt()

    chapter = CHAPTERS[chapter_index]
    questions = chapter["questions"]

    prompt = """Extract information from this conversation for a life story book. Do two things:

1. For each question below, if the person answered it (even partially), extract their answer using their own words, cleaned up for readability. Omit unanswered questions.

2. If the person shared stories, memories, anecdotes, or details that don't fit neatly into any question — capture those too. These are often the richest material. Use keys like "_story_1", "_story_2", etc. Write each as a short narrative paragraph in the person's voice.

Return ONLY a JSON object. No other text.

Questions to look for:
"""
    for q in questions:
        prompt += f'- "{q["id"]}": {q["text"]}\n'

    prompt += '\nExample output: {"birthday": "March 15, 1952", "birthplace": "Portland, Oregon", "_story_1": "We lived on a farm outside town with no electricity until I was six. My mother used to read to us by candlelight every night — she could do all the voices."}'
    return prompt


def get_chapter_count() -> int:
    return len(CHAPTERS)


def get_chapter_info(chapter_index: int) -> dict:
    if chapter_index == -1:
        return {
            "id": "freeform",
            "title": "Your Story",
            "subtitle": "Tell it your way",
            "question_count": 0,
        }
    if 0 <= chapter_index < len(CHAPTERS):
        ch = CHAPTERS[chapter_index]
        return {
            "id": ch["id"],
            "title": ch["title"],
            "subtitle": ch["subtitle"],
            "question_count": len(ch["questions"]),
        }
    return {}


# Pre-written opening messages per language — no LLM call needed.
# Each language has: first_chapter, freeform_new (list), freeform_returning (list), guided_returning (list)
# {name} is replaced with the person's name at runtime.
_OPENERS = {
    "en": {
        "first": "So {name}, let\u2019s start at the very beginning \u2014 when and where were you born?",
        "freeform_new": [
            "So {name}, what story would you like to share?",
            "Alright {name}, what\u2019s on your mind? Tell me anything.",
            "I\u2019m listening, {name}. What would you like to talk about?",
            "What\u2019s a story you\u2019ve been wanting to tell, {name}?",
            "Go ahead, {name} \u2014 what comes to mind?",
        ],
        "freeform_return": [
            "Welcome back, {name}. What else would you like to share?",
            "Good to have you back, {name}. Got another story for me?",
            "Hey {name}, ready to pick up where we left off?",
            "Back for more, {name}? I\u2019m all ears.",
        ],
        "guided_return": [
            "Welcome back, {name}. Got another story from this chapter?",
            "Hey {name}, good to pick this up again. What else comes to mind?",
            "Back for more, {name}? What else would you like to share about this?",
        ],
    },
    "es": {
        "first": "Bueno {name}, empecemos por el principio \u2014 \u00bfcu\u00e1ndo y d\u00f3nde naciste?",
        "freeform_new": [
            "\u00bfQu\u00e9 historia te gustar\u00eda compartir, {name}?",
            "Te escucho, {name}. \u00bfDe qu\u00e9 quieres hablar?",
            "\u00bfQu\u00e9 historia has querido contar, {name}?",
        ],
        "freeform_return": [
            "Bienvenido de vuelta, {name}. \u00bfQu\u00e9 m\u00e1s te gustar\u00eda compartir?",
            "Qu\u00e9 bueno tenerte de vuelta, {name}. \u00bfTienes otra historia?",
        ],
        "guided_return": [
            "Bienvenido de vuelta, {name}. \u00bfTienes otra historia de este cap\u00edtulo?",
            "Hola {name}, \u00bfqu\u00e9 m\u00e1s recuerdas?",
        ],
    },
    "fr": {
        "first": "Alors {name}, commen\u00e7ons par le d\u00e9but \u2014 quand et o\u00f9 \u00eates-vous n\u00e9(e) ?",
        "freeform_new": [
            "Quelle histoire aimeriez-vous partager, {name} ?",
            "Je vous \u00e9coute, {name}. De quoi aimeriez-vous parler ?",
            "Allez-y, {name} \u2014 qu\u2019est-ce qui vous vient \u00e0 l\u2019esprit ?",
        ],
        "freeform_return": [
            "Content de vous revoir, {name}. Quoi d\u2019autre aimeriez-vous partager ?",
            "Bon retour, {name}. Vous avez une autre histoire ?",
        ],
        "guided_return": [
            "Bon retour, {name}. Une autre histoire de ce chapitre ?",
            "Hey {name}, quoi d\u2019autre vous vient \u00e0 l\u2019esprit ?",
        ],
    },
    "de": {
        "first": "Also {name}, fangen wir ganz von vorne an \u2014 wann und wo bist du geboren?",
        "freeform_new": [
            "Welche Geschichte m\u00f6chtest du erz\u00e4hlen, {name}?",
            "Ich h\u00f6re zu, {name}. Wor\u00fcber m\u00f6chtest du sprechen?",
            "Leg los, {name} \u2014 was kommt dir in den Sinn?",
        ],
        "freeform_return": [
            "Willkommen zur\u00fcck, {name}. Was m\u00f6chtest du noch erz\u00e4hlen?",
            "Sch\u00f6n, dass du wieder da bist, {name}. Noch eine Geschichte?",
        ],
        "guided_return": [
            "Willkommen zur\u00fcck, {name}. Noch eine Geschichte aus diesem Kapitel?",
            "Hey {name}, was f\u00e4llt dir noch ein?",
        ],
    },
    "it": {
        "first": "Allora {name}, partiamo dall\u2019inizio \u2014 quando e dove sei nato/a?",
        "freeform_new": [
            "Che storia vorresti condividere, {name}?",
            "Ti ascolto, {name}. Di cosa vorresti parlare?",
            "Vai pure, {name} \u2014 cosa ti viene in mente?",
        ],
        "freeform_return": [
            "Bentornato/a, {name}. Cos\u2019altro vorresti condividere?",
            "Che bello rivederti, {name}. Hai un\u2019altra storia?",
        ],
        "guided_return": [
            "Bentornato/a, {name}. Un\u2019altra storia da questo capitolo?",
            "Hey {name}, cos\u2019altro ti viene in mente?",
        ],
    },
    "pt": {
        "first": "Ent\u00e3o {name}, vamos come\u00e7ar pelo in\u00edcio \u2014 quando e onde voc\u00ea nasceu?",
        "freeform_new": [
            "Que hist\u00f3ria voc\u00ea gostaria de compartilhar, {name}?",
            "Estou ouvindo, {name}. Sobre o que voc\u00ea quer falar?",
            "Pode come\u00e7ar, {name} \u2014 o que vem \u00e0 mente?",
        ],
        "freeform_return": [
            "Bem-vindo de volta, {name}. O que mais gostaria de compartilhar?",
            "Que bom ter voc\u00ea de volta, {name}. Tem outra hist\u00f3ria?",
        ],
        "guided_return": [
            "Bem-vindo de volta, {name}. Outra hist\u00f3ria deste cap\u00edtulo?",
            "E a\u00ed {name}, o que mais voc\u00ea lembra?",
        ],
    },
    "ja": {
        "first": "{name}\u3055\u3093\u3001\u307e\u305a\u306f\u6700\u521d\u304b\u3089\u59cb\u3081\u307e\u3057\u3087\u3046\u2014\u2014\u3044\u3064\u3001\u3069\u3053\u3067\u751f\u307e\u308c\u307e\u3057\u305f\u304b\uff1f",
        "freeform_new": [
            "{name}\u3055\u3093\u3001\u3069\u3093\u306a\u8a71\u3092\u3057\u305f\u3044\u3067\u3059\u304b\uff1f",
            "\u805e\u304b\u305b\u3066\u304f\u3060\u3055\u3044\u3001{name}\u3055\u3093\u3002\u4f55\u304c\u601d\u3044\u6d6e\u304b\u3073\u307e\u3059\u304b\uff1f",
        ],
        "freeform_return": [
            "\u304a\u304b\u3048\u308a\u306a\u3055\u3044\u3001{name}\u3055\u3093\u3002\u4ed6\u306b\u4f55\u304b\u5171\u6709\u3057\u305f\u3044\u3053\u3068\u306f\uff1f",
            "\u307e\u305f\u4f1a\u3048\u307e\u3057\u305f\u306d\u3001{name}\u3055\u3093\u3002\u6b21\u306e\u8a71\u306f\uff1f",
        ],
        "guided_return": [
            "\u304a\u304b\u3048\u308a\u306a\u3055\u3044\u3001{name}\u3055\u3093\u3002\u3053\u306e\u7ae0\u304b\u3089\u4ed6\u306b\u4f55\u304b\uff1f",
            "{name}\u3055\u3093\u3001\u4ed6\u306b\u4f55\u304b\u601d\u3044\u51fa\u3057\u307e\u3057\u305f\u304b\uff1f",
        ],
    },
    "zh": {
        "first": "{name}\uff0c\u8ba9\u6211\u4eec\u4ece\u5934\u5f00\u59cb\u2014\u2014\u4f60\u662f\u4ec0\u4e48\u65f6\u5019\u3001\u5728\u54ea\u91cc\u51fa\u751f\u7684\uff1f",
        "freeform_new": [
            "{name}\uff0c\u4f60\u60f3\u5206\u4eab\u4ec0\u4e48\u6545\u4e8b\uff1f",
            "\u6211\u5728\u542c\uff0c{name}\u3002\u4f60\u60f3\u804a\u4ec0\u4e48\uff1f",
        ],
        "freeform_return": [
            "\u6b22\u8fce\u56de\u6765\uff0c{name}\u3002\u8fd8\u60f3\u5206\u4eab\u4ec0\u4e48\uff1f",
            "\u5f88\u9ad8\u5174\u4f60\u56de\u6765\u4e86\uff0c{name}\u3002\u8fd8\u6709\u5176\u4ed6\u6545\u4e8b\u5417\uff1f",
        ],
        "guided_return": [
            "\u6b22\u8fce\u56de\u6765\uff0c{name}\u3002\u8fd9\u4e00\u7ae0\u8fd8\u6709\u5176\u4ed6\u6545\u4e8b\u5417\uff1f",
            "{name}\uff0c\u8fd8\u8bb0\u5f97\u4ec0\u4e48\u5417\uff1f",
        ],
    },
    "ko": {
        "first": "{name}\ub2d8, \ucc98\uc74c\ubd80\ud130 \uc2dc\uc791\ud574 \ubcfc\uae4c\uc694 \u2014 \uc5b8\uc81c, \uc5b4\ub514\uc11c \ud0dc\uc5b4\ub0ac\ub098\uc694?",
        "freeform_new": [
            "{name}\ub2d8, \uc5b4\ub5a4 \uc774\uc57c\uae30\ub97c \ub098\ub204\uace0 \uc2f6\uc73c\uc138\uc694?",
            "\ub4e3\uace0 \uc788\uc5b4\uc694, {name}\ub2d8. \ubb34\uc5c7\uc774 \ub5a0\uc624\ub974\uc138\uc694?",
        ],
        "freeform_return": [
            "\ub2e4\uc2dc \uc624\uc168\uad70\uc694, {name}\ub2d8. \ub610 \ub098\ub204\uace0 \uc2f6\uc740 \uc774\uc57c\uae30\uac00 \uc788\uc73c\uc138\uc694?",
        ],
        "guided_return": [
            "\ub2e4\uc2dc \uc624\uc168\uad70\uc694, {name}\ub2d8. \uc774 \ucc55\ud130\uc5d0\uc11c \ub610 \ub2e4\ub978 \uc774\uc57c\uae30\uac00 \uc788\uc73c\uc138\uc694?",
        ],
    },
    "ar": {
        "first": "\u062d\u0633\u0646\u064b\u0627 {name}\u060c \u0644\u0646\u0628\u062f\u0623 \u0645\u0646 \u0627\u0644\u0628\u062f\u0627\u064a\u0629 \u2014 \u0645\u062a\u0649 \u0648\u0623\u064a\u0646 \u0648\u064f\u0644\u062f\u062a\u061f",
        "freeform_new": [
            "\u0645\u0627 \u0627\u0644\u0642\u0635\u0629 \u0627\u0644\u062a\u064a \u062a\u0631\u064a\u062f \u0645\u0634\u0627\u0631\u0643\u062a\u0647\u0627\u060c {name}\u061f",
            "\u0623\u0646\u0627 \u0623\u0633\u062a\u0645\u0639\u060c {name}. \u0639\u0645\u0627 \u062a\u0631\u064a\u062f \u0627\u0644\u062a\u062d\u062f\u062b\u061f",
        ],
        "freeform_return": [
            "\u0623\u0647\u0644\u0627\u064b \u0628\u0639\u0648\u062f\u062a\u0643\u060c {name}. \u0645\u0627\u0630\u0627 \u062a\u0631\u064a\u062f \u0623\u0646 \u062a\u0634\u0627\u0631\u0643 \u0623\u064a\u0636\u064b\u0627\u061f",
        ],
        "guided_return": [
            "\u0623\u0647\u0644\u0627\u064b \u0628\u0639\u0648\u062f\u062a\u0643\u060c {name}. \u0647\u0644 \u0644\u062f\u064a\u0643 \u0642\u0635\u0629 \u0623\u062e\u0631\u0649 \u0645\u0646 \u0647\u0630\u0627 \u0627\u0644\u0641\u0635\u0644\u061f",
        ],
    },
    "hi": {
        "first": "\u0924\u094b {name}, \u0936\u0941\u0930\u0942 \u0938\u0947 \u0936\u0941\u0930\u0942 \u0915\u0930\u0924\u0947 \u0939\u0948\u0902 \u2014 \u0906\u092a\u0915\u093e \u091c\u0928\u094d\u092e \u0915\u092c \u0914\u0930 \u0915\u0939\u093e\u0901 \u0939\u0941\u0906?",
        "freeform_new": [
            "{name}, \u0906\u092a \u0915\u094c\u0928 \u0938\u0940 \u0915\u0939\u093e\u0928\u0940 \u0938\u093e\u091d\u093e \u0915\u0930\u0928\u093e \u091a\u093e\u0939\u0947\u0902\u0917\u0947?",
            "\u092e\u0948\u0902 \u0938\u0941\u0928 \u0930\u0939\u093e \u0939\u0942\u0901, {name}\u0964 \u0915\u094d\u092f\u093e \u092f\u093e\u0926 \u0906 \u0930\u0939\u093e \u0939\u0948?",
        ],
        "freeform_return": [
            "\u0935\u093e\u092a\u0938 \u0938\u094d\u0935\u093e\u0917\u0924, {name}\u0964 \u0914\u0930 \u0915\u094d\u092f\u093e \u0938\u093e\u091d\u093e \u0915\u0930\u0928\u093e \u091a\u093e\u0939\u0947\u0902\u0917\u0947?",
        ],
        "guided_return": [
            "\u0935\u093e\u092a\u0938 \u0938\u094d\u0935\u093e\u0917\u0924, {name}\u0964 \u0907\u0938 \u0905\u0927\u094d\u092f\u093e\u092f \u0938\u0947 \u0915\u094b\u0908 \u0914\u0930 \u0915\u0939\u093e\u0928\u0940?",
        ],
    },
    "ru": {
        "first": "\u0418\u0442\u0430\u043a, {name}, \u0434\u0430\u0432\u0430\u0439\u0442\u0435 \u043d\u0430\u0447\u043d\u0451\u043c \u0441 \u0441\u0430\u043c\u043e\u0433\u043e \u043d\u0430\u0447\u0430\u043b\u0430 \u2014 \u043a\u043e\u0433\u0434\u0430 \u0438 \u0433\u0434\u0435 \u0432\u044b \u0440\u043e\u0434\u0438\u043b\u0438\u0441\u044c?",
        "freeform_new": [
            "\u041a\u0430\u043a\u0443\u044e \u0438\u0441\u0442\u043e\u0440\u0438\u044e \u0432\u044b \u0445\u043e\u0442\u0438\u0442\u0435 \u0440\u0430\u0441\u0441\u043a\u0430\u0437\u0430\u0442\u044c, {name}?",
            "\u0421\u043b\u0443\u0448\u0430\u044e, {name}. \u041e \u0447\u0451\u043c \u0445\u043e\u0442\u0438\u0442\u0435 \u043f\u043e\u0433\u043e\u0432\u043e\u0440\u0438\u0442\u044c?",
        ],
        "freeform_return": [
            "\u0421 \u0432\u043e\u0437\u0432\u0440\u0430\u0449\u0435\u043d\u0438\u0435\u043c, {name}. \u0427\u0442\u043e \u0435\u0449\u0451 \u0445\u043e\u0442\u0438\u0442\u0435 \u0440\u0430\u0441\u0441\u043a\u0430\u0437\u0430\u0442\u044c?",
        ],
        "guided_return": [
            "\u0421 \u0432\u043e\u0437\u0432\u0440\u0430\u0449\u0435\u043d\u0438\u0435\u043c, {name}. \u0415\u0441\u0442\u044c \u0435\u0449\u0451 \u0438\u0441\u0442\u043e\u0440\u0438\u044f \u0438\u0437 \u044d\u0442\u043e\u0439 \u0433\u043b\u0430\u0432\u044b?",
        ],
    },
    "tr": {
        "first": "{name}, en ba\u015f\u0131ndan ba\u015flayal\u0131m \u2014 ne zaman ve nerede do\u011fdun?",
        "freeform_new": [
            "Hangi hikayeyi payla\u015fmak istersin, {name}?",
            "Dinliyorum, {name}. Ne anlatmak istersin?",
        ],
        "freeform_return": [
            "Tekrar ho\u015f geldin, {name}. Ba\u015fka ne payla\u015fmak istersin?",
        ],
        "guided_return": [
            "Tekrar ho\u015f geldin, {name}. Bu b\u00f6l\u00fcmden ba\u015fka bir hikayen var m\u0131?",
        ],
    },
    "nl": {
        "first": "Zo {name}, laten we bij het begin beginnen \u2014 wanneer en waar ben je geboren?",
        "freeform_new": [
            "Welk verhaal wil je delen, {name}?",
            "Ik luister, {name}. Waar wil je over praten?",
        ],
        "freeform_return": [
            "Welkom terug, {name}. Wat wil je nog meer delen?",
        ],
        "guided_return": [
            "Welkom terug, {name}. Nog een verhaal uit dit hoofdstuk?",
        ],
    },
    "pl": {
        "first": "Wi\u0119c {name}, zacznijmy od pocz\u0105tku \u2014 kiedy i gdzie si\u0119 urodzi\u0142e\u015b/a\u015b?",
        "freeform_new": [
            "Jak\u0105 histori\u0119 chcesz opowiedzie\u0107, {name}?",
            "S\u0142ucham, {name}. O czym chcesz porozmawia\u0107?",
        ],
        "freeform_return": [
            "Witaj z powrotem, {name}. Co jeszcze chcesz opowiedzie\u0107?",
        ],
        "guided_return": [
            "Witaj z powrotem, {name}. Masz jeszcze jak\u0105\u015b histori\u0119 z tego rozdzia\u0142u?",
        ],
    },
    "uk": {
        "first": "\u0422\u043e\u0436 {name}, \u043f\u043e\u0447\u043d\u0456\u043c\u043e \u0437 \u043f\u043e\u0447\u0430\u0442\u043a\u0443 \u2014 \u043a\u043e\u043b\u0438 \u0456 \u0434\u0435 \u0432\u0438 \u043d\u0430\u0440\u043e\u0434\u0438\u043b\u0438\u0441\u044f?",
        "freeform_new": ["\u042f\u043a\u0443 \u0456\u0441\u0442\u043e\u0440\u0456\u044e \u0432\u0438 \u0445\u043e\u0447\u0435\u0442\u0435 \u0440\u043e\u0437\u043f\u043e\u0432\u0456\u0441\u0442\u0438, {name}?"],
        "freeform_return": ["\u0417 \u043f\u043e\u0432\u0435\u0440\u043d\u0435\u043d\u043d\u044f\u043c, {name}. \u0429\u043e \u0449\u0435 \u0445\u043e\u0447\u0435\u0442\u0435 \u0440\u043e\u0437\u043f\u043e\u0432\u0456\u0441\u0442\u0438?"],
        "guided_return": ["\u0417 \u043f\u043e\u0432\u0435\u0440\u043d\u0435\u043d\u043d\u044f\u043c, {name}. \u0404 \u0449\u0435 \u0456\u0441\u0442\u043e\u0440\u0456\u044f \u0437 \u0446\u044c\u043e\u0433\u043e \u0440\u043e\u0437\u0434\u0456\u043b\u0443?"],
    },
    "sv": {
        "first": "S\u00e5 {name}, l\u00e5t oss b\u00f6rja fr\u00e5n b\u00f6rjan \u2014 n\u00e4r och var \u00e4r du f\u00f6dd?",
        "freeform_new": ["Vilken ber\u00e4ttelse vill du dela, {name}?"],
        "freeform_return": ["V\u00e4lkommen tillbaka, {name}. Vad mer vill du ber\u00e4tta?"],
        "guided_return": ["V\u00e4lkommen tillbaka, {name}. N\u00e5gon mer ber\u00e4ttelse fr\u00e5n det h\u00e4r kapitlet?"],
    },
    "da": {
        "first": "S\u00e5 {name}, lad os starte fra begyndelsen \u2014 hvorn\u00e5r og hvor er du f\u00f8dt?",
        "freeform_new": ["Hvilken historie vil du dele, {name}?"],
        "freeform_return": ["Velkommen tilbage, {name}. Hvad mere vil du fort\u00e6lle?"],
        "guided_return": ["Velkommen tilbage, {name}. Endnu en historie fra dette kapitel?"],
    },
    "fi": {
        "first": "No niin {name}, aloitetaan alusta \u2014 milloin ja miss\u00e4 synnyit?",
        "freeform_new": ["Mink\u00e4 tarinan haluaisit jakaa, {name}?"],
        "freeform_return": ["Tervetuloa takaisin, {name}. Mit\u00e4 muuta haluaisit kertoa?"],
        "guided_return": ["Tervetuloa takaisin, {name}. Viel\u00e4 yksi tarina t\u00e4st\u00e4 luvusta?"],
    },
    "no": {
        "first": "S\u00e5 {name}, la oss starte fra begynnelsen \u2014 n\u00e5r og hvor ble du f\u00f8dt?",
        "freeform_new": ["Hvilken historie vil du dele, {name}?"],
        "freeform_return": ["Velkommen tilbake, {name}. Hva mer vil du fortelle?"],
        "guided_return": ["Velkommen tilbake, {name}. En historie til fra dette kapittelet?"],
    },
    "ro": {
        "first": "Ei bine {name}, s\u0103 \u00eencepem de la \u00eenceput \u2014 c\u00e2nd \u0219i unde te-ai n\u0103scut?",
        "freeform_new": ["Ce poveste ai vrea s\u0103 \u00eempart\u0103\u0219e\u0219ti, {name}?"],
        "freeform_return": ["Bine ai revenit, {name}. Ce altceva ai vrea s\u0103 \u00eempart\u0103\u0219e\u0219ti?"],
        "guided_return": ["Bine ai revenit, {name}. Mai ai o poveste din acest capitol?"],
    },
    "el": {
        "first": "\u039b\u03bf\u03b9\u03c0\u03cc\u03bd {name}, \u03b1\u03c2 \u03be\u03b5\u03ba\u03b9\u03bd\u03ae\u03c3\u03bf\u03c5\u03bc\u03b5 \u03b1\u03c0\u03cc \u03c4\u03b7\u03bd \u03b1\u03c1\u03c7\u03ae \u2014 \u03c0\u03cc\u03c4\u03b5 \u03ba\u03b1\u03b9 \u03c0\u03bf\u03cd \u03b3\u03b5\u03bd\u03bd\u03ae\u03b8\u03b7\u03ba\u03b5\u03c2;",
        "freeform_new": ["\u03a0\u03bf\u03b9\u03b1 \u03b9\u03c3\u03c4\u03bf\u03c1\u03af\u03b1 \u03b8\u03b1 \u03ae\u03b8\u03b5\u03bb\u03b5\u03c2 \u03bd\u03b1 \u03bc\u03bf\u03b9\u03c1\u03b1\u03c3\u03c4\u03b5\u03af\u03c2, {name};"],
        "freeform_return": ["\u039a\u03b1\u03bb\u03ce\u03c2 \u03ae\u03c1\u03b8\u03b5\u03c2 \u03c0\u03af\u03c3\u03c9, {name}. \u03a4\u03b9 \u03ac\u03bb\u03bb\u03bf \u03b8\u03b1 \u03ae\u03b8\u03b5\u03bb\u03b5\u03c2 \u03bd\u03b1 \u03bc\u03bf\u03b9\u03c1\u03b1\u03c3\u03c4\u03b5\u03af\u03c2;"],
        "guided_return": ["\u039a\u03b1\u03bb\u03ce\u03c2 \u03ae\u03c1\u03b8\u03b5\u03c2 \u03c0\u03af\u03c3\u03c9, {name}. \u0386\u03bb\u03bb\u03b7 \u03b9\u03c3\u03c4\u03bf\u03c1\u03af\u03b1 \u03b1\u03c0\u03cc \u03b1\u03c5\u03c4\u03cc \u03c4\u03bf \u03ba\u03b5\u03c6\u03ac\u03bb\u03b1\u03b9\u03bf;"],
    },
    "cs": {
        "first": "Tak\u017ee {name}, za\u010dn\u011bme od za\u010d\u00e1tku \u2014 kdy a kde jste se narodil/a?",
        "freeform_new": ["Jak\u00fd p\u0159\u00edb\u011bh byste cht\u011bl/a sd\u00edlet, {name}?"],
        "freeform_return": ["V\u00edtejte zp\u011bt, {name}. Co dal\u0161\u00edho byste cht\u011bl/a vypr\u00e1v\u011bt?"],
        "guided_return": ["V\u00edtejte zp\u011bt, {name}. Je\u0161t\u011b n\u011bjak\u00fd p\u0159\u00edb\u011bh z t\u00e9to kapitoly?"],
    },
    "sk": {
        "first": "Tak\u017ee {name}, za\u010dnime od za\u010diatku \u2014 kedy a kde ste sa narodili?",
        "freeform_new": ["Ak\u00fd pr\u00edbeh by ste chceli zdie\u013ea\u0165, {name}?"],
        "freeform_return": ["Vitajte sp\u00e4\u0165, {name}. \u010co \u010fal\u0161ie by ste chceli porozpr\u00e1va\u0165?"],
        "guided_return": ["Vitajte sp\u00e4\u0165, {name}. E\u0161te nejak\u00fd pr\u00edbeh z tejto kapitoly?"],
    },
    "bg": {
        "first": "\u0418 \u0442\u0430\u043a\u0430 {name}, \u0434\u0430 \u0437\u0430\u043f\u043e\u0447\u043d\u0435\u043c \u043e\u0442\u043d\u0430\u0447\u0430\u043b\u043e \u2014 \u043a\u043e\u0433\u0430 \u0438 \u043a\u044a\u0434\u0435 \u0441\u0438 \u0440\u043e\u0434\u0435\u043d/\u0430?",
        "freeform_new": ["\u041a\u0430\u043a\u0432\u0430 \u0438\u0441\u0442\u043e\u0440\u0438\u044f \u0438\u0441\u043a\u0430\u0448 \u0434\u0430 \u0441\u043f\u043e\u0434\u0435\u043b\u0438\u0448, {name}?"],
        "freeform_return": ["\u0414\u043e\u0431\u0440\u0435 \u0434\u043e\u0448\u044a\u043b \u043e\u0431\u0440\u0430\u0442\u043d\u043e, {name}. \u041a\u0430\u043a\u0432\u043e \u0434\u0440\u0443\u0433\u043e \u0438\u0441\u043a\u0430\u0448 \u0434\u0430 \u0440\u0430\u0437\u043a\u0430\u0436\u0435\u0448?"],
        "guided_return": ["\u0414\u043e\u0431\u0440\u0435 \u0434\u043e\u0448\u044a\u043b \u043e\u0431\u0440\u0430\u0442\u043d\u043e, {name}. \u0418\u043c\u0430 \u043b\u0438 \u0434\u0440\u0443\u0433\u0430 \u0438\u0441\u0442\u043e\u0440\u0438\u044f \u043e\u0442 \u0442\u0430\u0437\u0438 \u0433\u043b\u0430\u0432\u0430?"],
    },
    "hr": {
        "first": "Dakle {name}, krenimo od po\u010detka \u2014 kada i gdje si ro\u0111en/a?",
        "freeform_new": ["Koju pri\u010du \u017eeli\u0161 podijeliti, {name}?"],
        "freeform_return": ["Dobro do\u0161ao/la natrag, {name}. \u0160to jo\u0161 \u017eeli\u0161 ispri\u010dati?"],
        "guided_return": ["Dobro do\u0161ao/la natrag, {name}. Jo\u0161 jedna pri\u010da iz ovog poglavlja?"],
    },
    "hu": {
        "first": "Nos {name}, kezdj\u00fck az elej\u00e9n \u2014 mikor \u00e9s hol sz\u00fclett\u00e9l?",
        "freeform_new": ["Milyen t\u00f6rt\u00e9netet szeretn\u00e9l megosztani, {name}?"],
        "freeform_return": ["\u00ddjra itt vagy, {name}. Mit szeretn\u00e9l m\u00e9g megosztani?"],
        "guided_return": ["\u00ddjra itt vagy, {name}. Van m\u00e9g egy t\u00f6rt\u00e9neted ebb\u0151l a fejezetb\u0151l?"],
    },
    "ta": {
        "first": "{name}, \u0ba4\u0bc1\u0bb5\u0b95\u0bcd\u0b95\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b87\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0bc7 \u0ba4\u0bca\u0b9f\u0b99\u0bcd\u0b95\u0bc1\u0bb5\u0bcb\u0bae\u0bcd \u2014 \u0ba8\u0bc0\u0b99\u0bcd\u0b95\u0bb3\u0bcd \u0b8e\u0baa\u0bcd\u0baa\u0bcb\u0ba4\u0bc1, \u0b8e\u0b99\u0bcd\u0b95\u0bc7 \u0baa\u0bbf\u0bb1\u0ba8\u0bcd\u0ba4\u0bc0\u0bb0\u0bcd\u0b95\u0bb3\u0bcd?",
        "freeform_new": ["\u0b8e\u0ba8\u0bcd\u0ba4 \u0b95\u0ba4\u0bc8\u0baf\u0bc8 \u0baa\u0b95\u0bbf\u0bb0 \u0bb5\u0bbf\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1\u0b95\u0bbf\u0bb1\u0bc0\u0bb0\u0bcd\u0b95\u0bb3\u0bcd, {name}?"],
        "freeform_return": ["\u0bae\u0bc0\u0ba3\u0bcd\u0b9f\u0bc1\u0bae\u0bcd \u0bb5\u0bb0\u0bb5\u0bc7\u0bb1\u0bcd\u0b95\u0bbf\u0bb1\u0bc7\u0ba9\u0bcd, {name}. \u0bb5\u0bc7\u0bb1\u0bc1 \u0b8e\u0ba9\u0bcd\u0ba9 \u0baa\u0b95\u0bbf\u0bb0 \u0bb5\u0bbf\u0bb0\u0bc1\u0bae\u0bcd\u0baa\u0bc1\u0b95\u0bbf\u0bb1\u0bc0\u0bb0\u0bcd\u0b95\u0bb3\u0bcd?"],
        "guided_return": ["\u0bae\u0bc0\u0ba3\u0bcd\u0b9f\u0bc1\u0bae\u0bcd \u0bb5\u0bb0\u0bb5\u0bc7\u0bb1\u0bcd\u0b95\u0bbf\u0bb1\u0bc7\u0ba9\u0bcd, {name}. \u0b87\u0ba8\u0bcd\u0ba4 \u0b85\u0ba4\u0bcd\u0ba4\u0bbf\u0baf\u0bbe\u0baf\u0ba4\u0bcd\u0ba4\u0bbf\u0bb2\u0bcd \u0b87\u0bb0\u0bc1\u0ba8\u0bcd\u0ba4\u0bc1 \u0bb5\u0bc7\u0bb1\u0bc1 \u0b95\u0ba4\u0bc8?"],
    },
    "id": {
        "first": "Jadi {name}, mari mulai dari awal \u2014 kapan dan di mana kamu lahir?",
        "freeform_new": ["Cerita apa yang ingin kamu bagikan, {name}?"],
        "freeform_return": ["Selamat datang kembali, {name}. Apa lagi yang ingin kamu ceritakan?"],
        "guided_return": ["Selamat datang kembali, {name}. Ada cerita lain dari bab ini?"],
    },
    "ms": {
        "first": "Jadi {name}, mari kita mula dari awal \u2014 bila dan di mana anda dilahirkan?",
        "freeform_new": ["Cerita apa yang anda ingin kongsi, {name}?"],
        "freeform_return": ["Selamat kembali, {name}. Apa lagi yang ingin anda kongsi?"],
        "guided_return": ["Selamat kembali, {name}. Ada cerita lain dari bab ini?"],
    },
    "fil": {
        "first": "So {name}, magsimula tayo sa pinakasimula \u2014 kailan at saan ka ipinanganak?",
        "freeform_new": ["Anong kuwento ang gusto mong ibahagi, {name}?"],
        "freeform_return": ["Welcome back, {name}. Ano pa ang gusto mong ikuwento?"],
        "guided_return": ["Welcome back, {name}. May iba pa bang kuwento mula sa kabanatang ito?"],
    },
    "vi": {
        "first": "V\u1eady {name}, h\u00e3y b\u1eaft \u0111\u1ea7u t\u1eeb \u0111\u1ea7u nh\u00e9 \u2014 b\u1ea1n sinh khi n\u00e0o v\u00e0 \u1edf \u0111\u00e2u?",
        "freeform_new": ["B\u1ea1n mu\u1ed1n chia s\u1ebb c\u00e2u chuy\u1ec7n g\u00ec, {name}?"],
        "freeform_return": ["Ch\u00e0o m\u1eebng tr\u1edf l\u1ea1i, {name}. B\u1ea1n c\u00f2n mu\u1ed1n k\u1ec3 g\u00ec n\u1eefa kh\u00f4ng?"],
        "guided_return": ["Ch\u00e0o m\u1eebng tr\u1edf l\u1ea1i, {name}. C\u00f2n c\u00e2u chuy\u1ec7n n\u00e0o kh\u00e1c t\u1eeb ch\u01b0\u01a1ng n\u00e0y kh\u00f4ng?"],
    },
    "th": {
        "first": "{name} \u0e40\u0e23\u0e32\u0e40\u0e23\u0e34\u0e48\u0e21\u0e01\u0e31\u0e19\u0e15\u0e31\u0e49\u0e07\u0e41\u0e15\u0e48\u0e15\u0e49\u0e19\u0e40\u0e25\u0e22\u0e19\u0e30 \u2014 \u0e04\u0e38\u0e13\u0e40\u0e01\u0e34\u0e14\u0e40\u0e21\u0e37\u0e48\u0e2d\u0e44\u0e2b\u0e23\u0e48\u0e41\u0e25\u0e30\u0e17\u0e35\u0e48\u0e44\u0e2b\u0e19?",
        "freeform_new": ["\u0e04\u0e38\u0e13\u0e2d\u0e22\u0e32\u0e01\u0e40\u0e25\u0e48\u0e32\u0e40\u0e23\u0e37\u0e48\u0e2d\u0e07\u0e2d\u0e30\u0e44\u0e23, {name}?"],
        "freeform_return": ["\u0e22\u0e34\u0e19\u0e14\u0e35\u0e15\u0e49\u0e2d\u0e19\u0e23\u0e31\u0e1a\u0e01\u0e25\u0e31\u0e1a\u0e21\u0e32, {name} \u0e2d\u0e22\u0e32\u0e01\u0e40\u0e25\u0e48\u0e32\u0e2d\u0e30\u0e44\u0e23\u0e40\u0e1e\u0e34\u0e48\u0e21\u0e40\u0e15\u0e34\u0e21\u0e44\u0e2b\u0e21?"],
        "guided_return": ["\u0e22\u0e34\u0e19\u0e14\u0e35\u0e15\u0e49\u0e2d\u0e19\u0e23\u0e31\u0e1a\u0e01\u0e25\u0e31\u0e1a\u0e21\u0e32, {name} \u0e21\u0e35\u0e40\u0e23\u0e37\u0e48\u0e2d\u0e07\u0e2d\u0e37\u0e48\u0e19\u0e08\u0e32\u0e01\u0e1a\u0e17\u0e19\u0e35\u0e49\u0e44\u0e2b\u0e21?"],
    },
}


def _get_opener(language: str, key: str, name: str) -> str:
    """Get a pre-written opener in the given language. Falls back to English."""
    lang_data = _OPENERS.get(language, _OPENERS["en"])
    if key == "first":
        return lang_data["first"].format(name=name)
    options = lang_data.get(key, _OPENERS["en"][key])
    return random.choice(options).format(name=name)


def get_opening_message(
    chapter_index: int,
    person_name: str,
    prior_context: list[str] | None = None,
    custom_chapter_title: str | None = None,
    language: str = "en",
) -> str:
    """Generate the AI's opening message for a new chapter conversation.

    Always returns a pre-written opener instantly (no LLM call).
    Openers are available in all 33 supported languages.
    """
    has_prior = prior_context and len(prior_context) > 0
    lang = language or "en"

    # First guided chapter, first time
    if chapter_index == 0 and not has_prior and custom_chapter_title is None:
        return _get_opener(lang, "first", person_name)

    # Freeform / custom chapter / open-ended stories
    if custom_chapter_title is not None or chapter_index == -1:
        key = "freeform_return" if has_prior else "freeform_new"
        return _get_opener(lang, key, person_name)

    # Guided chapter with prior stories (additional story in same chapter)
    if has_prior:
        return _get_opener(lang, "guided_return", person_name)

    # Guided chapter, first time (chapters 1+) — use the chapter's first question
    chapter = CHAPTERS[chapter_index]
    first_q = chapter["questions"][0]["text"]
    return f"{person_name}, {first_q.lower()}" if first_q[0].isupper() else f"{person_name}, {first_q}"


def chat(
    person_name: str,
    chapter_index: int,
    messages: list[dict],
    user_message: str,
    prior_context: list[str] | None = None,
    custom_chapter_title: str | None = None,
    language: str = "en",
) -> tuple[str, list[dict]]:
    """Send a message and get AI response. Returns (ai_response, updated_messages)."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    # Append user message
    messages.append({"role": "user", "content": user_message, "timestamp": now})

    # For custom chapters, use freeform prompt
    effective_index = -1 if custom_chapter_title is not None else chapter_index
    existing_answers = extract_answers(effective_index, messages)
    system = _build_system_prompt(effective_index, person_name, existing_answers, prior_context, language=language)
    model = llm.get_model(MODEL_ID)

    # Build the LLM conversation
    conversation = model.conversation()
    conversation.system = system

    # Replay prior messages through the conversation
    # The llm library's conversation.prompt() adds messages sequentially,
    # so we need to build the conversation from scratch each time.
    # Instead, we'll use a single prompt call with the full history in the system.
    history_text = ""
    for msg in messages[:-1]:  # all except the latest user message
        role_label = "You" if msg["role"] == "assistant" else person_name
        history_text += f"{role_label}: {msg['content']}\n\n"

    full_prompt = user_message
    if history_text:
        system += f"\n\nConversation so far:\n{history_text}\n{person_name}'s latest message follows."

    response = model.prompt(full_prompt, system=system)
    ai_text = response.text().strip()

    # Polish the user's message for the book
    user_msg = messages[-1]  # the user message we just appended
    polished = polish_message(user_msg["content"], language=language)
    if polished != user_msg["content"]:
        user_msg["polished"] = polished

    messages.append({"role": "assistant", "content": ai_text, "timestamp": now})
    return ai_text, messages


def extract_answers(chapter_index: int, messages: list[dict]) -> dict:
    """Extract structured answers from conversation transcript."""
    if not messages:
        return {}

    # Build transcript
    transcript = ""
    for msg in messages:
        label = "Interviewer" if msg["role"] == "assistant" else "Person"
        transcript += f"{label}: {msg['content']}\n\n"

    system = _build_extraction_prompt(chapter_index)
    model = llm.get_model(MODEL_ID)

    try:
        response = model.prompt(transcript, system=system)
        raw = response.text().strip()
        # Handle markdown code blocks
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.strip()
        answers = json.loads(raw)
        if isinstance(answers, dict):
            return {k: v for k, v in answers.items() if isinstance(v, str) and v.strip()}
    except Exception as e:
        logger.warning("Answer extraction failed: %s", e)

    return {}


def polish_message(text: str, language: str = "en") -> str:
    """Clean up a spoken/transcribed message for readability. Preserves meaning and voice."""
    model = llm.get_model(MODEL_ID)
    lang_name = LANGUAGE_NAMES.get(language, "English") if language and language != "en" else ""
    lang_note = f" The text is in {lang_name} — keep it in {lang_name}." if lang_name else ""
    system = f"""Lightly clean up this transcribed speech for a life story book. Fix grammar, remove filler words (um, uh, like, you know), and improve sentence structure. Keep the person's voice and personality — don't make it formal or literary. Keep it in first person. If it's already clean, return it unchanged. Return ONLY the cleaned text, nothing else.{lang_note}"""
    try:
        response = model.prompt(text, system=system)
        polished = response.text().strip()
        return polished if polished else text
    except Exception as e:
        logger.warning("Polish failed: %s", e)
        return text
