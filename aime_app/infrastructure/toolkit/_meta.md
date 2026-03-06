# toolkit/

本目录负责工具与技能的装配：自动发现并注册 tools/skills，把可调用函数与技能目录注入 AgentScope 的 `Toolkit`。

## 关键文件

- `toolkit_factory.py`：发现并注册 tools/skills，并注册内置工具函数

