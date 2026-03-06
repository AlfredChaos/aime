# usecases/

本目录承载应用层用例（Use Case）：将一次“用户意图/系统动作”组织为可执行流程，并通过 `application/ports.py` 注入外部能力实现。

## 边界

- 允许依赖：`aime_app.application.*`、`aime_app.domain.*`、标准库
- 禁止依赖：`aime_app.infrastructure.*` 与任何第三方 SDK（由 wiring 负责装配）

## 当前用例

- `run_chat.py`：构建并返回单个可对话 agent
- `run_team_chat.py`：通过编排器执行团队接力

