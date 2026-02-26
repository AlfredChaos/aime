# AgentScope 深度调研报告包

这份资源包包含对 AgentScope 框架的系统性调研，专为刚入门的开发者设计。我们剥离了复杂的专业术语，用通俗易懂的语言和最简代码示例，带你快速掌握 AgentScope 的核心能力。

## 📂 目录结构

```text
reports/zh_CN/
├── AgentScope_全景速览.md        # [推荐起点] 2000字快速了解 AgentScope 是什么
├── agentscope_agent_report.md    # 智能体：如何创建你的第一个数字员工
├── agentscope_tool_report.md     # 工具：给 AI 配备“双手”和“技能”
├── agentscope_workflow_report.md # 工作流：如何管理多人协作与流水线
├── agentscope_memory_report.md   # 记忆：让 AI 拥有“过目不忘”的能力
├── agentscope_mcp_report.md      # MCP：连接外部世界的通用接口
├── module_list.csv               # 完整功能模块清单 (Excel 可打开)
├── terms_v1.csv                  # 术语表 (中英对照 + 通俗解释)
└── *_raw.md                      # (归档用) 官方文档原始抓取内容
```

## 🚀 快速开始

### 1. 环境准备
确保你的电脑上安装了 Python 3.10 或更高版本。

```bash
# 安装核心库
pip install agentscope

# (可选) 如果需要使用数据库记忆
pip install sqlalchemy aiosqlite

# (可选) 如果需要使用 MCP 功能
pip install mcp
```

### 2. 配置模型 Key
AgentScope 运行需要大模型 API 的支持。推荐使用阿里云 DashScope (通义千问) 或 OpenAI 格式的 API。

**Linux / Mac:**
```bash
export DASHSCOPE_API_KEY="你的_API_KEY"
```

**Windows (PowerShell):**
```powershell
$env:DASHSCOPE_API_KEY="你的_API_KEY"
```

### 3. 运行示例
每个报告（`.md` 文件）中都包含一个“最小可运行示例”章节。
1. 打开报告，找到示例代码块。
2. 复制或者保存为 `demo.py`。
3. 在终端运行 `python demo.py`。

## ❓ 常见问题
如果在运行过程中遇到问题，请参考各报告末尾的“常见坑与调试技巧”章节。
