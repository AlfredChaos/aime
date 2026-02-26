from agentscope.agent import ReActAgent, AgentBase
from agentscope.formatter import GeminiChatFormatter
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg
from agentscope.model import GeminiChatModel
import asyncio
import os
import fix_agentscope_gemini, fix_gemini_thinking_formatter
fix_agentscope_gemini.apply_patch()
fix_gemini_thinking_formatter.apply_patch()


from agentscope.tool import Toolkit, execute_python_code


async def creating_react_agent() -> None:
    """创建一个 ReAct 智能体并运行一个简单任务。"""
    # 准备工具
    toolkit = Toolkit()
    toolkit.register_tool_function(execute_python_code)

    aime = ReActAgent(
        name="Aime",
        sys_prompt="你是一个名为 Aime 的助手",
        model=GeminiChatModel(
            model_name="gemini-2.5-flash",
            api_key=os.environ["GEMINI_API_KEY"],
            stream=True,
            client_kwargs={
                "http_options": {
                    "base_url": "https://aicode.cat"
                }
            },
        ),
        formatter=GeminiChatFormatter(),
        toolkit=toolkit,
        memory=InMemoryMemory(),
    )

    msg = Msg(
        name="user",
        content="介绍一下你自己。如果让你自己设定自己的性格爱好，你会怎么做？",
        role="user",
    )

    await aime(msg)


asyncio.run(creating_react_agent())