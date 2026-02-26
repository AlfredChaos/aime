# AgentScope 功能模块调研报告：MCP (模型上下文协议)

## 1. 模块定位
**“MCP (Model Context Protocol) 是 AI 时代的 USB 接口标准。”**
它解决的核心问题是：**如何让 AI 智能体像插 U 盘一样，轻松连接外部数据（如数据库、本地文件）和工具（如高德地图、Slack）。**
在没有 MCP 之前，每个工具的接口都不一样，接入一个新工具就要写一套新代码。有了 MCP，只要对方支持 MCP 协议，智能体就能直接用。

## 2. 核心概念与术语拆解

### 2.1 MCP Client (客户端)
*   **通俗解释**：就是你的智能体（Agent）。它负责发起请求，去调用外部的能力。
*   **类比**：你的电脑主机。

### 2.2 MCP Server (服务端)
*   **通俗解释**：提供工具或数据的一方。
*   **类比**：U 盘、打印机、鼠标。只要插上（Connect），主机就能用。

### 2.3 有状态 (Stateful) vs 无状态 (Stateless)
*   **有状态**：像打电话。接通后一直保持通话，直到挂断。适合本地运行的工具（StdIO）。
*   **无状态**：像发短信。发一条，回一条，发完就没关系了。适合远程 HTTP 服务。

---

## 3. 最小可运行示例 (Minimal Runnable Example)

这个示例展示如何通过 HTTP 连接到一个公开的 MCP 服务（高德地图示例），并调用其中的工具。
**注意**：此示例依赖网络，且需要配置高德 API Key。

```python
# main.py
import os
import asyncio
from agentscope.mcp import HttpStatelessClient

# 依赖安装： pip install agentscope

async def main():
    # 1. 创建 MCP 客户端 (无状态 HTTP 模式)
    # 假设我们连接到高德地图的 MCP 服务 (URL 仅为示例，实际需部署或使用公开服务)
    # 这里为了演示，我们假设有一个本地或远程的 MCP 服务地址
    mcp_server_url = "https://mcp.amap.com/mcp" 
    # 实际使用时通常需要加 key: f"{mcp_server_url}?key={os.environ['GAODE_API_KEY']}"
    
    client = HttpStatelessClient(
        name="MapService",
        transport="streamable_http",
        url=mcp_server_url 
    )

    try:
        # 2. 从服务器获取工具函数 "maps_geo" (地理编码)
        # wrap_tool_result=True 会把结果包装成 AgentScope 的 ToolResponse 格式
        geo_tool = await client.get_callable_function(
            "maps_geo", 
            wrap_tool_result=True
        )

        print(f"成功获取工具: {geo_tool.name}")
        print(f"工具描述: {geo_tool.description}")

        # 3. 直接像调用普通 Python 函数一样调用它
        # 注意：这里会发起网络请求
        result = await geo_tool(address="天安门", city="北京")
        
        # 4. 打印结果
        print("调用结果:", result.content)
        
    except Exception as e:
        print(f"连接或调用失败 (可能是因为没有真实的 API Key 或网络问题): {e}")

if __name__ == "__main__":
    asyncio.run(main())
```

---

## 4. 典型应用场景

### 场景 1：让智能体拥有“眼睛” (连接本地文件系统)
通过 MCP 连接本地文件系统 Server，让智能体能读取你电脑上的文件。

```python
from agentscope.mcp import StdIOStatefulClient
from agentscope.agent import ReActAgent
# ... 其他 import ...

# 1. 启动本地 MCP Server (假设你安装了 @modelcontextprotocol/server-filesystem)
# 这会在后台启动一个子进程
client = StdIOStatefulClient(
    name="FileSystem",
    command="npx", 
    args=["-y", "@modelcontextprotocol/server-filesystem", "/home/user/documents"]
)

# 2. 连接 Server
await client.connect()

# 3. 把 MCP 的所有工具一次性注册给智能体
toolkit = Toolkit()
await toolkit.register_mcp_client(client)

# 4. 智能体现在可以使用 read_file, list_directory 等工具了
agent = ReActAgent(
    name="FileBot",
    sys_prompt="你可以帮我查阅本地文档。",
    toolkit=toolkit,
    # ...
)

# 5. 用完记得关闭
# await client.close()
```

### 场景 2：连接数据库 (PostgreSQL)
不需要自己写 SQL 连接器，直接用 MCP Server。

```python
# 假设有一个运行中的 PostgreSQL MCP Server
client = HttpStatelessClient(
    name="DB",
    url="http://localhost:8080/mcp"
)

# 获取执行 SQL 的工具
query_tool = await client.get_callable_function("query_sql")

# 智能体可以直接执行 SQL
agent = ReActAgent(toolkit=[query_tool], ...)
```

---

## 5. 扩展能力调研

### 5.1 开发自己的 MCP Server
如果你有私有数据想给智能体用，可以开发一个 MCP Server。AgentScope 主要是 Client 端，Server 端通常使用官方 SDK (TypeScript/Python) 开发。
一旦你的 Server 符合 MCP 标准，任何支持 MCP 的框架（AgentScope, Claude Desktop 等）都能直接连接。

### 5.2 混合使用
AgentScope 支持同时连接多个 MCP Server 和本地 Python 工具。
```python
toolkit = Toolkit()
# 注册 MCP 工具
await toolkit.register_mcp_client(map_client)
await toolkit.register_mcp_client(db_client)
# 注册本地 Python 函数
toolkit.register_tool_function(my_local_function)
```

---

## 6. 常见坑与调试技巧

1.  **连接方式混淆 (StdIO vs HTTP)**：
    *   **现象**：报错 `Connection refused` 或 `Process failed to start`。
    *   **解决**：
        *   **StdIO**: 用于本地运行的 CLI 程序（如 `npx ...`，`python server.py`）。客户端会自动启动子进程。
        *   **HTTP**: 用于远程服务（如 `http://...`）。客户端只负责发请求。
        *   千万别用 HTTP Client 去连一个本地 CLI 命令。
2.  **工具参数错误**：
    *   **现象**：调用工具时提示 `Missing required argument`。
    *   **解决**：使用 `print(tool.json_schema)` 查看工具的具体参数定义。MCP 工具的参数由 Server 端定义，Client 端无法修改。
3.  **生命周期管理**：
    *   **现象**：程序卡死不退出。
    *   **解决**：对于 `StatefulClient` (特别是 StdIO)，必须显式调用 `await client.close()` 来杀掉子进程。

## 7. 进一步阅读
*   **MCP 官方协议文档**: [https://modelcontextprotocol.io](https://modelcontextprotocol.io)
*   **AgentScope MCP 教程**: [MCP Tutorial](https://doc.agentscope.io/zh_CN/tutorial/task_mcp.html)
