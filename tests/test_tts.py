"""Unit tests for storyteller.tts — ElevenLabs TTS and STT wrappers.

All network calls are mocked via unittest.mock.patch so tests run offline.
"""

import io
import json
import urllib.error
import urllib.request
from unittest.mock import MagicMock, patch

import pytest

import storyteller.tts as tts
from storyteller.tts import TTSError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_response(body: bytes, status: int = 200) -> MagicMock:
    """Return a context-manager-compatible mock for urllib.request.urlopen."""
    resp = MagicMock()
    resp.read.return_value = body
    resp.status = status
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def _http_error(code: int, body: bytes = b"error detail") -> urllib.error.HTTPError:
    return urllib.error.HTTPError(
        url="https://api.elevenlabs.io/v1/text-to-speech/voice",
        code=code,
        msg="Error",
        hdrs={},  # type: ignore[arg-type]
        fp=io.BytesIO(body),
    )


# ---------------------------------------------------------------------------
# get_api_key
# ---------------------------------------------------------------------------

class TestGetApiKey:
    def test_returns_key_when_set(self, monkeypatch):
        monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key-123")
        assert tts.get_api_key() == "test-key-123"

    def test_raises_when_missing(self, monkeypatch):
        monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
        with pytest.raises(TTSError, match="Missing ELEVENLABS_API_KEY"):
            tts.get_api_key()


# ---------------------------------------------------------------------------
# synthesize
# ---------------------------------------------------------------------------

class TestSynthesize:
    @pytest.fixture(autouse=True)
    def set_api_key(self, monkeypatch):
        monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")

    def test_returns_audio_bytes_on_success(self):
        audio = b"\xff\xfb\x90mock-mp3-data"
        mock_resp = _make_response(audio)
        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            result = tts.synthesize("Hello world")
        assert result == audio
        mock_open.assert_called_once()

    def test_uses_default_voice_when_none_provided(self):
        mock_resp = _make_response(b"audio")
        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            tts.synthesize("Hi")
        req = mock_open.call_args[0][0]
        assert tts.DEFAULT_VOICE_ID in req.full_url

    def test_uses_custom_voice_id(self):
        mock_resp = _make_response(b"audio")
        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            tts.synthesize("Hi", voice_id="custom-voice-xyz")
        req = mock_open.call_args[0][0]
        assert "custom-voice-xyz" in req.full_url

    def test_request_has_correct_headers(self):
        mock_resp = _make_response(b"audio")
        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            tts.synthesize("Test")
        req = mock_open.call_args[0][0]
        assert req.get_header("Xi-api-key") == "test-key"
        assert req.get_header("Content-type") == "application/json"
        assert req.get_header("Accept") == "audio/mpeg"

    def test_request_payload_contains_text(self):
        mock_resp = _make_response(b"audio")
        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            tts.synthesize("My story text")
        req = mock_open.call_args[0][0]
        payload = json.loads(req.data.decode("utf-8"))
        assert payload["text"] == "My story text"
        assert payload["model_id"] == "eleven_multilingual_v2"
        assert "voice_settings" in payload

    def test_uses_post_method(self):
        mock_resp = _make_response(b"audio")
        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            tts.synthesize("Hello")
        req = mock_open.call_args[0][0]
        assert req.method == "POST"

    def test_raises_tts_error_on_http_error(self):
        with patch("urllib.request.urlopen", side_effect=_http_error(401)):
            with pytest.raises(TTSError, match="401"):
                tts.synthesize("Hello")

    def test_raises_tts_error_on_http_429(self):
        with patch("urllib.request.urlopen", side_effect=_http_error(429, b"rate limited")):
            with pytest.raises(TTSError, match="429"):
                tts.synthesize("Hello")

    def test_raises_tts_error_on_url_error(self):
        url_err = urllib.error.URLError(reason="Name or service not known")
        with patch("urllib.request.urlopen", side_effect=url_err):
            with pytest.raises(TTSError, match="Could not reach ElevenLabs"):
                tts.synthesize("Hello")

    def test_raises_tts_error_when_no_api_key(self, monkeypatch):
        monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
        with pytest.raises(TTSError, match="Missing ELEVENLABS_API_KEY"):
            tts.synthesize("Hello")


