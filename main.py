
import asyncio
import os
import uuid
from pathlib import Path
from typing import Callable, Iterable

import fix_agentscope_gemini, fix_gemini_thinking_formatter
import importlib.util
from langfuse import Langfuse, observe
from dotenv import load_dotenv

from agentscope.agent import ReActAgent
from agentscope.embedding import GeminiTextEmbedding
from agentscope.formatter import GeminiChatFormatter
from agentscope.memory import InMemoryMemory, Mem0LongTermMemory
from agentscope.message import Msg
from agentscope.model import GeminiChatModel
from agentscope.tool import Toolkit, execute_python_code

# Load environment variables from .env file
load_dotenv()

# Apply patches
fix_agentscope_gemini.apply_patch()
fix_gemini_thinking_formatter.apply_patch()

# Initialize Langfuse client
langfuse = Langfuse()


def _project_root() -> Path:
    return Path(__file__).resolve().parent


def _parse_skill_front_matter(skill_md: Path) -> dict[str, str]:
    try:
        content = skill_md.read_text(encoding="utf-8")
    except Exception:
        return {}

    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}

    parsed: dict[str, str] = {}
    for line in lines[1:80]:
        if line.strip() == "---":
            break
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if key and value:
            parsed[key] = value
    return parsed


def _load_skills_index(skills_dir: Path) -> list[dict[str, str]]:
    if not skills_dir.exists() or not skills_dir.is_dir():
        return []

    items: list[dict[str, str]] = []
    for child in sorted(skills_dir.iterdir(), key=lambda p: p.name):
        if not child.is_dir():
            continue
        skill_md = child / "SKILL.md"
        if not skill_md.exists():
            continue
        fm = _parse_skill_front_matter(skill_md)
        items.append(
            {
                "dir": child.name,
                "name": fm.get("name", child.name),
                "description": fm.get("description", ""),
            },
        )
    return items


def _discover_tool_functions(tools_dir: Path) -> list[Callable]:
    if not tools_dir.exists() or not tools_dir.is_dir():
        return []

    tool_functions: list[Callable] = []
    for path in sorted(tools_dir.glob("*.py"), key=lambda p: p.name):
        if path.name.startswith("_"):
            continue
        module_name = f"global_tools.{path.stem}"
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            continue
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        funcs = getattr(module, "TOOL_FUNCTIONS", None)
        if isinstance(funcs, Iterable):
            for fn in funcs:
                if callable(fn):
                    tool_functions.append(fn)
    return tool_functions


def _build_sys_prompt(base_prompt: str, skills_index: list[dict[str, str]]) -> str:
    if not skills_index:
        return base_prompt

    lines = []
    for item in skills_index:
        name = item.get("name") or item.get("dir") or ""
        desc = (item.get("description") or "").strip()
        if desc:
            lines.append(f"- {name}: {desc}")
        else:
            lines.append(f"- {name}")

    skills_section = "\n".join(lines)
    return (
        f"{base_prompt}\n\n"
        f"可用 Skills（索引，按需读取细节）：\n{skills_section}\n\n"
        "使用方式：先调用 list_skills() 获取索引；确认要用哪个 Skill 后，再调用 "
        "read_skill_markdown(skill_dir) 或 read_skill_file(skill_dir, relative_path) 读取细节。"
    )


def _create_lancedb_vector_store(uri: str, table_name: str):
    from langchain_community.vectorstores import LanceDB as _LanceDB

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

    return LanceDBPrecomputedEmbeddings(uri=uri, table_name=table_name, embedding=None, mode="append")


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
    tools_dir = Path(os.environ.get("TOOLS_DIR", project_root / "tools")).expanduser()
    skills_dir = Path(os.environ.get("SKILLS_DIR", project_root / "skills")).expanduser()

    skills_index = _load_skills_index(skills_dir)
    sys_prompt_content = _build_sys_prompt(sys_prompt_content, skills_index)

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
    lancedb_vs = _create_lancedb_vector_store(uri=lancedb_uri, table_name=lancedb_table)

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
    toolkit = Toolkit()
    toolkit.register_tool_function(execute_python_code)
    for fn in _discover_tool_functions(tools_dir):
        toolkit.register_tool_function(fn)

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
        content="介绍一下你自己。如果让你自己设定自己的性格爱好，你会怎么做？",
        role="user",
    )

    await aime(msg)


if __name__ == "__main__":
    asyncio.run(creating_react_agent())
