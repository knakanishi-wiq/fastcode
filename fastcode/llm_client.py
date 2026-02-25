"""
Centralized LLM client for FastCode.

All LLM call sites import from this module. litellm globals are set at
import time as module-level side effects — no explicit init() call required.

Exports:
    completion(model, messages, **kwargs) -> ModelResponse
    completion_stream(model, messages, **kwargs) -> CustomStreamWrapper
    count_tokens(model, text) -> int
    DEFAULT_MODEL: str

NOTE: Signature is count_tokens(model, text) — reversed from utils.count_tokens(text, model).
Callers migrating from utils.count_tokens must update argument order.
"""
import os

import litellm
import tiktoken
from litellm import completion as _completion
from litellm import token_counter as _token_counter

# --- Module-level configuration (applied once at import) ---
litellm.drop_params = True
litellm.suppress_debug_info = True
litellm.num_retries = 3

# --- Environment validation (fail fast, not at first call) ---
_project = os.environ.get("VERTEXAI_PROJECT")
_location = os.environ.get("VERTEXAI_LOCATION")

if not _project:
    raise EnvironmentError(
        "VERTEXAI_PROJECT is not set. "
        "Export it to your GCP project ID before importing fastcode.llm_client."
    )
if not _location:
    raise EnvironmentError(
        "VERTEXAI_LOCATION is not set. "
        "Export it to your GCP region (e.g. 'us-central1') before importing fastcode.llm_client."
    )

# Default model (LITELLM_MODEL env var; falls back to gemini-2.0-flash-001 via VertexAI)
DEFAULT_MODEL: str = os.environ.get("LITELLM_MODEL", "vertex_ai/gemini-2.0-flash-001")


def completion(model: str, messages: list, **kwargs):
    """Call litellm.completion() — exceptions bubble up raw."""
    return _completion(model=model, messages=messages, **kwargs)


def completion_stream(model: str, messages: list, **kwargs):
    """Call litellm.completion() with stream=True — returns CustomStreamWrapper.

    Callers iterate chunks directly: for chunk in completion_stream(...): ...
    """
    return _completion(model=model, messages=messages, stream=True, **kwargs)


def count_tokens(model: str, text: str) -> int:
    """Count tokens via litellm; fall back to cl100k_base for unknown models.

    NOTE: Signature is (model, text) — reversed from utils.count_tokens(text, model).
    Callers migrating from utils.count_tokens must update argument order.
    """
    try:
        return _token_counter(model=model, text=text)
    except Exception:
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text, disallowed_special=()))
