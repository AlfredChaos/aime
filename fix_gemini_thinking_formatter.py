from agentscope.formatter._gemini_formatter import GeminiChatFormatter, _format_gemini_media_block
from agentscope.message import Msg, TextBlock, ImageBlock, URLSource
from agentscope._logging import logger

async def _patched_format(self, msgs: list[Msg]) -> list[dict]:
    """Format message objects into Gemini API required format."""
    # self.assert_list_of_msgs(msgs) # Assume valid or skip assertion

    messages: list = []
    i = 0
    while i < len(msgs):
        msg = msgs[i]
        parts = []

        for block in msg.get_content_blocks():
            typ = block.get("type")
            if typ == "text":
                parts.append(
                    {
                        "text": block.get("text"),
                    },
                )

            elif typ == "tool_use":
                parts.append(
                    {
                        "function_call": {
                            "id": None,
                            "name": block["name"],
                            "args": block["input"],
                        },
                        "thought_signature": block.get("id", None),
                    },
                )

            elif typ == "tool_result":
                (
                    textual_output,
                    multimodal_data,
                ) = self.convert_tool_result_to_string(block["output"])

                # First add the tool result message in DashScope API format
                messages.append(
                    {
                        "role": "user",
                        "parts": [
                            {
                                "function_response": {
                                    "id": block["id"],
                                    "name": block["name"],
                                    "response": {
                                        "output": textual_output,
                                    },
                                },
                            },
                        ],
                    },
                )

                promoted_blocks = []
                for url, multimodal_block in multimodal_data:
                    if (
                        multimodal_block["type"] == "image"
                        and self.promote_tool_result_images
                    ):
                        promoted_blocks.extend(
                            [
                                TextBlock(
                                    type="text",
                                    text=f"\n- The image from '{url}': ",
                                ),
                                ImageBlock(
                                    type="image",
                                    source=URLSource(
                                        type="url",
                                        url=url,
                                    ),
                                ),
                            ],
                        )

                if promoted_blocks:
                    # Insert promoted blocks as new user message(s)
                    promoted_blocks = [
                        TextBlock(
                            type="text",
                            text="<system-info>The following are "
                            "the image contents from the tool "
                            f"result of '{block['name']}':",
                        ),
                        *promoted_blocks,
                        TextBlock(
                            type="text",
                            text="</system-info>",
                        ),
                    ]

                    msgs.insert(
                        i + 1,
                        Msg(
                            name="user",
                            content=promoted_blocks,
                            role="user",
                        ),
                    )

            elif typ == "thinking":
                # Handle thinking block
                parts.append(
                    {
                        "text": block.get("thinking"),
                        "thought": True,
                    },
                )

            elif typ in ["image", "audio", "video"]:
                parts.append(
                    _format_gemini_media_block(
                        block,  # type: ignore[arg-type]
                    ),
                )

            else:
                logger.warning(
                    "Unsupported block type: %s in the message, skipped. ",
                    typ,
                )

        role = "model" if msg.role == "assistant" else "user"

        if parts:
            messages.append(
                {
                    "role": role,
                    "parts": parts,
                },
            )

        # Move to next message (including inserted messages, which will
        # be processed in subsequent iterations)
        i += 1

    return messages

def apply_patch():
    """Apply the fix to GeminiChatFormatter."""
    GeminiChatFormatter._format = _patched_format
