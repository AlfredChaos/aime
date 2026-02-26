# AgentScope Research

本项目包含关于 AgentScope 的研究代码、Langfuse 集成以及相关报告。

## 目录结构

### 1. AgentScope 示例 (Root)
根目录下包含基于 Python 的 AgentScope 示例代码：
- `main.py`: ReAct 智能体示例，使用 Gemini 模型。
- `fix_agentscope_gemini.py`: AgentScope 对接 Gemini 的修复补丁。
- `fix_gemini_thinking_formatter.py`: Gemini 思考过程格式化的修复补丁。

**运行方式**:
```bash
# 确保已设置 GEMINI_API_KEY 环境变量
python main.py
```

### 2. Langfuse 集成 (`langfuse/`)
包含 Langfuse 的相关实现，用于 LLM 可观测性和分析。
- `web/`: Next.js 前端项目。
- `worker/`: Node.js 后台 Worker 服务。

**注意**: 请参考各子目录下的说明进行配置和运行。

### 3. 研究报告 (`reports/`)
包含关于 AgentScope 的分析报告和相关文档。
- `reports/zh_CN/`: 中文报告目录。

## 环境要求

- Python 3.10+
- Node.js (用于 Langfuse 部分)
- AgentScope
- Google Generative AI SDK

## 快速开始

1. 克隆仓库
2. 安装 Python 依赖 (建议使用虚拟环境)
   ```bash
   pip install agentscope google-generativeai
   ```
3. 设置环境变量
   ```bash
   export GEMINI_API_KEY="your_api_key_here"
   ```
4. 运行示例
   ```bash
   python main.py
   ```
