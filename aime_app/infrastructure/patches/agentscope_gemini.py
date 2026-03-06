from __future__ import annotations


def patch_agentscope_gemini_stream_usage() -> None:
    from datetime import datetime
    import json
    import base64 as _base64

    from agentscope.model import GeminiChatModel
    from agentscope.model._model_usage import ChatUsage
    from agentscope.message import ToolUseBlock, TextBlock, ThinkingBlock
    from agentscope._utils._common import _json_loads_with_repair
    from agentscope.model._model_response import ChatResponse

    if getattr(
        GeminiChatModel._parse_gemini_stream_generation_response,
        "_agentscope_research_patched",
        False,
    ):
        return

    async def _patched_parse_gemini_stream_generation_response(
        self,
        start_datetime: datetime,
        response,
        structured_model=None,
    ):
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
                            call_id = _base64.b64encode(
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

            if text and structured_model:
                metadata = _json_loads_with_repair(text)

            usage = None
            if chunk.usage_metadata:
                prompt_tokens = chunk.usage_metadata.prompt_token_count or 0
                total_tokens = chunk.usage_metadata.total_token_count or 0
                output_tokens = max(0, total_tokens - prompt_tokens)

                usage = ChatUsage(
                    input_tokens=prompt_tokens,
                    output_tokens=output_tokens,
                    time=(datetime.now() - start_datetime).total_seconds(),
                )

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

    _patched_parse_gemini_stream_generation_response._agentscope_research_patched = True
    GeminiChatModel._parse_gemini_stream_generation_response = (
        _patched_parse_gemini_stream_generation_response
    )


def patch_agentscope_gemini_embedding_batch_fallback() -> None:
    import os
    from datetime import datetime

    from agentscope.embedding import GeminiTextEmbedding
    from agentscope.embedding._embedding_response import EmbeddingResponse
    from agentscope.embedding._embedding_usage import EmbeddingUsage

    if getattr(GeminiTextEmbedding.__call__, "_agentscope_research_patched", False):
        return

    original_call = GeminiTextEmbedding.__call__

    async def _patched_call(self, text, **kwargs):
        gather_text = []
        for _ in text:
            if isinstance(_, dict) and "text" in _:
                gather_text.append(_["text"])
            elif isinstance(_, str):
                gather_text.append(_)
            else:
                raise ValueError(
                    "Input text must be a list of strings or TextBlock dicts.",
                )

        request_identifier = {
            "model": self.model_name,
            "contents": gather_text[0] if len(gather_text) == 1 else gather_text,
            "config": kwargs,
        }

        if self.embedding_cache:
            cached_embeddings = await self.embedding_cache.retrieve(
                identifier=request_identifier,
            )
            if cached_embeddings:
                return EmbeddingResponse(
                    embeddings=cached_embeddings,
                    usage=EmbeddingUsage(
                        tokens=0,
                        time=0,
                    ),
                    source="cache",
                )

        start_time = datetime.now()

        def _extract_embeddings(resp):
            return [_.values for _ in resp.embeddings]

        enable_batch = os.environ.get("GEMINI_ENABLE_BATCH_EMBED", "").lower() in (
            "1",
            "true",
            "yes",
        )

        if len(gather_text) == 1:
            response = self.client.models.embed_content(
                model=self.model_name,
                contents=gather_text[0],
                config=kwargs,
            )
            embeddings = _extract_embeddings(response)
        elif not enable_batch:
            embeddings = []
            for item in gather_text:
                resp = self.client.models.embed_content(
                    model=self.model_name,
                    contents=item,
                    config=kwargs,
                )
                item_embeddings = _extract_embeddings(resp)
                if not item_embeddings:
                    raise RuntimeError("Empty embedding response")
                embeddings.append(item_embeddings[0])
        else:
            try:
                response = self.client.models.embed_content(
                    model=self.model_name,
                    contents=gather_text,
                    config=kwargs,
                )
                embeddings = _extract_embeddings(response)
            except Exception as e:
                err_text = str(e)
                if (
                    "batchEmbedContents" in err_text
                    or "Unsupported action" in err_text
                    or "404" in err_text
                    or "NOT_FOUND" in err_text
                ):
                    embeddings = []
                    for item in gather_text:
                        resp = self.client.models.embed_content(
                            model=self.model_name,
                            contents=item,
                            config=kwargs,
                        )
                        item_embeddings = _extract_embeddings(resp)
                        if not item_embeddings:
                            raise RuntimeError("Empty embedding response")
                        embeddings.append(item_embeddings[0])
                else:
                    raise

        time = (datetime.now() - start_time).total_seconds()

        if self.embedding_cache:
            await self.embedding_cache.store(
                identifier=request_identifier,
                embeddings=embeddings,
            )

        return EmbeddingResponse(
            embeddings=embeddings,
            usage=EmbeddingUsage(
                time=time,
            ),
        )

    _patched_call._agentscope_research_patched = True
    GeminiTextEmbedding.__call__ = _patched_call
    GeminiTextEmbedding.__call__._agentscope_research_original = original_call

