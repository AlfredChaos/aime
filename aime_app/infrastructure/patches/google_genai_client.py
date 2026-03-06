def patch_google_genai_client_close() -> None:
    try:
        from google.genai._api_client import BaseApiClient
    except Exception:
        return

    if getattr(BaseApiClient.aclose, "_agentscope_research_patched", False):
        return

    original_close = BaseApiClient.close
    original_aclose = BaseApiClient.aclose

    def _safe_close(self) -> None:
        if not hasattr(self, "_http_options"):
            return
        try:
            return original_close(self)
        except AttributeError as e:
            if "_http_options" in str(e):
                return
            raise

    async def _safe_aclose(self) -> None:
        if not hasattr(self, "_http_options"):
            return
        try:
            return await original_aclose(self)
        except AttributeError as e:
            if "_http_options" in str(e):
                return
            raise

    _safe_close._agentscope_research_patched = True
    _safe_aclose._agentscope_research_patched = True
    BaseApiClient.close = _safe_close
    BaseApiClient.aclose = _safe_aclose

