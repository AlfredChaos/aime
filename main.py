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


def _patch_agentscope_gemini_embedding_batch_fallback() -> None:
    from datetime import datetime

    from agentscope.embedding import GeminiTextEmbedding
    from agentscope.embedding._embedding_response import EmbeddingResponse
    from agentscope.embedding._embedding_usage import EmbeddingUsage

    if getattr(GeminiTextEmbedding.__call__, "_agentscope_research_patched", False):
        return

    original_call = GeminiTextEmbedding.__call__

    async def _patched_call(self, text, **kwargs):
        gather_text = []
        for _ in text:
            if isinstance(_, dict) and "text" in _:
                gather_text.append(_["text"])
            elif isinstance(_, str):
                gather_text.append(_)
            else:
                raise ValueError(
                    "Input text must be a list of strings or TextBlock dicts.",
                )

        request_identifier = {
            "model": self.model_name,
            "contents": gather_text[0] if len(gather_text) == 1 else gather_text,
            "config": kwargs,
        }

        if self.embedding_cache:
            cached_embeddings = await self.embedding_cache.retrieve(
                identifier=request_identifier,
            )
            if cached_embeddings:
                return EmbeddingResponse(
                    embeddings=cached_embeddings,
                    usage=EmbeddingUsage(
                        tokens=0,
                        time=0,
                    ),
                    source="cache",
                )

        start_time = datetime.now()

        def _extract_embeddings(resp):
            return [_.values for _ in resp.embeddings]

        enable_batch = os.environ.get("GEMINI_ENABLE_BATCH_EMBED", "").lower() in (
            "1",
            "true",
            "yes",
        )

        if len(gather_text) == 1:
            response = self.client.models.embed_content(
                model=self.model_name,
                contents=gather_text[0],
                config=kwargs,
            )
            embeddings = _extract_embeddings(response)
        elif not enable_batch:
            embeddings = []
            for item in gather_text:
                resp = self.client.models.embed_content(
                    model=self.model_name,
                    contents=item,
                    config=kwargs,
                )
                item_embeddings = _extract_embeddings(resp)
                if not item_embeddings:
                    raise RuntimeError("Empty embedding response")
                embeddings.append(item_embeddings[0])
        else:
            try:
                response = self.client.models.embed_content(
                    model=self.model_name,
                    contents=gather_text,
                    config=kwargs,
                )
                embeddings = _extract_embeddings(response)
            except Exception as e:
                err_text = str(e)
                if (
                    "batchEmbedContents" in err_text
                    or "Unsupported action" in err_text
                    or "404" in err_text
                    or "NOT_FOUND" in err_text
                ):
                    embeddings = []
                    for item in gather_text:
                        resp = self.client.models.embed_content(
                            model=self.model_name,
                            contents=item,
                            config=kwargs,
                        )
                        item_embeddings = _extract_embeddings(resp)
                        if not item_embeddings:
                            raise RuntimeError("Empty embedding response")
                        embeddings.append(item_embeddings[0])
                else:
                    raise

        time = (datetime.now() - start_time).total_seconds()

        if self.embedding_cache:
            await self.embedding_cache.store(
                identifier=request_identifier,
                embeddings=embeddings,
            )

        return EmbeddingResponse(
            embeddings=embeddings,
            usage=EmbeddingUsage(
                time=time,
            ),
        )

    _patched_call._agentscope_research_patched = True
    GeminiTextEmbedding.__call__ = _patched_call
    GeminiTextEmbedding.__call__._agentscope_research_original = original_call


# Apply patches
_patch_google_genai_client_close()
_patch_agentscope_gemini_stream_usage()
_patch_agentscope_gemini_embedding_batch_fallback()
fix_gemini_thinking_formatter.apply_patch()

# Initialize Langfuse client
langfuse = Langfuse()


def _project_root() -> Path:
    return Path(__file__).resolve().parent


async def _probe_embedding_dim(embedding_model) -> int | None:
    try:
        resp = await embedding_model(["dimension_probe"])
        embeddings = getattr(resp, "embeddings", None)
        if not embeddings:
            return None
        first = embeddings[0]
        if not first:
            return None
        return len(first)
    except Exception:
        return None


def _get_existing_lancedb_vector_dim(uri: str, table_name: str) -> int | None:
    try:
        import lancedb

        db = lancedb.connect(uri)
        list_tables = getattr(db, "list_tables", None)
        table_names = list_tables() if callable(list_tables) else db.table_names()
        if table_name not in set(table_names):
            return None
        tbl = db.open_table(table_name)
        schema = tbl.schema
        if "vector" not in schema.names:
            return None
        vec_type = schema.field("vector").type
        if hasattr(vec_type, "list_size"):
            return int(vec_type.list_size)
        return None
    except Exception:
        return None


def _resolve_lancedb_table_name(
    *, uri: str, table_name: str, embedding_dim: int | None
) -> str:
    if embedding_dim is None:
        return table_name
    existing_dim = _get_existing_lancedb_vector_dim(uri, table_name)
    if existing_dim is None or existing_dim == embedding_dim:
        return table_name
    return f"{table_name}_d{embedding_dim}"


