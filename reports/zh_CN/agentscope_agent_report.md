# AgentScope 功能模块调研报告：智能体 (Agent)

## 1. 模块定位
**“智能体 (Agent) 是 AgentScope 的核心执行单元，负责像人一样思考（推理）、做事（调用工具）并与外界交互。”**
如果把 AgentScope 比作一个公司，那么 `Agent` 就是公司里的员工，他们有各自的职责（Role），能听懂指令（Prompt），有记忆（Memory），并且能使用工具（Tools）完成任务。

## 2. 核心概念与术语拆解

### 2.1 ReAct (Reasoning + Acting)
*   **通俗解释**：一种让 AI “先想后做” 的模式。传统的 AI 像个只会说话的鹦鹉，而 ReAct 智能体像个厨师：先看菜谱思考步骤（Reasoning），然后动手切菜炒菜（Acting），再观察菜熟没熟（Observation），如此循环。
*   **类比**：你让实习生去买咖啡。
    *   **普通 LLM**：直接说“好的，我买到了”（其实在瞎编）。
    *   **ReAct Agent**：
        1.  **思考**：老板要拿铁，通过地图 App 查最近的星巴克。（Reasoning）
        2.  **行动**：调用“地图搜索”工具。（Acting）
        3.  **观察**：发现楼下就有一家。（Observation）
        4.  **思考**：我现在去买。（Reasoning）
        5.  **行动**：执行“购买”动作。（Acting）

### 2.2 实时介入 (Realtime Steering)
*   **通俗解释**：在智能体干活的过程中，人类可以随时喊“停”或者插嘴纠正它，而不是只能干等着它做完。
*   **类比**：你坐出租车（智能体是司机）。虽然你告诉了目的地，但在路上你发现走错路了，你可以立刻说“师傅，前面左转”，司机（智能体）会立刻响应你的新指令，而不是非要开到终点才理你。

### 2.3 记忆压缩 (Memory Compression)
*   **通俗解释**：当聊得太久，记忆太多记不住时，自动把之前的对话总结成摘要。
*   **类比**：开了一天的会，你不可能把每个人说的每个字都背下来（Token 溢出），而是会在笔记本上记下“上午讨论了 A 方案，结论是不行”（生成摘要），剩下的细节就忘掉了。

### 2.4 结构化输出 (Structured Output)
*   **通俗解释**：强制 AI 按规定的格式（如 JSON）回答，而不是随便乱说。
*   **类比**：去办护照填表。你不能在表格里写一篇散文介绍自己，必须在“姓名”栏填名字，在“年龄”栏填数字。

---

## 3. 最小可运行示例 (Minimal Runnable Example)

这是一个最简单的“回声”智能体示例。虽然它没有挂载复杂工具，但展示了 Agent 的最小生命周期。
**前置条件**：你需要配置 `DASHSCOPE_API_KEY` 环境变量，或者替换为其他兼容 OpenAI 格式的模型配置。

```python
# main.py
import os
import agentscope
from agentscope.agent import ReActAgent, UserAgent
from agentscope.message import Msg
from agentscope.model import DashScopeChatModel  # 或 OpenAIChatModel

# 依赖安装： pip install agentscope

def main():
    # 1. 初始化 (通常配置 studio_url 等，这里留空)
    agentscope.init(project="MyFirstAgent")

    # 2. 配置模型 (请确保环境变量中有 DASHSCOPE_API_KEY)
    # 如果没有 Key，AgentScope 会报错。这里假设你已经配置好了。
    model_config = DashScopeChatModel(
        model_name="qwen-plus",
        # api_key="sk-..." # 建议通过环境变量配置
    )

    # 3. 创建智能体
    # ReActAgent 是最通用的智能体类型
    bot = ReActAgent(
        name="Bot",
        sys_prompt="你是一个幽默的助手，喜欢在每句话结尾加一个emoji。",
        model=model_config,
    )
    
    user = UserAgent(name="User")

    # 4. 开始对话循环
    msg = Msg(name="User", content="你好，给我讲个冷笑话", role="user")
    
    # 打印用户消息
    print(f"\nUser: {msg.content}")
    
    # 智能体回复
    response = bot(msg)
    
    # 打印回复内容
    print(f"Bot: {response.content}")

if __name__ == "__main__":
    main()
```

---

## 4. 典型应用场景

### 场景 1：使用工具完成数学计算
当用户问“3.14 的 5 次方是多少”时，LLM 口算可能不准，使用 Python 工具最准确。

