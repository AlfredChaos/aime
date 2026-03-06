# infrastructure/ 协作指南

`infrastructure/` 放所有“具体实现”与“第三方集成”，包括模型工厂、向量库、Langfuse、AgentScope 适配、patch 以及装配（wiring）。

## 当前模块地图

- [wiring.py](file:///home/shixuan/code/agentscope-research/aime_app/infrastructure/wiring.py)
  - 应用装配入口：把 `application/` 用例与 `infrastructure/` 实现拼起来
- `agentscope_adapter/`
  - [react_agent_builder.py](file:///home/shixuan/code/agentscope-research/aime_app/infrastructure/agentscope_adapter/react_agent_builder.py)
  - 负责构建 ReActAgent：prompt、模型、记忆、工具包、长期记忆配置
- `models/`
  - [gemini_factory.py](file:///home/shixuan/code/agentscope-research/aime_app/infrastructure/models/gemini_factory.py)
  - 统一创建 chat 与 embedding 模型实例
- `prompts/`
  - [langfuse_repo.py](file:///home/shixuan/code/agentscope-research/aime_app/infrastructure/prompts/langfuse_repo.py)
  - 以 Langfuse 作为 prompt 仓库（带 fallback）
- `vectorstores/`
  - [lancedb_store.py](file:///home/shixuan/code/agentscope-research/aime_app/infrastructure/vectorstores/lancedb_store.py)
  - LanceDB 向量存储适配：embedding 维度探测、表名派生、Mem0 向量配置
- `toolkit/`
  - [toolkit_factory.py](file:///home/shixuan/code/agentscope-research/aime_app/infrastructure/toolkit/toolkit_factory.py)
  - 自动发现并注册 tools/skills，最终注入到 AgentScope Toolkit
- `orchestration/`
  - [sequential_team_orchestrator.py](file:///home/shixuan/code/agentscope-research/aime_app/infrastructure/orchestration/sequential_team_orchestrator.py)
  - 最小团队接力编排器：按成员顺序串行执行
- `patches/`
  - [__init__.py](file:///home/shixuan/code/agentscope-research/aime_app/infrastructure/patches/__init__.py) 提供 `apply_all()`
  - 通过 monkey patch 修复/兼容 AgentScope 与 Google GenAI SDK 的边界问题
- [nulls.py](file:///home/shixuan/code/agentscope-research/aime_app/infrastructure/nulls.py)
  - `NoopGateway` / `NoopScheduler`：未配置时的空实现/占位

## 约束

- 任何第三方 SDK 交互都集中在 `infrastructure/`，并通过 `application/ports.py` 的 Protocol 暴露给用例层。
- `wiring.py` 是默认装配点：如果要切换实现（例如换模型、换存储），优先通过 wiring 替换依赖，而不是修改用例层。
- patch 必须是幂等的（重复调用不应改变行为），当前实现以“打补丁标记属性”方式保证。

