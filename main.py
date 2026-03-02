
from agentscope.agent import ReActAgent
from agentscope.formatter import GeminiChatFormatter
from agentscope.memory import InMemoryMemory
from agentscope.message import Msg
from agentscope.model import GeminiChatModel
import asyncio
import os
import fix_agentscope_gemini, fix_gemini_thinking_formatter
from langfuse import Langfuse, observe
from agentscope.tool import Toolkit, execute_python_code
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Apply patches
fix_agentscope_gemini.apply_patch()
fix_gemini_thinking_formatter.apply_patch()

# Initialize Langfuse client
langfuse = Langfuse()

@observe()
async def creating_react_agent() -> None:
    """创建一个 ReAct 智能体并运行一个简单任务。"""
    # Get Prompt from Langfuse
    print("Fetching prompt from Langfuse...")
    try:
        prompt = langfuse.get_prompt("aime-system-prompt")
        sys_prompt_content = prompt.compile()
        print(f"Loaded prompt: {sys_prompt_content}")
    except Exception as e:
        print(f"Error loading prompt from Langfuse: {e}")
        sys_prompt_content = "你是一个名为 Aime 的助手"

    # Prepare tools
    toolkit = Toolkit()
    toolkit.register_tool_function(execute_python_code)

    aime = ReActAgent(
        name="Aime",
        sys_prompt=sys_prompt_content,
        model=GeminiChatModel(
            model_name="gemini-2.5-flash",
            api_key=os.environ.get("GEMINI_API_KEY"),
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


if __name__ == "__main__":
    asyncio.run(creating_react_agent())
