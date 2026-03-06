# Aime App（aime_app）协作指南

本文件面向后续的人类与 AI 协作维护，目标是让任何人只读这一份文档，就能理解 `aime_app` 的结构、运行方式、关键调用链，以及如何安全扩展。

## 这是什么

`aime_app` 是一个以 AgentScope 为核心的对话应用层实现：通过 CLI 入口启动一个 ReAct 智能体，使用 Gemini 模型，结合 Langfuse 托管系统提示词，并用 Mem0 + LanceDB 作为长期记忆向量存储。应用通过“分层结构”隔离入口、用例、领域模型与基础设施实现。

## 目录结构（只列关键项）

```
aime_app/
  application/        # 用例与端口（协议/接口）
  domain/             # 纯领域对象/策略
  entrypoints/        # 入口（CLI），负责 I/O 与参数解析
  infrastructure/     # 具体实现：AgentScope 适配、模型工厂、存储、patch、装配(wiring)
```

对应的详细规则分别在各目录的 `AGENTS.md` 中维护。

## 推荐运行方式

项目根目录的 [main.py](file:///home/shixuan/code/agentscope-research/main.py) 是推荐入口：它会加载 `.env`，应用必要的 patch，然后启动交互式 CLI。

```bash
export GEMINI_API_KEY="..."
python main.py
```

交互模式支持：
- 纯文本：直接输入发送
- 图片：`/img <path> [可选描述]`
- 退出：`/exit`

入口实现见 [chat_cli.py](file:///home/shixuan/code/agentscope-research/aime_app/entrypoints/chat_cli.py)。

## 关键调用链（从入口到模型）

### 单智能体聊天（默认）

1. `main.py` 调用 `aime_app.entrypoints.chat_cli.main()`
2. `chat_cli.main_async()` 通过 [wiring.py](file:///home/shixuan/code/agentscope-research/aime_app/infrastructure/wiring.py) 创建用例 `RunChat`
3. `RunChat.create_agent()` 调用 `AgentBuilder.build()`
4. `ReActAgentBuilder.build()` 组装：
   - Langfuse prompt（失败则 fallback）
   - Gemini chat/embedding model
   - LanceDB + Mem0 长期记忆
   - Toolkit（自动发现 tools/skills）
   - ReActAgent（AgentScope）

核心装配见：
- [wiring.py](file:///home/shixuan/code/agentscope-research/aime_app/infrastructure/wiring.py)
- [react_agent_builder.py](file:///home/shixuan/code/agentscope-research/aime_app/infrastructure/agentscope_adapter/react_agent_builder.py)

### 团队接力（已具备用例与编排器，缺少默认 CLI）

代码中已具备 Team Chat 的装配函数 `create_run_team_chat()` 与用例 `RunTeamChat`：
- [wiring.py](file:///home/shixuan/code/agentscope-research/aime_app/infrastructure/wiring.py)
- [run_team_chat.py](file:///home/shixuan/code/agentscope-research/aime_app/application/usecases/run_team_chat.py)
- [sequential_team_orchestrator.py](file:///home/shixuan/code/agentscope-research/aime_app/infrastructure/orchestration/sequential_team_orchestrator.py)

最小调用示例（供二次开发参考）：

```python
import asyncio
from agentscope.message import Msg
from aime_app.infrastructure.wiring import create_run_team_chat

async def demo():
    run_team_chat = create_run_team_chat()
    result = await run_team_chat.run(msg=Msg(name="user", role="user", content="你好"))
    print(result)

asyncio.run(demo())
```

## 配置项（环境变量约定）

必需：
- `GEMINI_API_KEY`：Gemini API Key（未设置会直接抛错）

常用可选：
- `GEMINI_BASE_URL`：Gemini API Base URL（默认 `https://aicode.cat`）
- `GEMINI_CHAT_MODEL`：聊天模型名（默认 `gemini-2.5-flash`）
- `GEMINI_EMBEDDING_MODEL`：Embedding 模型名（默认 `text-embedding-004`）
- `GEMINI_EMBEDDING_DIMS` / `EMBEDDING_DIMS`：Embedding 维度（不填会探测）

Langfuse（prompt 读取/写入）：
- `LANGFUSE_PROMPT_NAME`：系统提示词名称（默认 `aime-system-prompt`）
- `LANGFUSE_PROMPT_FALLBACK`：Langfuse 不可用时的 fallback 文本
- 其余 Langfuse SDK 连接参数遵循 Langfuse 官方环境变量约定（例如 host、keys 等）

长期记忆（LanceDB）：
- `LANCEDB_URI`：LanceDB 路径（默认 `~/.lancedb`）
- `LANCEDB_TABLE_NAME`：表名（默认 `mem0_memory`）

工具与技能自动发现：
- `TOOLS_DIR`：tools 目录（默认 `<project_root>/tools`）
- `SKILLS_DIR`：skills 目录（默认 `<project_root>/skills`）

## Prompt 管理（Langfuse）

`aime_app.entrypoints.upload_prompt_cli` 提供了一个最小上传/更新系统提示词的 CLI。
推荐通过环境变量传入内容，便于 CI/脚本化：

```bash
export LANGFUSE_PROMPT_NAME="aime-system-prompt"
export LANGFUSE_PROMPT_CONTENT="你是一个名为 Aime 的智能助手..."
python -c "from aime_app.entrypoints.upload_prompt_cli import main; main()"
```

实现见 [upload_prompt_cli.py](file:///home/shixuan/code/agentscope-research/aime_app/entrypoints/upload_prompt_cli.py) 与 [langfuse_repo.py](file:///home/shixuan/code/agentscope-research/aime_app/infrastructure/prompts/langfuse_repo.py)。

## 工具与技能（Tools/Skills）如何接入

智能体的 toolkit 在 [toolkit_factory.py](file:///home/shixuan/code/agentscope-research/aime_app/infrastructure/toolkit/toolkit_factory.py) 中自动发现并注册：

### Tools（Python 函数）

在 `TOOLS_DIR` 指向的目录中：
- 若模块提供 `register(toolkit)`，将优先调用
- 或提供 `TOOL_FUNCTIONS`（list/tuple），元素可为：
  - 可调用对象
  - `(callable, preset_kwargs: dict)`
  - `{"fn": callable, "preset_kwargs": {...}}`

### Skills（AgentScope skill 目录）

在 `SKILLS_DIR` 指向的目录中，每个子目录若存在 `SKILL.md`，会被注册为技能。

## 变更与协作规则（强约束）

- 保持分层：入口只做 I/O；用例只编排；领域只放纯逻辑；基础设施放第三方与 I/O。
- 新增环境变量：必须同步更新本文件的“配置项”章节与对应模块的 `AGENTS.md`。
- 新增工具/技能：优先通过 tools/skills 扩展，而不是把能力硬编码进智能体构建器。
- 不要在 `domain/` 引入基础设施依赖；不要在 `application/` 直接依赖第三方 SDK。

## 常见问题定位

- 报错 `GEMINI_API_KEY is required`：未设置 `GEMINI_API_KEY`，见 [react_agent_builder.py](file:///home/shixuan/code/agentscope-research/aime_app/infrastructure/agentscope_adapter/react_agent_builder.py)。
- Langfuse 不可用时 prompt 仍能工作：会走 fallback（`source="fallback"`），见 [langfuse_repo.py](file:///home/shixuan/code/agentscope-research/aime_app/infrastructure/prompts/langfuse_repo.py)。
- 向量维度不一致导致旧表不可用：会根据维度自动派生表名（`<table>_d<dim>`），见 [lancedb_store.py](file:///home/shixuan/code/agentscope-research/aime_app/infrastructure/vectorstores/lancedb_store.py)。

