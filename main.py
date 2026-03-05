
import asyncio
import os
import uuid
from pathlib import Path

import fix_agentscope_gemini, fix_gemini_thinking_formatter
from langfuse import Langfuse, observe
from dotenv import load_dotenv

from agentscope.agent import ReActAgent
from agentscope.embedding import GeminiTextEmbedding
from agentscope.formatter import GeminiChatFormatter
from agentscope.memory import InMemoryMemory, Mem0LongTermMemory
from agentscope.message import Msg
from agentscope.model import GeminiChatModel
from agent_bootstrap import create_toolkit

# Load environment variables from .env file
load_dotenv()

# Apply patches
fix_agentscope_gemini.apply_patch()
fix_gemini_thinking_formatter.apply_patch()

# Initialize Langfuse client
langfuse = Langfuse()


def _project_root() -> Path:
    return Path(__file__).resolve().parent


def _create_lancedb_vector_store(uri: str, table_name: str, embedding_model):
    from langchain_community.vectorstores import LanceDB as _LanceDB
    from langchain_core.embeddings import Embeddings as _Embeddings

    class _AgentscopeEmbeddingsAdapter(_Embeddings):
        def __init__(self, model):
            self._model = model

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                resp = asyncio.run(self._model(texts))
                return resp.embeddings

            import concurrent.futures

            def _run():
                return asyncio.run(self._model(texts))

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                return executor.submit(_run).result().embeddings

        def embed_query(self, text: str) -> list[float]:
            return self.embed_documents([text])[0]

        async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
            resp = await self._model(texts)
            return resp.embeddings

        async def aembed_query(self, text: str) -> list[float]:
            resp = await self._model([text])
            return resp.embeddings[0]

    class LanceDBPrecomputedEmbeddings(_LanceDB):
        def add_embeddings(self, embeddings, metadatas=None, ids=None):
            ids = ids or [str(uuid.uuid4()) for _ in embeddings]
            docs = []
            for idx, embedding in enumerate(embeddings):
                metadata = metadatas[idx] if metadatas else {"id": ids[idx]}
                text = ""
                if isinstance(metadata, dict):
                    text = str(metadata.get("data", ""))
                docs.append(
                    {
                        self._vector_key: embedding,
                        self._id_key: ids[idx],
                        self._text_key: text,
                        "metadata": metadata,
                    },
                )

            tbl = self.get_table()
            if tbl is None:
                tbl = self._connection.create_table(self._table_name, data=docs)
                self._table = tbl
            else:
                if self.api_key is None:
                    tbl.add(docs, mode=self.mode)
                else:
                    tbl.add(docs)

            self._fts_index = None
            return ids

    return LanceDBPrecomputedEmbeddings(
        uri=uri,
        table_name=table_name,
        embedding=_AgentscopeEmbeddingsAdapter(embedding_model),
        mode="append",
    )


@observe()
async def creating_react_agent() -> None:
    """创建一个 ReAct 智能体并运行一个简单任务。"""
    # Get Prompt from Langfuse
    print("Fetching prompt from Langfuse...")
    try:
        prompt = langfuse.get_prompt("aime-system-prompt")
        sys_prompt_content = prompt.compile()
        print(f"Loaded prompt: {sys_prompt_content}")
    except Exception as e:
        print(f"Error loading prompt from Langfuse: {e}")
        sys_prompt_content = "你是一个名为 Aime 的助手"

    project_root = _project_root()

    base_url = os.environ.get("GEMINI_BASE_URL", "https://aicode.cat")
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    if not gemini_api_key:
        raise RuntimeError("GEMINI_API_KEY is required")

    model = GeminiChatModel(
        model_name=os.environ.get("GEMINI_CHAT_MODEL", "gemini-2.5-flash"),
        api_key=gemini_api_key,
        stream=True,
        client_kwargs={
            "http_options": {
                "base_url": base_url,
            },
        },
    )

    embedding_model = GeminiTextEmbedding(
        api_key=gemini_api_key,
        model_name=os.environ.get("GEMINI_EMBEDDING_MODEL", "text-embedding-004"),
        http_options={
            "base_url": base_url,
        },
    )

    lancedb_uri = os.environ.get("LANCEDB_URI", str(Path("~/.lancedb").expanduser()))
    lancedb_table = os.environ.get("LANCEDB_TABLE_NAME", "mem0_memory")
    lancedb_vs = _create_lancedb_vector_store(
        uri=lancedb_uri,
        table_name=lancedb_table,
        embedding_model=embedding_model,
    )

    import mem0

    vector_store_config = mem0.vector_stores.configs.VectorStoreConfig(
        provider="langchain",
        config={"client": lancedb_vs, "collection_name": "mem0"},
    )

    long_term_memory = Mem0LongTermMemory(
        agent_name="Aime",
        user_name="user",
        model=model,
        embedding_model=embedding_model,
        vector_store_config=vector_store_config,
        suppress_mem0_logging=True,
    )

    # Prepare tools
    toolkit = create_toolkit(project_root=str(project_root))

    aime = ReActAgent(
        name="Aime",
        sys_prompt=sys_prompt_content,
        model=model,
        formatter=GeminiChatFormatter(),
        toolkit=toolkit,
        memory=InMemoryMemory(),
        long_term_memory=long_term_memory,
        long_term_memory_mode="agent_control",
    )

    msg = Msg(
        name="user",
        content="告诉我你有哪些工具和技能？",
        role="user",
    )

    await aime(msg)


if __name__ == "__main__":
    asyncio.run(creating_react_agent())
