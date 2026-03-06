from __future__ import annotations

from pathlib import Path

from aime_app.application.usecases.run_chat import RunChat
from aime_app.application.usecases.run_team_chat import RunTeamChat
from aime_app.domain.team_spec import TeamMemberSpec, TeamSpec
from aime_app.infrastructure.agentscope_adapter.react_agent_builder import ReActAgentBuilder
from aime_app.infrastructure.orchestration.sequential_team_orchestrator import (
    SequentialTeamOrchestrator,
)


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def create_run_chat() -> RunChat:
    return RunChat(agent_builder=ReActAgentBuilder(project_root=project_root()))


def create_run_team_chat() -> RunTeamChat:
    root = project_root()
    members = [
        ReActAgentBuilder(project_root=root),
        ReActAgentBuilder(project_root=root),
    ]
    team_spec = TeamSpec(
        team_id="default-team",
        members=[
            TeamMemberSpec(member_id="aime-1", role="assistant"),
            TeamMemberSpec(member_id="aime-2", role="assistant"),
        ],
    )
    orchestrator = SequentialTeamOrchestrator(members=members)
    return RunTeamChat(orchestrator=orchestrator, team_spec=team_spec)
