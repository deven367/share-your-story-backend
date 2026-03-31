"""Tests for storyteller.ai — LLM-powered title and tag generation (mocked)."""

from unittest.mock import MagicMock, patch

from storyteller import ai


class TestIsAvailable:
    @patch("storyteller.ai._get_model")
    def test_returns_true_when_model_exists(self, mock_get):
        mock_get.return_value = MagicMock()
        assert ai.is_available() is True

    @patch("storyteller.ai._get_model", side_effect=ai.llm.UnknownModelError("nope"))
    def test_returns_false_when_model_missing(self, mock_get):
        assert ai.is_available() is False


class TestGenerateTitle:
    @patch("storyteller.ai._get_model")
    def test_returns_cleaned_title(self, mock_get):
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text.return_value = '  "A Quiet Dawn"  '
        mock_model.prompt.return_value = mock_response
        mock_get.return_value = mock_model

        title = ai.generate_title("My story about mornings")
        assert title == "A Quiet Dawn"

    @patch("storyteller.ai._get_model")
    def test_returns_none_on_empty_response(self, mock_get):
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text.return_value = "   "
        mock_model.prompt.return_value = mock_response
        mock_get.return_value = mock_model

        assert ai.generate_title("story") is None

    @patch("storyteller.ai._get_model", side_effect=Exception("connection error"))
    def test_returns_none_on_exception(self, mock_get):
        assert ai.generate_title("story") is None


class TestGenerateTags:
    @patch("storyteller.ai._get_model")
    def test_parses_json_array(self, mock_get):
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text.return_value = '["childhood", "family"]'
        mock_model.prompt.return_value = mock_response
        mock_get.return_value = mock_model

        tags = ai.generate_tags("story about growing up", ["childhood", "family", "love"])
        assert tags == ["childhood", "family"]

    @patch("storyteller.ai._get_model")
    def test_handles_markdown_code_fence(self, mock_get):
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text.return_value = '```json\n["travel", "adventure"]\n```'
        mock_model.prompt.return_value = mock_response
        mock_get.return_value = mock_model

        tags = ai.generate_tags("my trip", ["travel", "adventure"])
        assert tags == ["travel", "adventure"]

    @patch("storyteller.ai._get_model")
    def test_lowercases_and_strips_tags(self, mock_get):
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text.return_value = '["  Career ", "LOVE"]'
        mock_model.prompt.return_value = mock_response
        mock_get.return_value = mock_model

        tags = ai.generate_tags("story", ["career", "love"])
        assert tags == ["career", "love"]

    @patch("storyteller.ai._get_model", side_effect=Exception("timeout"))
    def test_returns_none_on_exception(self, mock_get):
        assert ai.generate_tags("story", ["tag1"]) is None

    @patch("storyteller.ai._get_model")
    def test_returns_none_on_invalid_json(self, mock_get):
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text.return_value = "not json at all"
        mock_model.prompt.return_value = mock_response
        mock_get.return_value = mock_model

        assert ai.generate_tags("story", ["tag1"]) is None
