"""
[Input] 运行目录下的 tools/ 与 skills/，以及 agentscope.tool.Toolkit 实例。
[Output] 提供 create_toolkit()，自动加载工具与技能，并注册“技能按需读取”工具函数。
[Pos] Agent 启动引导层：把“目录化扩展（tools/skills）”打通到 AgentScope 的 Toolkit。

关于“渐进式披露（Progressive Disclosure）”
------------------------------------------
目标：让智能体在不把所有能力细节一次性塞进 Prompt 的前提下，仍能“发现并按需获取”能力说明。

在本项目里，“渐进式披露”分两层：
1) 启动时披露“目录级索引（Index）”
   - 仅把每个 Skill 的 name/description/目录路径加入系统提示词（SKILL.md 的 YAML front matter + 简要正文）。
   - 这样模型知道“有哪些技能存在、它们大致用于什么”，但不会把技能的全部实现细节一次性灌入上下文。

2) 运行时披露“内容级细节（Details on demand）”
   - 通过工具 read_skill_markdown / read_skill_file，让模型在需要时再读取具体技能文件内容。
   - 这把信息获取从“推送（push）”改为“拉取（pull）”，降低 token 溢出与注意力分散。

这套机制的核心是：让模型先获得“可检索的目录索引”，再用工具按需读取局部细节。
"""

from __future__ import annotations

import hashlib
import importlib.util
import os
from pathlib import Path
from typing import Iterable

from agentscope.tool import Toolkit


def _iter_python_files(root_dir: Path) -> Iterable[Path]:
    if not root_dir.exists():
        return []
    for path in root_dir.rglob("*.py"):
        if path.name.startswith("_"):
            continue
        yield path


def _load_module_from_path(file_path: Path):
    module_key = hashlib.sha256(str(file_path).encode("utf-8")).hexdigest()[:16]
    module_name = f"_auto_tools_{module_key}"
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Failed to load module spec from {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def discover_and_register_tools(toolkit: Toolkit, tools_dir: str) -> list[str]:
    loaded: list[str] = []
    root = Path(tools_dir)
    for file_path in _iter_python_files(root):
        module = _load_module_from_path(file_path)

        register = getattr(module, "register", None)
        if callable(register):
            register(toolkit)
            loaded.append(str(file_path))
            continue

        tool_functions = getattr(module, "TOOL_FUNCTIONS", None)
        if tool_functions is None:
            continue

        if not isinstance(tool_functions, (list, tuple)):
            raise TypeError(
                f"{file_path} TOOL_FUNCTIONS must be a list/tuple of callables",
            )

        for item in tool_functions:
            if callable(item):
                toolkit.register_tool_function(item)
                continue

            if isinstance(item, tuple) and len(item) == 2 and callable(item[0]) and isinstance(item[1], dict):
                toolkit.register_tool_function(item[0], preset_kwargs=item[1])
                continue

            if isinstance(item, dict):
                fn = item.get("fn") or item.get("function")
                preset_kwargs = item.get("preset_kwargs")
                if not callable(fn):
                    raise TypeError(f"{file_path} TOOL_FUNCTIONS dict item missing callable fn")
                if preset_kwargs is not None and not isinstance(preset_kwargs, dict):
                    raise TypeError(f"{file_path} TOOL_FUNCTIONS dict item preset_kwargs must be dict")
                toolkit.register_tool_function(fn, preset_kwargs=preset_kwargs)
                continue

            raise TypeError(
                f"{file_path} TOOL_FUNCTIONS item must be callable, (callable, dict), or dict",
            )
        loaded.append(str(file_path))

    return loaded


def discover_and_register_skills(toolkit: Toolkit, skills_dir: str) -> list[str]:
    root = Path(skills_dir)
    if not root.exists():
        return []

    registered: list[str] = []
    for skill_dir in sorted([p for p in root.iterdir() if p.is_dir()]):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        toolkit.register_agent_skill(str(skill_dir))
        registered.append(str(skill_dir))

    return registered


def create_toolkit(project_root: str | None = None) -> Toolkit:
    root = Path(project_root or os.getcwd()).resolve()
    tools_dir = str(Path(os.environ.get("TOOLS_DIR", root / "tools")).expanduser())
    skills_dir = str(Path(os.environ.get("SKILLS_DIR", root / "skills")).expanduser())

    toolkit = Toolkit()

    tool_mod = __import__("agentscope.tool", fromlist=["*"])
    for builtin_name in [
        "execute_python_code",
        "execute_shell_command",
        "view_text_file",
        "write_text_file",
        "insert_text_file",
    ]:
        builtin = getattr(tool_mod, builtin_name, None)
        if callable(builtin):
            toolkit.register_tool_function(builtin)

    discover_and_register_tools(toolkit, tools_dir)
    discover_and_register_skills(toolkit, skills_dir)

    return toolkit
