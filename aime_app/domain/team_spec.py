from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TeamMemberSpec:
    member_id: str
    role: str


@dataclass(frozen=True)
class TeamSpec:
    team_id: str
    members: list[TeamMemberSpec]

