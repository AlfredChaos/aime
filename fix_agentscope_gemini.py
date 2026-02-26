import json
import base64
from datetime import datetime
from agentscope.model import GeminiChatModel
from agentscope.model._model_usage import ChatUsage
from agentscope.message import ToolUseBlock, TextBlock, ThinkingBlock
from agentscope._utils._common import _json_loads_with_repair
from agentscope.model._model_response import ChatResponse

async def _parse_gemini_stream_generation_response(
    self,
    start_datetime: datetime,
    response,
    structured_model = None,
):
    """
    Fixed version of _parse_gemini_stream_generation_response that handles None values in usage metadata.
    """
    text = ""
    thinking = ""
    tool_calls = []
    metadata = None
    
    async for chunk in response:
        if (
            chunk.candidates
            and chunk.candidates[0].content
            and chunk.candidates[0].content.parts
        ):
            for part in chunk.candidates[0].content.parts:
                if part.text:
                    if part.thought:
                        thinking += part.text
                    else:
                        text += part.text

                if part.function_call:
                    keyword_args = part.function_call.args or {}
                    
                    if part.thought_signature:
                        call_id = base64.b64encode(
                            part.thought_signature,
                        ).decode("utf-8")
                    else:
                        call_id = part.function_call.id

                    tool_calls.append(
                        ToolUseBlock(
                            type="tool_use",
                            id=call_id,
                            name=part.function_call.name,
                            input=keyword_args,
                            raw_input=json.dumps(
                                keyword_args,
                                ensure_ascii=False,
                            ),
                        ),
                    )

        # Text parts
        if text and structured_model:
            metadata = _json_loads_with_repair(text)

        usage = None
        if chunk.usage_metadata:
            # FIX: Handle None values in token counts by defaulting to 0
            input_tokens = chunk.usage_metadata.prompt_token_count or 0
            total_tokens = chunk.usage_metadata.total_token_count or 0
            # Ensure output_tokens is not negative
            output_tokens = max(0, total_tokens - input_tokens)
            
            usage = ChatUsage(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                time=(datetime.now() - start_datetime).total_seconds(),
            )

        # The content blocks for the current chunk
        content_blocks = []

        if thinking:
            content_blocks.append(
                ThinkingBlock(
                    type="thinking",
                    thinking=thinking,
                ),
            )

        if text:
            content_blocks.append(
                TextBlock(
                    type="text",
                    text=text,
                ),
            )

        yield ChatResponse(
            content=content_blocks + tool_calls,
            usage=usage,
            metadata=metadata,
        )

def apply_patch():
    """Apply the fix to GeminiChatModel."""
    GeminiChatModel._parse_gemini_stream_generation_response = _parse_gemini_stream_generation_response
