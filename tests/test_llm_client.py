"""
Unit tests for fastcode.llm_client module contract.

Tests cover:
- Import-time environment validation (EnvironmentError when vars missing)
- Module-level litellm globals (drop_params, suppress_debug_info)
- count_tokens with vertex_ai/ prefix, empty string, and unknown models
- completion() and completion_stream() function signatures (mocked)
"""
import importlib
import sys

import pytest


# ---------------------------------------------------------------------------
# Helper: force a fresh import of fastcode.llm_client
# ---------------------------------------------------------------------------

def _reload_llm_client():
    """Delete cached module and re-import to test import-time side effects.

    Loads llm_client.py directly by file path (bypasses fastcode/__init__.py,
    which imports from modules that are intentionally broken during Phase 2-3
    migration).
    """
    import importlib.util
    import pathlib

    if "fastcode.llm_client" in sys.modules:
        del sys.modules["fastcode.llm_client"]

    spec = importlib.util.spec_from_file_location(
        "fastcode.llm_client",
        pathlib.Path(__file__).parent.parent / "fastcode" / "llm_client.py",
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["fastcode.llm_client"] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Import-time validation tests
# ---------------------------------------------------------------------------

class TestImportValidation:
    def test_import_raises_when_vertexai_project_missing(self, monkeypatch):
        """When VERTEXAI_PROJECT is unset, import must raise EnvironmentError."""
        monkeypatch.delenv("VERTEXAI_PROJECT", raising=False)
        monkeypatch.setenv("VERTEXAI_LOCATION", "us-central1")

        with pytest.raises(EnvironmentError, match="VERTEXAI_PROJECT"):
            _reload_llm_client()

    def test_import_raises_when_vertexai_location_missing(self, monkeypatch):
        """When VERTEXAI_LOCATION is unset, import must raise EnvironmentError."""
        monkeypatch.setenv("VERTEXAI_PROJECT", "test-project")
        monkeypatch.delenv("VERTEXAI_LOCATION", raising=False)

        with pytest.raises(EnvironmentError, match="VERTEXAI_LOCATION"):
            _reload_llm_client()

    def test_import_succeeds_when_both_vars_set(self, monkeypatch):
        """When both env vars are set, import succeeds without raising."""
        monkeypatch.setenv("VERTEXAI_PROJECT", "test-project")
        monkeypatch.setenv("VERTEXAI_LOCATION", "us-central1")

        # Should not raise
        mod = _reload_llm_client()
        assert mod is not None


# ---------------------------------------------------------------------------
# Module-level globals tests
# ---------------------------------------------------------------------------

class TestModuleGlobals:
    @pytest.fixture(autouse=True)
    def set_env(self, monkeypatch):
        monkeypatch.setenv("VERTEXAI_PROJECT", "test-project")
        monkeypatch.setenv("VERTEXAI_LOCATION", "us-central1")

    def test_litellm_drop_params_is_true_after_import(self, monkeypatch):
        """litellm.drop_params must be True after importing llm_client."""
        import litellm
        _reload_llm_client()
        assert litellm.drop_params is True

    def test_litellm_suppress_debug_info_is_true_after_import(self, monkeypatch):
        """litellm.suppress_debug_info must be True after importing llm_client."""
        import litellm
        _reload_llm_client()
        assert litellm.suppress_debug_info is True


# ---------------------------------------------------------------------------
# count_tokens tests
# ---------------------------------------------------------------------------

class TestCountTokens:
    @pytest.fixture(autouse=True)
    def set_env(self, monkeypatch):
        monkeypatch.setenv("VERTEXAI_PROJECT", "test-project")
        monkeypatch.setenv("VERTEXAI_LOCATION", "us-central1")

    def test_count_tokens_vertex_ai_prefix_returns_positive_int(self, monkeypatch):
        """count_tokens for a vertex_ai/ model returns a positive integer."""
        mod = _reload_llm_client()
        result = mod.count_tokens("vertex_ai/gemini-2.0-flash-001", "Hello world")
        assert isinstance(result, int), f"Expected int, got {type(result)}"
        assert result > 0, f"Expected positive int, got {result}"

    def test_count_tokens_empty_string_does_not_raise(self, monkeypatch):
        """count_tokens with empty string returns 0 or small int without exception."""
        mod = _reload_llm_client()
        result = mod.count_tokens("vertex_ai/gemini-2.0-flash-001", "")
        assert isinstance(result, int), f"Expected int, got {type(result)}"
        assert result >= 0, f"Expected non-negative int, got {result}"

    def test_count_tokens_unknown_model_falls_back_to_tiktoken(self, monkeypatch):
        """count_tokens for unknown model uses tiktoken fallback, returns positive int."""
        mod = _reload_llm_client()
        result = mod.count_tokens("completely-unknown-model-xyz-123", "Hello world")
        assert isinstance(result, int), f"Expected int, got {type(result)}"
        assert result > 0, f"Expected positive int from tiktoken fallback, got {result}"


# ---------------------------------------------------------------------------
# Function signature tests (mocked — no live LLM calls)
# ---------------------------------------------------------------------------

class TestFunctionSignatures:
    @pytest.fixture(autouse=True)
    def set_env(self, monkeypatch):
        monkeypatch.setenv("VERTEXAI_PROJECT", "test-project")
        monkeypatch.setenv("VERTEXAI_LOCATION", "us-central1")

    def test_completion_calls_litellm_completion_with_same_args(self, monkeypatch):
        """completion() delegates to litellm.completion with model and messages."""
        import litellm

        captured = {}

        def fake_completion(model, messages, **kwargs):
            captured["model"] = model
            captured["messages"] = messages
            captured["kwargs"] = kwargs
            return object()  # fake ModelResponse

        monkeypatch.setattr(litellm, "completion", fake_completion)
        mod = _reload_llm_client()

        messages = [{"role": "user", "content": "hi"}]
        mod.completion(model="vertex_ai/gemini-2.0-flash-001", messages=messages)

        assert captured["model"] == "vertex_ai/gemini-2.0-flash-001"
        assert captured["messages"] == messages

    def test_completion_stream_calls_litellm_with_stream_true(self, monkeypatch):
        """completion_stream() delegates to litellm.completion with stream=True."""
        import litellm

        captured = {}

        def fake_completion(model, messages, **kwargs):
            captured["model"] = model
            captured["messages"] = messages
            captured["stream"] = kwargs.get("stream")
            return object()  # fake CustomStreamWrapper

        monkeypatch.setattr(litellm, "completion", fake_completion)
        mod = _reload_llm_client()

        messages = [{"role": "user", "content": "hi"}]
        mod.completion_stream(model="vertex_ai/gemini-2.0-flash-001", messages=messages)

        assert captured["model"] == "vertex_ai/gemini-2.0-flash-001"
        assert captured["messages"] == messages
        assert captured["stream"] is True
