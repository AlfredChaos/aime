# application/ 协作指南

`application/` 放“用例（Use Case）”与“端口（Ports/Protocols）”，负责把业务动作组织成可执行流程，并用 Protocol 隔离基础设施实现。

## 你应该在这里做什么

- 新增/调整用例：把“用户想完成的一件事”抽象成一个类/函数（通常是 `usecases/` 下的类）。
- 定义端口：用 `Protocol` 描述外部能力（例如构建 Agent、编排团队、调度、网关等），避免在用例中直接依赖第三方 SDK。
- 保持可测试：用例应能在不启动真实模型/数据库的前提下被替换依赖进行测试。

## 你不应该在这里做什么

- 不要在 `application/` 直接 import Langfuse / LanceDB / Mem0 / AgentScope 等第三方实现。
- 不要在用例中读环境变量、拼装 SDK 配置、处理文件/网络 I/O。

## 当前包含内容

- [ports.py](file:///home/shixuan/code/agentscope-research/aime_app/application/ports.py)
  - `ChatAgent`：对话 agent 的最小调用协议（`await agent(msg)`）
  - `AgentBuilder`：构建 agent 的协议（`await build()`）
  - `TeamOrchestrator`：团队编排协议（`await run(team_spec, msg)`）
  - `Scheduler` / `Gateway`：预留端口（当前默认实现为 Noop）
- `usecases/`
  - [run_chat.py](file:///home/shixuan/code/agentscope-research/aime_app/application/usecases/run_chat.py)：构建单智能体并返回
  - [run_team_chat.py](file:///home/shixuan/code/agentscope-research/aime_app/application/usecases/run_team_chat.py)：以 TeamSpec + Orchestrator 执行团队接力

## 扩展示例：新增一个用例

规则：用例只依赖 `ports` 与 `domain`，并通过构造函数注入外部能力。

```python
from __future__ import annotations

from aime_app.application.ports import Scheduler

class RunSomethingLater:
    def __init__(self, *, scheduler: Scheduler):
        self._scheduler = scheduler

    def schedule(self) -> str:
        return self._scheduler.schedule(job_spec={"type": "something"}, handler=self._handler)

    async def _handler(self) -> None:
        ...
```