```python
import agentscope
from agentscope.agent import ReActAgent
from agentscope.tool import execute_python_code  # 内置的代码执行工具

# ... 初始化代码略 ...

# 注册工具
agent = ReActAgent(
    name="MathGenius",
    sys_prompt="你是一个数学专家，遇到计算问题请编写 Python 代码求解。",
    model=model_config,
    # 启用代码执行工具
    toolkit=[execute_python_code], 
    verbose=True # 显示思考过程
)

# 发送任务
msg = Msg("User", "计算 123456 * 789012，并告诉我结果。", role="user")
agent(msg)
```

### 场景 2：结构化数据提取
从非结构化文本中提取用户信息，用于存入数据库。

```python
from pydantic import BaseModel, Field

# 定义目标数据结构
class UserProfile(BaseModel):
    name: str = Field(description="用户姓名")
    age: int = Field(description="用户年龄")
    hobby: list[str] = Field(description="爱好列表")

# 调用时传入 structured_model
response = agent(
    Msg("User", "我是张三，今年18岁，喜欢唱、跳、Rap。", role="user"),
    structured_model=UserProfile # 强制要求返回这个结构
)

# 获取解析后的对象（response.metadata 中）
# 输出: {'name': '张三', 'age': 18, 'hobby': ['唱', '跳', 'Rap']}
```

---

## 5. 扩展能力调研

### 5.1 自定义智能体 (继承)
如果你需要一个特殊的智能体，比如“只在周五工作”的智能体，可以继承 `ReActAgent` 或 `AgentBase`。

```python
from agentscope.agent import AgentBase
from agentscope.message import Msg

class LazyAgent(AgentBase):
    def __init__(self, name, model):
        super().__init__(name=name, model=model)
    
    def reply(self, x: Msg = None) -> Msg:
        # 自定义逻辑
        import datetime
        if datetime.datetime.now().weekday() != 4: # 不是周五
            return Msg(self.name, "我只在周五工作，别烦我。", role="assistant")
        
        # 正常调用模型
        return self.model(x)
```

### 5.2 第三方可观测性 (Langfuse 集成)
AgentScope 通过 OpenTelemetry (OTel) 协议支持接入第三方平台（如 Langfuse、Arize-Phoenix）。
你需要先获取 Langfuse 的公钥/私钥，并配置 `OTEL_EXPORTER_OTLP_HEADERS` 环境变量。

**接入 Langfuse 步骤**：
1.  在 Langfuse 后台获取 `Public Key` 和 `Secret Key`。
2.  在代码初始化时配置 `tracing_url` 和环境变量。

```python
import os
import base64
import agentscope

# 1. 配置 Langfuse 认证信息
LANGFUSE_PUBLIC_KEY = "pk-lf-..."
LANGFUSE_SECRET_KEY = "sk-lf-..."
LANGFUSE_AUTH_STRING = f"{LANGFUSE_PUBLIC_KEY}:{LANGFUSE_SECRET_KEY}"
LANGFUSE_AUTH = base64.b64encode(LANGFUSE_AUTH_STRING.encode("utf-8")).decode("ascii")

# 设置 OTel Header
os.environ["OTEL_EXPORTER_OTLP_HEADERS"] = f"Authorization=Basic {LANGFUSE_AUTH}"

# 2. 初始化 AgentScope，指向 Langfuse 的 OTel 接入点
# 注意：不同区域（欧盟/美国）的 URL 可能不同，请参考 Langfuse 文档
agentscope.init(
    project="MyAgentProject",
    name="Run-001",
    tracing_url="https://cloud.langfuse.com/api/public/otel/v1/traces"
)
```

---

## 6. 常见坑与调试技巧

1.  **API Key 报错**：
    *   **现象**：`ValueError: api_key is not set`
    *   **解决**：确保环境变量 `DASHSCOPE_API_KEY` (或对应模型的 key) 已设置。推荐使用 `os.environ["..."]` 显式传入或在 `.env` 文件中配置。
2.  **工具调用失败/死循环**：
    *   **现象**：智能体反复调用同一个工具，或者参数一直传错。
    *   **解决**：检查 `sys_prompt` 中是否清晰描述了工具的用途和参数格式。ReAct 极其依赖 Prompt 的质量。
3.  **ImportError: cannot import name 'xxx'**：
    *   **现象**：版本不兼容。
    *   **解决**：确保安装的是最新版 `pip install agentscope --upgrade`。

## 7. 进一步阅读
*   **源码路径**: `src/agentscope/agent/react_agent.py` (核心逻辑)
*   **官方文档**: [AgentScope Tutorial - Agent](https://doc.agentscope.io/zh_CN/tutorial/task_agent.html)
