from __future__ import annotations

from typing import Any

from aime_app.application.ports import TeamOrchestrator
from aime_app.domain.team_spec import TeamSpec


class RunTeamChat:
    def __init__(self, *, orchestrator: TeamOrchestrator, team_spec: TeamSpec):
        self._orchestrator = orchestrator
        self._team_spec = team_spec

    async def run(self, *, msg: Any) -> Any:
        return await self._orchestrator.run(team_spec=self._team_spec, msg=msg)

