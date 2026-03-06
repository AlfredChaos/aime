def ensure_memory_policy(sys_prompt_content: str) -> str:
    if (
        "record_to_memory" not in sys_prompt_content
        and "retrieve_from_memory" not in sys_prompt_content
    ):
        return (
            sys_prompt_content
            + "\n\n## 记忆管理指南：\n"
            "1. 当用户分享个人信息、偏好、习惯或可复用事实时，使用 record_to_memory 记录。\n"
            "2. 在回答涉及用户过往信息/偏好/事实的问题前，先使用 retrieve_from_memory 检索。\n"
            "3. keywords 使用短、明确的短语（如地点、人名、主题、日期）。"
        )

    return sys_prompt_content