def _create_lancedb_vector_store(uri: str, table_name: str, embedding_model):
    from langchain_community.vectorstores import LanceDB as _LanceDB
    from langchain_core.embeddings import Embeddings as _Embeddings
    from langchain_core.documents import Document as _Document

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
        @staticmethod
        def _quote_lance_sql_value(value):
            if value is None:
                return "NULL"
            if isinstance(value, bool):
                return "true" if value else "false"
            if isinstance(value, (int, float)):
                return str(value)
            text = str(value).replace("\\", "\\\\").replace("'", "\\'")
            return f"'{text}'"

        @classmethod
        def _to_lance_where(cls, filter_dict: dict) -> str:
            parts: list[str] = []
            for key, value in filter_dict.items():
                if key.startswith("$"):
                    raise ValueError(f"Unsupported filter operator: {key}")
                parts.append(f"metadata.{key} = {cls._quote_lance_sql_value(value)}")
            return " AND ".join(parts)

        def add_embeddings(self, embeddings, metadatas=None, ids=None):
            ids = ids or [str(uuid.uuid4()) for _ in embeddings]
            docs = []
            tbl = self.get_table()
            metadata_allowed_keys = None
            if tbl is not None and "metadata" in tbl.schema.names:
                try:
                    meta_field = tbl.schema.field("metadata")
                    meta_type = meta_field.type
                    if hasattr(meta_type, "names") and meta_type.names:
                        metadata_allowed_keys = set(meta_type.names)
                except Exception:
                    metadata_allowed_keys = None

            for idx, embedding in enumerate(embeddings):
                metadata = metadatas[idx] if metadatas else {"id": ids[idx]}
                text = ""
                if isinstance(metadata, dict):
                    text = str(metadata.get("data", ""))
                    if metadata_allowed_keys is not None:
                        metadata = {k: v for k, v in metadata.items() if k in metadata_allowed_keys}
                docs.append(
                    {
                        self._vector_key: embedding,
                        self._id_key: ids[idx],
                        self._text_key: text,
                        "metadata": metadata,
                    },
                )

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

        def similarity_search_by_vector(
            self,
            embedding,
            k: int | None = None,
            filter: dict | str | None = None,
            name: str | None = None,
            **kwargs,
        ):
            if isinstance(embedding, list) and embedding and isinstance(
                embedding[0],
                (list, tuple),
            ):
                embedding = embedding[0]

            where = None
            if isinstance(filter, dict):
                where = self._to_lance_where(filter)
            else:
                where = filter

            docs = self._query(embedding, k, filter=where, name=name, **kwargs)
            ids = []
            scores = []
            metadatas = []

            relevance_score_fn = self._select_relevance_score_fn()
            distance_col = "_distance" if "_distance" in docs.schema.names else None

            for idx in range(len(docs)):
                ids.append(docs[self._id_key][idx].as_py())
                metadatas.append(docs["metadata"][idx].as_py() if "metadata" in docs.schema.names else {})
                if distance_col is not None:
                    scores.append(relevance_score_fn(float(docs[distance_col][idx].as_py())))
                else:
                    scores.append(None)

            return {"ids": [ids], "distances": [scores], "metadatas": [metadatas]}

        def get_by_ids(self, ids: list[str], name: str | None = None):
            if not ids:
                return []
            tbl = self.get_table(name)
            quoted = ",".join(self._quote_lance_sql_value(i) for i in ids)
            rows = tbl.search().where(f"{self._id_key} in ({quoted})").to_arrow()
            docs = []
            for idx in range(len(rows)):
                page_content = rows[self._text_key][idx].as_py()
                metadata = rows["metadata"][idx].as_py() if "metadata" in rows.schema.names else {}
                doc_id = rows[self._id_key][idx].as_py()
                docs.append(_Document(page_content=page_content, metadata=metadata, id=doc_id))
            return docs

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

    if (
        "record_to_memory" not in sys_prompt_content
        and "retrieve_from_memory" not in sys_prompt_content
    ):
        sys_prompt_content = (
            sys_prompt_content
            + "\n\n## 记忆管理指南：\n"
            "1. 当用户分享个人信息、偏好、习惯或可复用事实时，使用 record_to_memory 记录。\n"
            "2. 在回答涉及用户过往信息/偏好/事实的问题前，先使用 retrieve_from_memory 检索。\n"
            "3. keywords 使用短、明确的短语（如地点、人名、主题、日期）。"
        )

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

    embedding_dim = None
    embedding_dim_env = os.environ.get("GEMINI_EMBEDDING_DIMS") or os.environ.get(
        "EMBEDDING_DIMS",
    )
    if embedding_dim_env:
        try:
            embedding_dim = int(embedding_dim_env)
        except ValueError:
            embedding_dim = None
    if embedding_dim is None:
        embedding_dim = await _probe_embedding_dim(embedding_model)
    lancedb_table = _resolve_lancedb_table_name(
        uri=lancedb_uri,
        table_name=lancedb_table,
        embedding_dim=embedding_dim,
    )
    effective_embedding_dim = embedding_dim or _get_existing_lancedb_vector_dim(
        lancedb_uri,
        lancedb_table,
    )
    lancedb_vs = _create_lancedb_vector_store(
        uri=lancedb_uri,
        table_name=lancedb_table,
        embedding_model=embedding_model,
    )

    import mem0

    try:
        from mem0.vector_stores.langchain import Langchain as _Mem0LangchainVectorStore

        if effective_embedding_dim is not None:
            _Mem0LangchainVectorStore.embedding_model_dims = effective_embedding_dim
    except Exception:
        pass
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
