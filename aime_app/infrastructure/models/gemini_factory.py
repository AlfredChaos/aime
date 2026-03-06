from __future__ import annotations

import os

from agentscope.embedding import GeminiTextEmbedding
from agentscope.model import GeminiChatModel


def create_chat_model(*, api_key: str, base_url: str | None = None) -> GeminiChatModel:
    return GeminiChatModel(
        model_name=os.environ.get("GEMINI_CHAT_MODEL", "gemini-2.5-flash"),
        api_key=api_key,
        stream=True,
        client_kwargs={
            "http_options": {
                "base_url": base_url or os.environ.get("GEMINI_BASE_URL", "https://aicode.cat"),
            },
        },
    )


def create_embedding_model(*, api_key: str, base_url: str | None = None) -> GeminiTextEmbedding:
    return GeminiTextEmbedding(
        api_key=api_key,
        model_name=os.environ.get("GEMINI_EMBEDDING_MODEL", "text-embedding-004"),
        http_options={
            "base_url": base_url or os.environ.get("GEMINI_BASE_URL", "https://aicode.cat"),
        },
    )

