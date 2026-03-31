from __future__ import annotations

from pathlib import Path
from typing import Optional

from openai import OpenAI
import os
import shutil
import subprocess


class TranscriptionError(Exception):
    pass


def get_openai_client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise TranscriptionError(
            "Missing OPENAI_API_KEY. Set it in your environment or .env file."
        )
    return OpenAI(api_key=api_key)


def _transcribe_with_llm_cli(audio_path: Path) -> Optional[str]:
    """
    Try to transcribe using `llm whisper-api` CLI.
    Returns text on success, or None if llm is not available.
    Raises TranscriptionError on CLI execution errors.
    """
    llm_path = shutil.which("llm")
    if not llm_path:
        return None

    api_key = os.getenv("OPENAI_API_KEY")
    cmd = [llm_path, "whisper-api", str(audio_path)]
    if api_key:
        cmd.extend(["--key", api_key])

    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.strip() if e.stderr else "unknown error"
        raise TranscriptionError(f"llm whisper-api failed: {stderr}") from e
    text = (result.stdout or "").strip()
    if not text:
        raise TranscriptionError("llm whisper-api returned empty output.")
    return text


def transcribe_audio_file(audio_path: Path, *, model: str = "gpt-4o-mini-transcribe") -> str:
    if not audio_path.exists() or not audio_path.is_file():
        raise TranscriptionError(f"Audio file not found: {audio_path}")

    use_cli_first = os.getenv("USE_LLM_WHISPER_API", "1") not in ("0", "false", "False")
    if use_cli_first:
        cli_text = _transcribe_with_llm_cli(audio_path)
        if isinstance(cli_text, str):
            return cli_text

    client = get_openai_client()
    try:
        with audio_path.open("rb") as f:
            resp = client.audio.transcriptions.create(
                model=model,
                file=f,
                response_format="text",
            )
    except Exception as e:
        raise TranscriptionError(str(e)) from e

    text: Optional[str] = resp  # type: ignore[assignment]
    if not text or not isinstance(text, str):
        raise TranscriptionError("Empty transcription result.")
    return text.strip()
