from __future__ import annotations

import asyncio
import base64
import mimetypes
import warnings
from pathlib import Path

from agentscope.message import Base64Source, ImageBlock, Msg, TextBlock

from aime_app.infrastructure.wiring import create_run_chat


try:
    from langfuse import observe as _observe
except Exception:
    def _observe():
        def _wrap(fn):
            return fn
        return _wrap


@_observe()
async def main_async() -> None:
    warnings.filterwarnings(
        "ignore",
        category=DeprecationWarning,
        message=r"Inheritance class AiohttpClientSession from ClientSession is discouraged",
    )

    run_chat = create_run_chat()
    agent = await run_chat.create_agent()

    print("已启动交互模式：直接输入文本发送；发送图片：/img <path> [可选描述]；退出：/exit")
    while True:
        raw = await asyncio.to_thread(input, "You> ")
        if raw is None:
            continue

        user_input = raw.strip()
        if not user_input:
            continue

        if user_input.lower() in {"exit", "quit", "/exit", "/quit"}:
            break

        if user_input.startswith("/img "):
            parts = user_input.split(maxsplit=2)
            if len(parts) < 2:
                print("Error: missing image path")
                continue

            image_path = str(Path(parts[1]).expanduser())
            caption = parts[2] if len(parts) >= 3 else ""

            try:
                data = Path(image_path).read_bytes()
            except FileNotFoundError:
                print(f"Error: image file not found: {image_path}")
                continue
            except Exception as e:
                print(f"Error: failed to read image: {e}")
                continue

            mime, _ = mimetypes.guess_type(image_path)
            media_type = mime or "image/jpeg"
            b64 = base64.b64encode(data).decode("utf-8")

            blocks = []
            if caption:
                blocks.append(TextBlock(type="text", text=caption))
            blocks.append(
                ImageBlock(
                    type="image",
                    source=Base64Source(
                        type="base64",
                        media_type=media_type,
                        data=b64,
                    ),
                ),
            )

            msg = Msg(name="user", role="user", content=blocks)
        else:
            msg = Msg(name="user", role="user", content=user_input)

        try:
            warnings.simplefilter("ignore", DeprecationWarning)
            await agent(msg)
        except Exception as e:
            print(f"Error: {e}")


def main() -> None:
    asyncio.run(main_async())
