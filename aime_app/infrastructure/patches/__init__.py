from __future__ import annotations

from aime_app.infrastructure.patches.agentscope_gemini import (
    patch_agentscope_gemini_embedding_batch_fallback,
    patch_agentscope_gemini_stream_usage,
)
from aime_app.infrastructure.patches.gemini_thinking_formatter import (
    patch_gemini_thinking_formatter,
)
from aime_app.infrastructure.patches.google_genai_client import (
    patch_google_genai_client_close,
)


def apply_all() -> None:
    patch_google_genai_client_close()
    patch_agentscope_gemini_stream_usage()
    patch_agentscope_gemini_embedding_batch_fallback()
    patch_gemini_thinking_formatter()

