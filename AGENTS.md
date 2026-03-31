# Share Your Story — Development Notes

## Project vision

A conversational storytelling app that captures life stories through natural AI interviews. 10 guided life chapters plus freeform mode, voice-first with 33-language support, stories viewable as a book and exportable as reels or audiobooks.

## Development instructions

1. Run code in the uv-based `.venv` in `backend/`
2. Do not merge directly into `main` — always create PRs
3. Use existing code and external dependencies; don't reimplement
4. Use `sqlite-utils` for database operations, not raw SQL

## Key technical notes

- **Model ID**: `llm-anthropic` requires the `anthropic/` prefix: `anthropic/claude-sonnet-4-6`. Short aliases like `claude-opus-4.6` may work for some models but not all.
- **API keys**: `.env` file at project root (auto-loaded by server.py). Keys: `ANTHROPIC_API_KEY`, `ELEVENLABS_API_KEY`.
- **DB location**: `stories.db` at repo root. `DB_PATH` in `db.py` resolves via `Path(__file__).resolve().parent.parent.parent / "stories.db"`.
- **Deployment**: Vercel (backend API) + GitHub Pages (frontend). `sys.path` insert in `server.py` ensures `storyteller` is importable on Vercel.
- **Frontend env**: `VITE_API_URL` in `.env.development` / `.env.production` controls the API base URL.
- **Chapter data duplication**: Questions are defined in both `frontend/src/data/chapters.js` and `backend/storyteller/conversation.py`. Keep them in sync.
- **Instant openers**: `get_opening_message()` returns pre-written strings in all 33 languages — no LLM call. Translations are in the `_OPENERS` dict in `conversation.py`.
- **ElevenLabs**: TTS uses `eleven_multilingual_v2` (auto-detects language from text). STT uses Scribe v1 (auto-detects spoken language). No language param needed for either.
- **Flask port**: Use port 5050 (not 5000).
- **Reel generation**: Requires `ffmpeg` on the system, `pillow` and `ffmpeg-python` in requirements. Background video at `assets/background.mp4`.
