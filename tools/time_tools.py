from __future__ import annotations

from datetime import datetime, timezone

from agentscope.message import TextBlock
from agentscope.tool import ToolResponse


def get_current_utc_time() -> ToolResponse:
    """
    Get current UTC time in ISO-8601 format.
    """
    now = datetime.now(timezone.utc).isoformat()
    return ToolResponse(content=[TextBlock(text=now)])


TOOL_FUNCTIONS = [get_current_utc_time]

