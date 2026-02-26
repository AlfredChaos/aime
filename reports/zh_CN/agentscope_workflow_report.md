# AgentScope 功能模块调研报告：工作流 (Workflow)

## 1. 模块定位
**“工作流 (Workflow) 是多智能体系统的指挥棒，负责编排智能体之间的协作模式。”**
如果说 `Agent` 是单一的员工，那么 `Workflow` 就是公司的组织架构和业务流程。它决定了员工是坐在一起开会（MsgHub），还是像流水线一样传递工作（Pipeline）。

## 2. 核心概念与术语拆解

### 2.1 MsgHub (消息中心)
*   **通俗解释**：一个会自动广播消息的“聊天室”。
*   **类比**：
    *   **没有 MsgHub**：Alice 说话，必须显式地告诉 Bob 和 Charlie。
    *   **有 MsgHub**：Alice 在群里说话，Bob 和 Charlie 自动就能听到。
*   **作用**：极大简化了多智能体之间的消息传递代码。

### 2.2 Pipeline (管道)
*   **通俗解释**：把多个智能体串联或并联起来的流水线。
*   **Sequential Pipeline (顺序管道)**：像接力赛。A 做完给 B，B 做完给 C。
*   **Fanout Pipeline (扇出管道)**：像发问卷。同一个问题同时发给 A、B、C，然后收集大家的所有回答。

---

## 3. 最小可运行示例 (Minimal Runnable Example)

这是一个使用 `SequentialPipeline` 将两个智能体串联的简单示例：用户 -> 翻译官 -> 润色师。

```python
# main.py
import agentscope
from agentscope.agent import ReActAgent
from agentscope.pipeline import SequentialPipeline
from agentscope.message import Msg
from agentscope.model import DashScopeChatModel

# 依赖安装： pip install agentscope

def main():
    agentscope.init(project="TranslationPipeline")
    
    # 配置模型 (需环境变量 DASHSCOPE_API_KEY)
    model = DashScopeChatModel(model_name="qwen-plus")

    # 1. 创建智能体
    translator = ReActAgent(
        name="Translator",
        sys_prompt="你是一个翻译官，将用户的中文直接翻译成英文，不要多说话。",
        model=model
    )
    
    polisher = ReActAgent(
        name="Polisher",
        sys_prompt="你是一个润色师，将输入的英文润色得更地道。",
        model=model
    )

    # 2. 创建顺序管道：Translator -> Polisher
    # 输入的消息会先给 Translator，其回复会作为 Polisher 的输入
    pipeline = SequentialPipeline([translator, polisher])

    # 3. 运行管道
    input_msg = Msg("User", "这个周末天气真不错，我想去公园放风筝。", "user")
    res = pipeline(input_msg)

    # 4. 打印最终结果 (Polisher 的回复)
    print(f"最终结果: {res.content}")

if __name__ == "__main__":
    main()
```

---

## 4. 典型应用场景

### 场景 1：多智能体群聊/辩论 (MsgHub)
让三个智能体（正方、反方、裁判）在一个群里自动辩论。

```python
from agentscope.pipeline import MsgHub
# ... 创建 agent_a (正方), agent_b (反方), judge (裁判) ...

async def debate():
    # 创建一个聊天室，把三个人拉进去
    async with MsgHub(participants=[agent_a, agent_b, judge]) as hub:
        # 1. 裁判发布辩题 (这条消息会自动广播给所有人)
        await judge(Msg("System", "辩题：AI 是否会取代人类？正方先发言。", "system"))
        
        # 2. 依次发言
        # 注意：在 MsgHub 中，agent_a 说的话，agent_b 和 judge 会自动存入记忆
        await agent_a() 
        await agent_b()
        await agent_a()
        await agent_b()
        
        # 3. 裁判总结
        await judge()
```

### 场景 2：并行投票/评审 (Fanout Pipeline)
让三个评审员同时对一篇文章打分，互不干扰。

```python
from agentscope.pipeline import FanoutPipeline
# ... 创建 reviewer_1, reviewer_2, reviewer_3 ...

# 创建扇出管道
# 默认 enable_gather=True 表示并行执行 (速度快)
vote_pipeline = FanoutPipeline([reviewer_1, reviewer_2, reviewer_3])

# 一条消息同时发给三个人
input_msg = Msg("User", "请对这篇文章打分：...", "user")
results = vote_pipeline(input_msg)

# results 是一个列表，包含三个人的回复
for i, res in enumerate(results):
    print(f"评审员 {i+1} 意见: {res.content}")
```

---

## 5. 扩展能力调研

### 5.1 自定义 Pipeline
如果官方的顺序/扇出管道不能满足需求（比如需要条件分支：如果 A 说 Yes 找 B，说 No 找 C），可以继承 `PipelineBase` 或直接写 Python 控制流。

```python
# 实际上，Pipeline 只是对 list[Agent] 的封装。
# 最灵活的方式是直接写 Python 代码逻辑：

async def custom_workflow(input_msg):
    # 1. 经理先看
    manager_res = await manager(input_msg)
    
    # 2. 根据经理意见分流
    if "同意" in manager_res.content:
        return await executor(manager_res)
    else:
        return await reviser(manager_res)
```

### 5.2 嵌套使用
Pipeline 本身也可以看作一个 Agent，因此可以嵌套。比如 `SequentialPipeline([agent_a, fanout_pipeline])`。

---

## 6. 常见坑与调试技巧

1.  **MsgHub 中有人“听不见”**：
    *   **现象**：Agent A 说完，Agent B 的回复完全不接茬。
    *   **解决**：确保 Agent B 在 `MsgHub(participants=[...])` 的列表中。不在列表里的 Agent 收不到广播。
2.  **顺序管道传递了错误的消息**：
    *   **现象**：第二个 Agent 收到的是 User 的消息，而不是第一个 Agent 的回复。
    *   **解决**：`SequentialPipeline` 自动将上一个输出作为下一个输入。检查第一个 Agent 是否正确返回了 `Msg` 对象。
3.  **并行执行报错**：
    *   **现象**：`FanoutPipeline` 报错 Event Loop 相关错误。
    *   **解决**：并行执行依赖异步 (`asyncio`)。确保你的 Agent 和 Tool 都是异步兼容的。如果遇到兼容性问题，尝试设置 `enable_gather=False` 改为串行执行。

## 7. 进一步阅读
*   **Pipeline 教程**: [Pipeline Tutorial](https://doc.agentscope.io/zh_CN/tutorial/task_pipeline.html)
*   **Conversation 教程**: [Conversation Tutorial](https://doc.agentscope.io/zh_CN/tutorial/workflow_conversation.html)
