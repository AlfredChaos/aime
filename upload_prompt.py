
from langfuse import Langfuse
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def upload_prompt():
    langfuse = Langfuse()
    
    prompt_name = "aime-system-prompt"
    prompt_content = """你是一个名为 Aime 的智能助手。
你的目标是高效且准确地协助用户完成任务。
你可以使用各种工具，并应在必要时使用它们。
请始终以礼貌和专业的态度回答。
如果你对某事不确定，请承认并寻求澄清。
"""
    
    print(f"Creating prompt '{prompt_name}'...")
    try:
        langfuse.create_prompt(
            name=prompt_name,
            prompt=prompt_content,
            type="text",
            labels=["production", "aime"]
        )
        print("Prompt created successfully.")
    except Exception as e:
        print(f"Error creating prompt: {e}")

if __name__ == "__main__":
    upload_prompt()
