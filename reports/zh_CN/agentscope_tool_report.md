# AgentScope 功能模块调研报告：工具 (Tool)

## 1. 模块定位
**“工具 (Tool) 是智能体的手和脚，让 AI 能够突破文本生成的局限，与真实世界交互。”**
LLM 本身只能生成文字，不能上网、不能查数据库、不能运行代码。`Toolkit` 模块就是负责把这些能力封装成 AI 能理解的“技能包”，让智能体按需调用。

## 2. 核心概念与术语拆解

### 2.1 Toolkit (工具箱)
*   **通俗解释**：一个装着各种工具的盒子。
*   **类比**：多啦A梦的口袋。里面可能有“任意门”（联网工具）、“竹蜻蜓”（文件读取工具）。

### 2.2 Tool Function (工具函数)
*   **通俗解释**：具体的某一项技能。在 Python 中，它就是一个普通的函数，但必须写清楚注释（Docstring），告诉 AI 这个函数是干嘛的、参数是什么。
*   **类比**：口袋里的具体道具。比如“螺丝刀”，说明书上写着“用于拧螺丝，需要指定螺丝大小”。

### 2.3 JSON Schema
*   **通俗解释**：AI 能读懂的“工具说明书”。AgentScope 会自动把你的 Python 函数注释转换成这种格式发给模型。
*   **类比**：把中文说明书翻译成 AI 专用的机器语言。

---

## 3. 最小可运行示例 (Minimal Runnable Example)

这个示例展示如何定义一个自定义工具（计算器），并让智能体调用它。

```python
# main.py
import agentscope
from agentscope.agent import ReActAgent
from agentscope.tool import Toolkit, ToolResponse
from agentscope.message import Msg, TextBlock
from agentscope.model import DashScopeChatModel

# 依赖安装： pip install agentscope

# 1. 定义工具函数 (必须有清晰的 Docstring 和类型注解)
def sum_two_numbers(a: int, b: int) -> ToolResponse:
    """
    计算两个数字的和。
    
    Args:
        a (int): 第一个加数。
        b (int): 第二个加数。
    """
    result = a + b
    # 返回标准 ToolResponse
    return ToolResponse(content=[TextBlock(text=str(result))])

def main():
    agentscope.init(project="ToolDemo")
    
    # 2. 创建工具箱并注册工具
    toolkit = Toolkit()
    toolkit.register_tool_function(sum_two_numbers)
    
    # 3. 创建智能体并挂载工具箱
    agent = ReActAgent(
        name="MathBot",
        sys_prompt="你是一个计算助手，遇到加法问题请使用工具。",
        model=DashScopeChatModel(model_name="qwen-plus"),
        toolkit=toolkit # 关键步骤：给 Agent 装备工具
    )
    
    # 4. 测试调用
    msg = Msg("User", "请帮我计算 12345 加 67890 等于多少？", "user")
    agent(msg)

if __name__ == "__main__":
    main()
```

---

## 4. 典型应用场景

### 场景 1：使用内置工具 (代码执行/文件操作)
AgentScope 内置了 `execute_python_code` 等强力工具，无需自己写。

```python
from agentscope.tool import execute_python_code, execute_shell_command

# 直接注册内置工具
toolkit = Toolkit()
toolkit.register_tool_function(execute_python_code) # 让 AI 能写 Python 代码并运行
toolkit.register_tool_function(execute_shell_command) # 让 AI 能执行 Shell 命令

# Agent 现在是一个能写代码的程序员了
```

### 场景 2：查询实时信息 (如天气/股票)
```python
def get_weather(city: str) -> ToolResponse:
    """
    查询指定城市的天气。
    Args:
        city (str): 城市名称，如 "Beijing".
    """
    # 这里模拟 API 调用
    mock_data = {"Beijing": "Sunny, 25°C", "Shanghai": "Rainy, 20°C"}
    weather = mock_data.get(city, "Unknown")
    return ToolResponse(content=[TextBlock(text=weather)])

toolkit.register_tool_function(get_weather)
```

---

## 5. 扩展能力调研

### 5.1 动态工具组 (Tool Groups)
如果工具有几百个，全塞给 LLM 会导致 Token 溢出且变笨。可以使用“工具组”动态激活/冻结。
```python
# 创建一个名为 "browser" 的工具组，默认不激活
toolkit.create_tool_group("browser", active=False)
toolkit.register_tool_function(open_url, group_name="browser")

# 智能体可以通过调用元工具 `reset_equipped_tools` 来自己决定何时激活这个组
toolkit.register_tool_function(toolkit.reset_equipped_tools)
```

### 5.2 智能体技能 (Agent Skill)
类似 Anthropic 的概念，将一组文件（代码+说明文档）打包成一个 Skill，动态加载。
```python
# 目录结构:
# my_skill/
#   SKILL.md (说明书)
#   script.py

toolkit.register_agent_skill("path/to/my_skill")
```

---

## 6. 常见坑与调试技巧

1.  **Docstring 写得太烂**：
    *   **现象**：智能体瞎填参数，或者根本不调用工具。
    *   **解决**：Docstring 是给 AI 看的“Prompt”。必须详细描述函数功能，每个参数的含义、格式、取值范围。
2.  **缺少类型注解**：
    *   **现象**：`register_tool_function` 报错，无法生成 JSON Schema。
    *   **解决**：Python 函数参数必须加类型 Hint，如 `a: int`, `b: str`。
3.  **返回值格式错误**：
    *   **现象**：报错 `ToolResponse expected`。
    *   **解决**：工具函数必须返回 `ToolResponse` 对象，不要直接返回字符串或数字。

## 7. 进一步阅读
*   **官方文档**: [Tool Tutorial](https://doc.agentscope.io/zh_CN/tutorial/task_tool.html)
*   **内置工具列表**: 查看 `agentscope.tool` 源码。
