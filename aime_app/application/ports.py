from __future__ import annotations

from typing import Any, Awaitable, Callable, Protocol, runtime_checkable


@runtime_checkable
class ChatAgent(Protocol):
    async def __call__(self, msg: Any) -> Any: ...


class AgentBuilder(Protocol):
    async def build(self) -> ChatAgent: ...


class TeamOrchestrator(Protocol):
    async def run(self, *, team_spec: Any, msg: Any) -> Any: ...


class Scheduler(Protocol):
    def schedule(self, *, job_spec: Any, handler: Callable[[], Awaitable[None]]) -> str: ...
    def cancel(self, job_id: str) -> None: ...


class Gateway(Protocol):
    def emit(self, event: Any) -> None: ...
    def on_event(self, handler: Callable[[Any], Awaitable[None]]) -> None: ...

