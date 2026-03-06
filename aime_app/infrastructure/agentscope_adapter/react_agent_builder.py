from __future__ import annotations

import os
from pathlib import Path

from agentscope.agent import ReActAgent
from agentscope.formatter import GeminiChatFormatter
from agentscope.memory import InMemoryMemory, Mem0LongTermMemory

from aime_app.application.ports import AgentBuilder, ChatAgent
from aime_app.domain.prompt_policy import ensure_memory_policy
from aime_app.infrastructure.models.gemini_factory import (
    create_chat_model,
    create_embedding_model,
)
from aime_app.infrastructure.prompts.langfuse_repo import fetch_prompt
from aime_app.infrastructure.toolkit.toolkit_factory import create_toolkit
from aime_app.infrastructure.vectorstores.lancedb_store import (
    create_lancedb_vector_store,
    create_vector_store_config,
    get_existing_lancedb_vector_dim,
    migrate_lancedb_table_embeddings,
    probe_embedding_dim,
    resolve_lancedb_table_name,
    ensure_lancedb_table_exists,
)


class ReActAgentBuilder(AgentBuilder):
    def __init__(self, *, project_root: Path):
        self._project_root = project_root

    async def build(self) -> ChatAgent:
        prompt_name = os.environ.get("LANGFUSE_PROMPT_NAME", "aime-system-prompt")
        prompt_fallback = os.environ.get(
            "LANGFUSE_PROMPT_FALLBACK",
            "你是一个名为 Aime 的助手",
        )
        prompt_result = fetch_prompt(prompt_name=prompt_name, fallback=prompt_fallback)
        sys_prompt_content = ensure_memory_policy(prompt_result.content)

        base_url = os.environ.get("GEMINI_BASE_URL", "https://aicode.cat")
        gemini_api_key = os.environ.get("GEMINI_API_KEY")
        if not gemini_api_key:
            raise RuntimeError("GEMINI_API_KEY is required")

        model = create_chat_model(
            api_key=gemini_api_key,
            base_url=base_url,
        )

        embedding_model = create_embedding_model(
            api_key=gemini_api_key,
            base_url=base_url,
        )

        lancedb_uri = os.environ.get(
            "LANCEDB_URI",
            str(Path("~/.lancedb").expanduser()),
        )
        lancedb_table = os.environ.get("LANCEDB_TABLE_NAME", "mem0_memory")

        embedding_dim = None
        embedding_dim_env = (
            os.environ.get("SILICONFLOW_EMBEDDING_DIMS")
            or os.environ.get("GEMINI_EMBEDDING_DIMS")
            or os.environ.get("EMBEDDING_DIMS")
        )
        if embedding_dim_env:
            try:
                embedding_dim = int(embedding_dim_env)
            except ValueError:
                embedding_dim = None

        probed_dim = await probe_embedding_dim(embedding_model)
        if probed_dim is not None:
            embedding_dim = probed_dim

        base_lancedb_table = lancedb_table
        lancedb_table = resolve_lancedb_table_name(
            uri=lancedb_uri,
            table_name=lancedb_table,
            embedding_dim=embedding_dim,
        )

        if embedding_dim is not None:
            ensure_lancedb_table_exists(
                uri=lancedb_uri,
                table_name=lancedb_table,
                embedding_dim=embedding_dim,
                template_table_name=base_lancedb_table,
            )
            base_dim = get_existing_lancedb_vector_dim(lancedb_uri, base_lancedb_table)
            if (
                base_dim is not None
                and base_dim != embedding_dim
                and base_lancedb_table != lancedb_table
            ):
                await migrate_lancedb_table_embeddings(
                    uri=lancedb_uri,
                    source_table_name=base_lancedb_table,
                    target_table_name=lancedb_table,
                    embedding_model=embedding_model,
                )

        effective_embedding_dim = embedding_dim or get_existing_lancedb_vector_dim(
            lancedb_uri,
            lancedb_table,
        )

        lancedb_vs = create_lancedb_vector_store(
            uri=lancedb_uri,
            table_name=lancedb_table,
            embedding_model=embedding_model,
        )

        vector_store_config = create_vector_store_config(
            lancedb_vs=lancedb_vs,
            effective_embedding_dim=effective_embedding_dim,
        )

        long_term_memory = Mem0LongTermMemory(
            agent_name="Aime",
            user_name="user",
            model=model,
            embedding_model=embedding_model,
            vector_store_config=vector_store_config,
            suppress_mem0_logging=True,
        )

        toolkit = create_toolkit(project_root=str(self._project_root))

        agent = ReActAgent(
            name="Aime",
            sys_prompt=sys_prompt_content,
            model=model,
            formatter=GeminiChatFormatter(),
            toolkit=toolkit,
            memory=InMemoryMemory(),
            long_term_memory=long_term_memory,
            long_term_memory_mode="agent_control",
        )

        return agent
