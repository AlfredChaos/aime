from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptFetchResult:
    content: str
    source: str


def fetch_prompt(*, prompt_name: str, fallback: str) -> PromptFetchResult:
    from langfuse import Langfuse

    langfuse = Langfuse()
    try:
        prompt = langfuse.get_prompt(prompt_name)
        return PromptFetchResult(content=prompt.compile(), source="langfuse")
    except Exception:
        return PromptFetchResult(content=fallback, source="fallback")


def upsert_text_prompt(*, prompt_name: str, prompt_content: str, labels: list[str] | None = None) -> None:
    from langfuse import Langfuse

    langfuse = Langfuse()
    langfuse.create_prompt(
        name=prompt_name,
        prompt=prompt_content,
        type="text",
        labels=labels or [],
    )

