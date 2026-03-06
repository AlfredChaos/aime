from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

from agentscope.embedding import GeminiTextEmbedding
from agentscope.embedding._embedding_base import EmbeddingModelBase
from agentscope.model import GeminiChatModel


def create_chat_model(*, api_key: str, base_url: str | None = None) -> GeminiChatModel:
    return GeminiChatModel(
        model_name=os.environ.get("GEMINI_CHAT_MODEL", "gemini-2.5-flash"),
        api_key=api_key,
        stream=False,
        client_kwargs={
            "http_options": {
                "base_url": base_url or os.environ.get("GEMINI_BASE_URL", "https://aicode.cat"),
            },
        },
    )


def create_embedding_model(*, api_key: str, base_url: str | None = None) -> Any:
    provider = (os.environ.get("EMBEDDING_PROVIDER") or "siliconflow").strip().lower()

    if provider == "gemini":
        return GeminiTextEmbedding(
            api_key=api_key,
            model_name=os.environ.get("GEMINI_EMBEDDING_MODEL", "text-embedding-004"),
            http_options={
                "base_url": base_url
                or os.environ.get("GEMINI_BASE_URL", "https://aicode.cat"),
            },
        )

    if provider == "dashscope":
        dashscope_api_key = os.environ.get("DASHSCOPE_API_KEY")
        if not dashscope_api_key:
            raise RuntimeError("DASHSCOPE_API_KEY is required for dashscope embedding")

        from agentscope.embedding import DashScopeTextEmbedding

        return DashScopeTextEmbedding(
            model_name=os.environ.get("DASHSCOPE_EMBEDDING_MODEL", "text-embedding-v2"),
            api_key=dashscope_api_key,
        )

    if provider == "siliconflow":
        siliconflow_api_key = os.environ.get("SILICONFLOW_API_KEY")
        if not siliconflow_api_key:
            raise RuntimeError(
                "SILICONFLOW_API_KEY is required for siliconflow embedding",
            )

        dims_env = os.environ.get("SILICONFLOW_EMBEDDING_DIMS") or os.environ.get(
            "EMBEDDING_DIMS",
        )
        dimensions = 0
        if dims_env:
            try:
                dimensions = int(dims_env)
            except ValueError:
                dimensions = 0

        return SiliconFlowTextEmbedding(
            api_key=siliconflow_api_key,
            model_name=os.environ.get("SILICONFLOW_EMBEDDING_MODEL", "BAAI/bge-m3"),
            base_url=os.environ.get(
                "SILICONFLOW_BASE_URL",
                "https://api.siliconflow.cn/v1/embeddings",
            ),
            dimensions=dimensions,
        )

    raise RuntimeError(f"Unsupported EMBEDDING_PROVIDER: {provider}")


class SiliconFlowTextEmbedding(EmbeddingModelBase):
    def __init__(self, *, api_key: str, model_name: str, base_url: str, dimensions: int) -> None:
        super().__init__(model_name=model_name, dimensions=dimensions)
        self._api_key = api_key
        self._base_url = base_url

    async def __call__(self, text, **kwargs):
        gather_text: list[str] = []
        for item in text:
            if isinstance(item, dict) and "text" in item:
                gather_text.append(item["text"])
            elif isinstance(item, str):
                gather_text.append(item)
            else:
                raise ValueError(
                    "Input text must be a list of strings or TextBlock dicts.",
                )

        start_time = datetime.now()
        embeddings = await asyncio.to_thread(self._embed_sync, gather_text)
        if self.dimensions <= 0 and embeddings and embeddings[0]:
            self.dimensions = len(embeddings[0])
        time = (datetime.now() - start_time).total_seconds()

        from agentscope.embedding._embedding_response import EmbeddingResponse
        from agentscope.embedding._embedding_usage import EmbeddingUsage

        return EmbeddingResponse(
            embeddings=embeddings,
            usage=EmbeddingUsage(
                time=time,
            ),
        )

    def _embed_sync(self, texts: list[str]) -> list[list[float]]:
        payload = {
            "model": self.model_name,
            "input": texts[0] if len(texts) == 1 else texts,
            "encoding_format": "float",
        }

        req = urllib.request.Request(
            self._base_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")
            except Exception:
                body = ""
            raise RuntimeError(f"SiliconFlow embeddings HTTP {e.code}: {body}") from e
        except Exception as e:
            raise RuntimeError(f"SiliconFlow embeddings request failed: {e}") from e

        try:
            parsed = json.loads(raw.decode("utf-8"))
        except Exception as e:
            raise RuntimeError("SiliconFlow embeddings response is not valid JSON") from e

        data = parsed.get("data")
        if not isinstance(data, list):
            raise RuntimeError(f"SiliconFlow embeddings invalid response: {parsed}")

        data_sorted = sorted(
            data,
            key=lambda x: x.get("index", 0) if isinstance(x, dict) else 0,
        )
        embeddings: list[list[float]] = []
        for row in data_sorted:
            if not isinstance(row, dict) or "embedding" not in row:
                raise RuntimeError(f"SiliconFlow embeddings invalid row: {row}")
            embeddings.append(row["embedding"])
        return embeddings
