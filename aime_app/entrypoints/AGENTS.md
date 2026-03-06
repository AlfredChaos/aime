# entrypoints/ 协作指南

`entrypoints/` 提供面向“人类/脚本”的启动入口，主要职责是：
- 解析输入（CLI/环境变量/文件）
- 构造消息对象并调用用例
- 做最薄的一层错误处理与输出展示

这里不应该承载业务规则与复杂装配逻辑；装配逻辑统一放在 `infrastructure/wiring.py`。

## 当前入口

- [chat_cli.py](file:///home/shixuan/code/agentscope-research/aime_app/entrypoints/chat_cli.py)
  - 交互式对话：支持文本与 `/img` 图片输入
  - 通过 `create_run_chat()` 启动并拿到 `agent`，随后循环 `await agent(msg)`
  - 若安装了 Langfuse，会通过 `langfuse.observe` 包裹 `main_async`
- [upload_prompt_cli.py](file:///home/shixuan/code/agentscope-research/aime_app/entrypoints/upload_prompt_cli.py)
  - 用环境变量驱动，将文本 prompt 写入 Langfuse

## 约束

- 入口层不要 import `agentscope` 的复杂对象并在此处组装；组装放 `infrastructure/`。
- 入口层的错误信息保持英文（便于搜索），用户提示可为中文。

