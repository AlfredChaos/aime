from __future__ import annotations

from aime_app.application.ports import AgentBuilder, ChatAgent


class RunChat:
    def __init__(self, agent_builder: AgentBuilder):
        self._agent_builder = agent_builder


    async def create_agent(self) -> ChatAgent:
        return await self._agent_builder.build()
