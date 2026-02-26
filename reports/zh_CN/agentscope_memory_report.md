# AgentScope 功能模块调研报告：Memory（记忆）

## 1. 模块定位
**“记忆 (Memory) 是智能体的大脑海马体，负责存储、检索和管理对话历史与知识。”**
如果没有记忆，智能体就像金鱼，说完一句话转头就忘。AgentScope 的记忆模块不仅能记住“刚才说了什么”（短期记忆），还能记住“用户喜欢什么”（长期记忆）。

## 2. 核心概念与术语拆解

### 2.1 记忆 (Memory) vs 消息 (Msg)
*   **消息 (Msg)**：对话的最小单位，包含 `role`（谁说的）、`content`（说了什么）。
*   **记忆 (Memory)**：消息的容器。
*   **类比**：
    *   **Msg**：一张便利贴。
    *   **Memory**：一本贴满便利贴的笔记本。

### 2.2 标记 (Marks)
*   **通俗解释**：给特定的消息打上标签，方便以后快速找到。
*   **类比**：在笔记本的重要页面贴上红色的“紧急”标签，或者蓝色的“待办”标签。查阅时，只看红标签就能快速找到重点。

### 2.3 长期记忆 (Long-term Memory)与向量库
*   **通俗解释**：当笔记本写满了（短期记忆溢出），我们需要把重要的知识存进图书馆（长期记忆）。为了能快速找到书，我们需要一个索引系统（向量库）。
*   **Embedding (嵌入)**：把文字变成数字坐标。意思相近的话，坐标离得近。
*   **类比**：
    *   **普通搜索**：必须字完全一样才能搜到（如搜“苹果”找不到“iPhone”）。
    *   **Embedding 搜索**：搜“水果”，能找到“苹果”、“香蕉”，因为它们意思相近。

---

## 3. 最小可运行示例 (Minimal Runnable Example)

这是一个使用内存（RAM）存储对话历史的简单示例。重启程序后记忆会丢失。

```python
# main.py
import asyncio
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg

# 依赖安装： pip install agentscope

async def main():
    # 1. 创建一个内存记忆对象
    memory = InMemoryMemory()

    # 2. 模拟对话：添加用户消息
    # Msg 参数：name(发送者), content(内容), role(角色: user/assistant/system)
    await memory.add(Msg("User", "我叫张三，我是程序员。", "user"))
    
    # 3. 添加带有“标记”的消息 (比如系统提示)
    await memory.add(
        Msg("System", "请记住用户的职业。", "system"), 
        marks="important" # 打上 'important' 标签
    )

    # 4. 获取所有记忆
    all_msgs = await memory.get_memory()
    print(f"当前总共有 {len(all_msgs)} 条记忆。")

    # 5. 只获取带 'important' 标签的记忆
    important_msgs = await memory.get_memory(mark="important")
    print(f"重要记忆内容: {important_msgs[0].content}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 4. 典型应用场景

### 场景 1：持久化记忆 (存入数据库)
内存记忆一断电就没了，企业级应用需要存入数据库。AgentScope 支持 SQL 和 Redis。

```python
# 需要安装：pip install sqlalchemy aiosqlite
from agentscope.memory import AsyncSQLAlchemyMemory
from sqlalchemy.ext.asyncio import create_async_engine

# 1. 创建数据库引擎 (这里用本地 SQLite 文件 memory.db)
engine = create_async_engine("sqlite+aiosqlite:///./memory.db")

# 2. 初始化持久化记忆
# user_id 和 session_id 用于区分不同用户和会话
memory = AsyncSQLAlchemyMemory(
    engine_or_session=engine, 
    user_id="user_001", 
    session_id="session_abc"
)

# 像普通记忆一样使用，数据会自动存入 memory.db
# await memory.add(...) 
```

### 场景 2：RAG (检索增强生成) - 长期记忆
当用户问“我上次提到的那个项目叫什么”时，智能体需要在海量历史中检索。这里使用 `Mem0` (一个流行的记忆库) 作为后端。

```python
# 需要安装：pip install mem0ai
from agentscope.memory import Mem0LongTermMemory
# ... 配置 embedding 模型 (参考 Agent 报告中的 model 配置) ...

long_term_mem = Mem0LongTermMemory(
    agent_name="Assistant",
    user_name="user_001",
    # 需要传入 embedding_model 用于计算文本相似度
    # embedding_model=... 
)

# 1. 存入知识
await long_term_mem.record([
    Msg("User", "我正在做一个叫 'SkyNet' 的 AI 项目。", "user")
])

# 2. 检索知识 (搜索与 "项目名称" 相关的记忆)
retrieved = await long_term_mem.retrieve(
    [Msg("User", "我的项目叫什么名字？", "user")]
)
# 智能体将获得包含 'SkyNet' 的上下文
```

---

## 5. 扩展能力调研

### 5.1 自定义记忆后端
如果你想把记忆存到飞书文档、Notion 或者自研的数据库，可以继承 `MemoryBase`。

```python
from agentscope.memory import MemoryBase

class NotionMemory(MemoryBase):
    def __init__(self, notion_api_key):
        self.api_key = notion_api_key
        
    async def add(self, memories, **kwargs):
        # 实现调用 Notion API 写入数据的逻辑
        print("正在写入 Notion...")
        
    async def get_memory(self, **kwargs):
        # 实现从 Notion 读取数据的逻辑
        return []
        
    # ... 其他必须实现的方法 (delete, clear 等)
```

### 5.2 记忆压缩 (与 ReActAgent 结合)
当记忆太长超过模型限制时，AgentScope 支持自动压缩。这是 `ReActAgent` 的功能，但作用于 Memory。

```python
from agentscope.agent import ReActAgent

agent = ReActAgent(
    # ... 其他配置 ...
    compression_config={
        "enable": True,
        "trigger_threshold": 2000, # 当 Token 超过 2000 时触发
        "keep_recent": 5, # 保留最近 5 条原始消息，其他的压缩成摘要
    }
)
```

---

## 6. 常见坑与调试技巧

1.  **数据库连接未关闭**：
    *   **现象**：程序报错 `RuntimeError: Event loop is closed` 或数据库锁死。
    *   **解决**：使用 `AsyncSQLAlchemyMemory` 时，务必在程序结束前调用 `await memory.close()`，或使用 `async with` 上下文管理器。
2.  **长期记忆检索不到**：
    *   **现象**：明明存了，但检索结果为空。
    *   **解决**：检查 Embedding 模型是否配置正确。中文内容建议使用支持中文的 Embedding 模型（如 `text-embedding-v3` 或 DashScope 的 embedding 服务）。
3.  **标记 (Marks) 混淆**：
    *   **现象**：`get_memory(mark="hint")` 返回空。
    *   **解决**：`add` 的时候必须显式传入 `marks="hint"`。注意 `marks` 是字符串或字符串列表。

## 7. 进一步阅读
*   **官方文档**: [Memory Tutorial](https://doc.agentscope.io/zh_CN/tutorial/task_memory.html)
*   **Mem0 项目**: [https://github.com/mem0ai/mem0](https://github.com/mem0ai/mem0)
