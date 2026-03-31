"""ElevenLabs speech services — TTS and STT. Zero external dependencies."""

import io
import json
import os
import urllib.request
import urllib.error
import logging
import uuid

logger = logging.getLogger(__name__)

API_BASE = "https://api.elevenlabs.io/v1"
API_URL = f"{API_BASE}/text-to-speech"
STT_URL = f"{API_BASE}/speech-to-text"

# Rachel — calm, warm, good for narration
DEFAULT_VOICE_ID = "21m00Tcm4TlvDq8ikWAM"
REQUEST_TIMEOUT = 30  # seconds


class TTSError(Exception):
    pass


def get_api_key() -> str:
    key = os.getenv("ELEVENLABS_API_KEY")
    if not key:
        raise TTSError("Missing ELEVENLABS_API_KEY environment variable.")
    return key


def synthesize(text: str, voice_id: str | None = None) -> bytes:
    """Convert text to speech. Returns MP3 audio bytes."""
    api_key = get_api_key()
    vid = voice_id or DEFAULT_VOICE_ID

    payload = json.dumps({
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {
            "stability": 0.6,
            "similarity_boost": 0.75,
            "speed": 0.92,
        },
    }).encode("utf-8")

    req = urllib.request.Request(
        f"{API_URL}/{vid}",
        data=payload,
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            return resp.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        logger.warning("ElevenLabs API error %s: %s", e.code, body)
        raise TTSError(f"ElevenLabs API returned {e.code}") from e
    except urllib.error.URLError as e:
        raise TTSError(f"Could not reach ElevenLabs API: {e.reason}") from e


def transcribe(audio_data: bytes, filename: str = "audio.webm") -> str:
    """Transcribe audio using ElevenLabs Scribe. Returns text."""
    api_key = get_api_key()

    # Build multipart/form-data by hand (no extra deps)
    boundary = uuid.uuid4().hex
    body = io.BytesIO()

    # audio file part — ElevenLabs expects the field name "file"
    body.write(f"--{boundary}\r\n".encode())
    body.write(f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'.encode())
    body.write(b"Content-Type: application/octet-stream\r\n\r\n")
    body.write(audio_data)
    body.write(b"\r\n")

    # model_id part
    body.write(f"--{boundary}\r\n".encode())
    body.write(b'Content-Disposition: form-data; name="model_id"\r\n\r\n')
    body.write(b"scribe_v1")
    body.write(b"\r\n")

    body.write(f"--{boundary}--\r\n".encode())

    req = urllib.request.Request(
        STT_URL,
        data=body.getvalue(),
        headers={
            "xi-api-key": api_key,
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            text = result.get("text", "").strip()
            if not text:
                raise TTSError("ElevenLabs returned empty transcription.")
            return text
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        logger.warning("ElevenLabs STT error %s: %s", e.code, error_body)
        raise TTSError(f"ElevenLabs STT returned {e.code}") from e
    except urllib.error.URLError as e:
        raise TTSError(f"Could not reach ElevenLabs API: {e.reason}") from e
