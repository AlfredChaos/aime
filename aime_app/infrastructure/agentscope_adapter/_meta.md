# agentscope_adapter/

本目录是对 AgentScope 的适配层：把 `application/ports.py` 中的抽象（如 `AgentBuilder`）落到具体的 AgentScope 组件（如 `ReActAgent`）上，并负责在构建期完成依赖组装（prompt、模型、记忆、工具包等）。

## 关键文件

- `react_agent_builder.py`：实现 `AgentBuilder`，构建可运行的 ReActAgent