# ---------------------------------------------------------------------------
# transcribe
# ---------------------------------------------------------------------------

class TestTranscribe:
    @pytest.fixture(autouse=True)
    def set_api_key(self, monkeypatch):
        monkeypatch.setenv("ELEVENLABS_API_KEY", "test-key")

    def test_returns_transcribed_text(self):
        response_body = json.dumps({"text": "  Hello world  "}).encode()
        mock_resp = _make_response(response_body)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            result = tts.transcribe(b"audio-data")
        assert result == "Hello world"

    def test_request_sent_to_stt_url(self):
        response_body = json.dumps({"text": "text"}).encode()
        mock_resp = _make_response(response_body)
        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            tts.transcribe(b"audio")
        req = mock_open.call_args[0][0]
        assert req.full_url == tts.STT_URL

    def test_request_uses_post(self):
        response_body = json.dumps({"text": "hi"}).encode()
        mock_resp = _make_response(response_body)
        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            tts.transcribe(b"audio")
        req = mock_open.call_args[0][0]
        assert req.method == "POST"

    def test_request_includes_api_key_header(self):
        response_body = json.dumps({"text": "hi"}).encode()
        mock_resp = _make_response(response_body)
        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            tts.transcribe(b"audio")
        req = mock_open.call_args[0][0]
        assert req.get_header("Xi-api-key") == "test-key"

    def test_request_body_contains_audio_and_model_id(self):
        audio_data = b"raw-audio-bytes"
        response_body = json.dumps({"text": "spoken words"}).encode()
        mock_resp = _make_response(response_body)
        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            tts.transcribe(audio_data, filename="recording.webm")
        req = mock_open.call_args[0][0]
        body = req.data
        assert b"recording.webm" in body
        assert audio_data in body
        assert b"scribe_v1" in body
        assert b"model_id" in body

    def test_multipart_content_type_header(self):
        response_body = json.dumps({"text": "hi"}).encode()
        mock_resp = _make_response(response_body)
        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            tts.transcribe(b"audio")
        req = mock_open.call_args[0][0]
        content_type = req.get_header("Content-type")
        assert content_type.startswith("multipart/form-data; boundary=")

    def test_raises_on_empty_transcription(self):
        response_body = json.dumps({"text": "   "}).encode()
        mock_resp = _make_response(response_body)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            with pytest.raises(TTSError, match="empty transcription"):
                tts.transcribe(b"audio")

    def test_raises_on_missing_text_key(self):
        response_body = json.dumps({}).encode()
        mock_resp = _make_response(response_body)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            with pytest.raises(TTSError, match="empty transcription"):
                tts.transcribe(b"audio")

    def test_raises_tts_error_on_http_error(self):
        stt_err = urllib.error.HTTPError(
            url=tts.STT_URL,
            code=400,
            msg="Bad Request",
            hdrs={},  # type: ignore[arg-type]
            fp=io.BytesIO(b"bad audio format"),
        )
        with patch("urllib.request.urlopen", side_effect=stt_err):
            with pytest.raises(TTSError, match="400"):
                tts.transcribe(b"audio")

    def test_raises_tts_error_on_url_error(self):
        url_err = urllib.error.URLError(reason="Network unreachable")
        with patch("urllib.request.urlopen", side_effect=url_err):
            with pytest.raises(TTSError, match="Could not reach ElevenLabs"):
                tts.transcribe(b"audio")

    def test_raises_when_no_api_key(self, monkeypatch):
        monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)
        with pytest.raises(TTSError, match="Missing ELEVENLABS_API_KEY"):
            tts.transcribe(b"audio")
