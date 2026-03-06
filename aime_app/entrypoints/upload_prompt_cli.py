from __future__ import annotations

import os

from aime_app.infrastructure.prompts.langfuse_repo import upsert_text_prompt


def main() -> None:
    prompt_name = os.environ.get("LANGFUSE_PROMPT_NAME", "aime-system-prompt")
    prompt_content = os.environ.get(
        "LANGFUSE_PROMPT_CONTENT",
        """你是一个名为 Aime 的智能助手。
你的目标是高效且准确地协助用户完成任务。
你可以使用各种工具，并应在必要时使用它们。
请始终以礼貌和专业的态度回答。
如果你对某事不确定，请承认并寻求澄清。
""",
    )
    labels = os.environ.get("LANGFUSE_PROMPT_LABELS", "production,aime")
    label_list = [s.strip() for s in labels.split(",") if s.strip()]

    print(f"Creating prompt '{prompt_name}'...")
    try:
        upsert_text_prompt(
            prompt_name=prompt_name,
            prompt_content=prompt_content,
            labels=label_list,
        )
        print("Prompt created successfully.")
    except Exception as e:
        print(f"Error creating prompt: {e}")

