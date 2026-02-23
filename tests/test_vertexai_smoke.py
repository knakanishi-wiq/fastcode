"""
VertexAI smoke tests — validates litellm + ADC integration.

Happy path: skipped when VERTEXAI_PROJECT is not set (CI without credentials).
Error path: always runs — confirms missing VERTEXAI_PROJECT produces a
            configuration error, not a misleading 401 auth error.
"""
import os

import pytest
from dotenv import load_dotenv

import litellm

load_dotenv()

VERTEX_MODEL = "vertex_ai/gemini-3-flash-preview"


class TestVertexAISmoke:
    @pytest.mark.skipif(
        not os.environ.get("VERTEXAI_PROJECT"),
        reason="VERTEXAI_PROJECT not set — skipping live test",
    )
    def test_happy_path_returns_valid_response(self):
        """Call VertexAI via ADC and assert a non-empty response is returned."""
        response = litellm.completion(
            model=VERTEX_MODEL,
            messages=[{"role": "user", "content": "Say hello in one word."}],
        )
        assert response.choices[0].message.content, (
            "Expected non-empty response content from VertexAI"
        )
        assert response.model is not None, "Expected response.model to be set"

    def test_missing_project_raises_config_error(self, monkeypatch):
        """When VERTEXAI_PROJECT is unset, litellm should raise a configuration
        error (not a 401) so the caller knows what to fix."""
        monkeypatch.delenv("VERTEXAI_PROJECT", raising=False)
        monkeypatch.delenv("VERTEXAI_LOCATION", raising=False)
        monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)

        with pytest.raises(Exception) as exc_info:
            litellm.completion(
                model=VERTEX_MODEL,
                messages=[{"role": "user", "content": "Say hello in one word."}],
            )

        error_text = str(exc_info.value).lower()
        config_keywords = {"project", "credentials", "configuration", "not found", "default"}
        assert any(kw in error_text for kw in config_keywords), (
            f"Expected a configuration-related error, got: {exc_info.value}"
        )
        assert "401" not in error_text, (
            f"Got a 401 auth error instead of a configuration error: {exc_info.value}"
        )
