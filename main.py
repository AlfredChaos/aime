import warnings

warnings.filterwarnings(
    "ignore",
    category=DeprecationWarning,
    message=r"Inheritance class AiohttpClientSession from ClientSession is discouraged",
)

import asyncio
import base64
import mimetypes
import os
import uuid
from pathlib import Path

import fix_gemini_thinking_formatter
from langfuse import Langfuse, observe
from dotenv import load_dotenv

from agentscope.agent import ReActAgent
from agentscope.embedding import GeminiTextEmbedding
from agentscope.formatter import GeminiChatFormatter
from agentscope.memory import InMemoryMemory, Mem0LongTermMemory
from agentscope.message import Base64Source, ImageBlock, Msg, TextBlock
from agentscope.model import GeminiChatModel
from agent_bootstrap import create_toolkit

# Load environment variables from .env file
load_dotenv()

def _patch_google_genai_client_close() -> None:
    try:
        from google.genai._api_client import BaseApiClient
    except Exception:
        return

    if getattr(BaseApiClient.aclose, "_agentscope_research_patched", False):
        return

    original_close = BaseApiClient.close
    original_aclose = BaseApiClient.aclose

    def _safe_close(self) -> None:
        if not hasattr(self, "_http_options"):
            return
        try:
            return original_close(self)
        except AttributeError as e:
            if "_http_options" in str(e):
                return
            raise

    async def _safe_aclose(self) -> None:
        if not hasattr(self, "_http_options"):
            return
        try:
            return await original_aclose(self)
        except AttributeError as e:
            if "_http_options" in str(e):
                return
            raise

    _safe_close._agentscope_research_patched = True
    _safe_aclose._agentscope_research_patched = True
    BaseApiClient.close = _safe_close
    BaseApiClient.aclose = _safe_aclose


def _patch_agentscope_gemini_stream_usage() -> None:
    from datetime import datetime
    import json
    import base64 as _base64

    from agentscope.model import GeminiChatModel
    from agentscope.model._model_usage import ChatUsage
    from agentscope.message import ToolUseBlock, TextBlock, ThinkingBlock
    from agentscope._utils._common import _json_loads_with_repair
    from agentscope.model._model_response import ChatResponse

    if getattr(
        GeminiChatModel._parse_gemini_stream_generation_response,
        "_agentscope_research_patched",
        False,
    ):
        return

    async def _patched_parse_gemini_stream_generation_response(
        self,
        start_datetime: datetime,
        response,
        structured_model=None,
    ):
        text = ""
        thinking = ""
        tool_calls = []
        metadata = None

        async for chunk in response:
            if (
                chunk.candidates
                and chunk.candidates[0].content
                and chunk.candidates[0].content.parts
            ):
                for part in chunk.candidates[0].content.parts:
                    if part.text:
                        if part.thought:
                            thinking += part.text
                        else:
                            text += part.text

                    if part.function_call:
                        keyword_args = part.function_call.args or {}

                        if part.thought_signature:
                            call_id = _base64.b64encode(
                                part.thought_signature,
                            ).decode("utf-8")
                        else:
                            call_id = part.function_call.id

                        tool_calls.append(
                            ToolUseBlock(
                                type="tool_use",
                                id=call_id,
                                name=part.function_call.name,
                                input=keyword_args,
                                raw_input=json.dumps(
                                    keyword_args,
                                    ensure_ascii=False,
                                ),
                            ),
                        )

            if text and structured_model:
                metadata = _json_loads_with_repair(text)

            usage = None
            if chunk.usage_metadata:
                prompt_tokens = chunk.usage_metadata.prompt_token_count or 0
                total_tokens = chunk.usage_metadata.total_token_count or 0
                output_tokens = max(0, total_tokens - prompt_tokens)

                usage = ChatUsage(
                    input_tokens=prompt_tokens,
                    output_tokens=output_tokens,
                    time=(datetime.now() - start_datetime).total_seconds(),
                )

            content_blocks = []
            if thinking:
                content_blocks.append(
                    ThinkingBlock(
                        type="thinking",
                        thinking=thinking,
                    ),
                )

            if text:
                content_blocks.append(
                    TextBlock(
                        type="text",
                        text=text,
                    ),
                )

            yield ChatResponse(
                content=content_blocks + tool_calls,
                usage=usage,
                metadata=metadata,
            )

    _patched_parse_gemini_stream_generation_response._agentscope_research_patched = True
    GeminiChatModel._parse_gemini_stream_generation_response = (
        _patched_parse_gemini_stream_generation_response
    )


# Apply patches
_patch_google_genai_client_close()
_patch_agentscope_gemini_stream_usage()
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
    warnings.filterwarnings(
        "ignore",
        category=DeprecationWarning,
        message=r"Inheritance class AiohttpClientSession from ClientSession is discouraged",
    )
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

    print("已启动交互模式：直接输入文本发送；发送图片：/img <path> [可选描述]；退出：/exit")
    while True:
        raw = await asyncio.to_thread(input, "You> ")
        if raw is None:
            continue

        user_input = raw.strip()
        if not user_input:
            continue

        if user_input.lower() in {"exit", "quit", "/exit", "/quit"}:
            break

        if user_input.startswith("/img "):
            parts = user_input.split(maxsplit=2)
            if len(parts) < 2:
                print("Error: missing image path")
                continue

            image_path = os.path.expanduser(parts[1])
            caption = parts[2] if len(parts) >= 3 else ""

            try:
                data = Path(image_path).read_bytes()
            except FileNotFoundError:
                print(f"Error: image file not found: {image_path}")
                continue
            except Exception as e:
                print(f"Error: failed to read image: {e}")
                continue

            mime, _ = mimetypes.guess_type(image_path)
            media_type = mime or "image/jpeg"
            b64 = base64.b64encode(data).decode("utf-8")

            blocks = []
            if caption:
                blocks.append(TextBlock(type="text", text=caption))
            blocks.append(
                ImageBlock(
                    type="image",
                    source=Base64Source(
                        type="base64",
                        media_type=media_type,
                        data=b64,
                    ),
                ),
            )

            msg = Msg(name="user", role="user", content=blocks)
        else:
            msg = Msg(name="user", role="user", content=user_input)

        try:
            warnings.simplefilter("ignore", DeprecationWarning)
            await aime(msg)
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(creating_react_agent())
