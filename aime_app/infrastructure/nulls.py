from __future__ import annotations

from typing import Any, Awaitable, Callable

from aime_app.application.ports import Gateway, Scheduler


class NoopGateway(Gateway):
    def emit(self, event: Any) -> None:
        return

    def on_event(self, handler: Callable[[Any], Awaitable[None]]) -> None:
        return


class NoopScheduler(Scheduler):
    def schedule(self, *, job_spec: Any, handler: Callable[[], Awaitable[None]]) -> str:
        raise NotImplementedError("Scheduler is not configured")

    def cancel(self, job_id: str) -> None:
        return
