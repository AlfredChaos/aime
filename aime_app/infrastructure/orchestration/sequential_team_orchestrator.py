from __future__ import annotations

from typing import Any

from aime_app.application.ports import AgentBuilder, ChatAgent, TeamOrchestrator
from aime_app.domain.team_spec import TeamSpec


class SequentialTeamOrchestrator(TeamOrchestrator):
    def __init__(self, *, members: list[AgentBuilder]):
        self._members = members
        self._agents: list[ChatAgent] | None = None

    async def _ensure_agents(self) -> list[ChatAgent]:
        if self._agents is not None:
            return self._agents
        self._agents = [await b.build() for b in self._members]
        return self._agents

    async def run(self, *, team_spec: TeamSpec, msg: Any) -> Any:
        agents = await self._ensure_agents()
        current = msg
        for agent in agents:
            result = await agent(current)
            if result is not None:
                current = result
        return current

