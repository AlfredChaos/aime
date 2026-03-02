from __future__ import annotations

import json
import os
import re
from pathlib import Path

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


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


def _get_skills_index() -> list[dict[str, str]]:
    skills_dir = Path(os.environ.get("SKILLS_DIR", _project_root() / "skills")).expanduser()
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
                "path": str(child),
            },
        )
    return items


def count_words(text: str) -> ToolResponse:
    """
    Count words in the given text.

    Args:
        text (str):
            Any text.
    """
    words = re.findall(r"\b\w+\b", text)
    return ToolResponse(content=[TextBlock(text=str(len(words)))])


def extract_top_lines(text: str, max_lines: int = 5) -> ToolResponse:
    """
    Extract the first N non-empty lines.

    Args:
        text (str):
            Any text with line breaks.
        max_lines (int):
            Maximum number of non-empty lines to return.
    """
    if max_lines <= 0:
        raise ValueError("max_lines must be positive")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return ToolResponse(content=[TextBlock(text="\n".join(lines[:max_lines]))])


def list_skills() -> ToolResponse:
    """
    列出 skills/ 目录下所有可用技能（只返回索引，不返回全文内容）。
    """
    skills = _get_skills_index()
    return ToolResponse(content=[TextBlock(text=json.dumps(skills, ensure_ascii=False, indent=2))])


def read_skill_markdown(skill_dir: str) -> ToolResponse:
    """
    读取指定技能目录下的 SKILL.md 全文。

    Args:
        skill_dir (str):
            skills/ 下的子目录名（不是 YAML front matter 里的 name 字段）。
    """
    return read_skill_file(skill_dir=skill_dir, relative_path="SKILL.md")


def read_skill_file(skill_dir: str, relative_path: str, max_chars: int = 12000) -> ToolResponse:
    """
    读取指定技能目录下的任意文件（用于按需披露技能细节）。

    Args:
        skill_dir (str):
            skills/ 下的子目录名。
        relative_path (str):
            相对 skill 目录的路径（例如 \"prompt.txt\" 或 \"scripts/example.py\"）。
        max_chars (int):
            读取内容的最大字符数，超出将截断。
    """
    if max_chars <= 0:
        raise ValueError("max_chars must be positive")

    skills_dir = Path(os.environ.get("SKILLS_DIR", _project_root() / "skills")).expanduser().resolve()
    base = (skills_dir / skill_dir).resolve()
    if not str(base).startswith(str(skills_dir)):
        raise ValueError("Invalid skill_dir")

    target = (base / relative_path).resolve()
    if not str(target).startswith(str(base)):
        raise ValueError("Invalid relative_path")

    if not target.exists() or not target.is_file():
        raise FileNotFoundError(f"Skill file not found: {skill_dir}/{relative_path}")

    content = target.read_text(encoding="utf-8", errors="replace")
    if len(content) > max_chars:
        content = content[:max_chars]
    return ToolResponse(content=[TextBlock(text=content)])


TOOL_FUNCTIONS = [count_words, extract_top_lines, list_skills, read_skill_markdown, read_skill_file]
