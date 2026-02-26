# AgentScope 全景速览：零基础入门指南

## 1. AgentScope 是什么？

想象一下，你是一家新公司的 CEO。你需要招聘员工、组建团队、分配任务，最终完成复杂的项目。
**AgentScope 就是一个让你在电脑上“开公司”的工具包。**

*   **智能体 (Agent)**：就是你的**员工**。有的负责写代码，有的负责翻译，有的负责查资料。他们不仅能聊天，还能真的干活。
*   **工具 (Tool)**：就是员工用的**电脑、软件、U盘**。有了工具，员工才能上网、存文件、跑程序。
*   **工作流 (Workflow)**：就是公司的**管理制度**。是让大家坐在一起头脑风暴（群聊），还是流水线式的一个接一个干（管道）。
*   **记忆 (Memory)**：就是员工的**大脑和笔记本**。记住老板刚才说了什么，也记住以前的项目经验。

简单来说，**AgentScope 帮你把大模型（如 GPT-4, Qwen）包装成能干活的“数字员工”，并把他们组织起来解决复杂问题。**

---

## 2. AgentScope 能干什么？

它能帮你构建各种 AI 应用，从简单的聊天机器人到复杂的自动化系统：

1.  **超级助理**：不仅能陪聊，还能帮你读取本地文件、写 Python 代码分析 Excel 表格、甚至帮你发邮件。
2.  **多角色辩论/游戏**：创建一个“狼人杀”游戏，或者让一个“激进派”和一个“保守派”AI 辩论某个话题，你在旁边吃瓜。
3.  **自动化流水线**：
    *   用户输入一句话 → **翻译员**翻译成英文 → **润色师**修改语法 → **程序员**写成代码。
    *   全程自动流转，不需要你插手。
4.  **连接真实世界**：通过 MCP 协议，让 AI 连接你的数据库、Notion、飞书，成为你的业务中枢。

---

## 3. 我该从哪里开始学？

作为初学者，不要试图一口气吃成胖子。请按照以下顺序阅读我们为你准备的调研报告：

### 第一步：招募你的第一个员工 (Agent)
*   **阅读目标**：[agentscope_agent_report.md](./agentscope_agent_report.md)
*   **你将学会**：如何创建一个最简单的 AI，给它起名字，给它设定人设（System Prompt）。
*   **核心代码**：`agent = ReActAgent(name="Friday", ...)`

### 第二步：给员工配备工具 (Tool)
*   **阅读目标**：[agentscope_tool_report.md](./agentscope_tool_report.md)
*   **你将学会**：光会说话没用，要让 AI 能算数、能写代码。学会如何把 Python 函数变成 AI 的工具。
*   **核心代码**：`toolkit.register_tool_function(my_function)`

### 第三步：组建团队与流程 (Workflow)
*   **阅读目标**：[agentscope_workflow_report.md](./agentscope_workflow_report.md)
*   **你将学会**：如何让两个 AI 配合工作。是让他们在群里聊天（MsgHub），还是像传球一样接力（Pipeline）。
*   **核心代码**：`Pipeline([agent_a, agent_b])`

### 第四步：增强记忆力 (Memory)
*   **阅读目标**：[agentscope_memory_report.md](./agentscope_memory_report.md)
*   **你将学会**：如何让 AI 记住很久以前的事情，或者把重要的知识存进数据库。
*   **核心概念**：短期记忆 vs 长期记忆。

### 第五步：连接外部世界 (MCP)
*   **阅读目标**：[agentscope_mcp_report.md](./agentscope_mcp_report.md)
*   **你将学会**：进阶玩法。如何使用标准协议连接现成的外部服务（如高德地图）。

---

## 4. 如何运行示例代码？

我们在每个报告中都准备了“最小可运行示例”。请按以下步骤操作：

1.  **安装环境**：
    确保你安装了 Python 3.10 或以上版本。
    ```bash
    pip install agentscope
    ```

2.  **配置模型 Key**：
    AgentScope 需要大模型（如通义千问、GPT-4）的支持。你需要去阿里云 DashScope 或 OpenAI 申请一个 API Key。
    **强烈建议**将 Key 设置为环境变量，这样不用每次都在代码里改：
    ```bash
    # Linux/Mac
    export DASHSCOPE_API_KEY="sk-..."
    
    # Windows (PowerShell)
    $env:DASHSCOPE_API_KEY="sk-..."
    ```

3.  **运行代码**：
    将报告中的代码复制保存为 `demo.py`，然后在终端运行：
    ```bash
    python demo.py
    ```

---

## 5. 遇到问题怎么办？

*   **报错 "api_key is not set"**：检查环境变量是否配置成功。
*   **报错 "ImportError"**：可能是版本过低，运行 `pip install agentscope --upgrade` 更新。
*   **AI 答非所问**：检查你的 `sys_prompt`（系统提示词）是否写得足够清楚。Prompt 是 AI 的灵魂。

祝你在 AgentScope 的世界里玩得开心！🚀
