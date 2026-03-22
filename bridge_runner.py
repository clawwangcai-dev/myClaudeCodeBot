from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Protocol


class RunnerError(RuntimeError):
    pass


@dataclass
class RunnerResponse:
    session_id: str
    text: str
    raw: dict
    command: list[str]


class BridgeRunner(Protocol):
    def ask_new(
        self,
        prompt: str,
        *,
        permission_mode_override: str | None = None,
        image_paths: list[str] | None = None,
    ) -> RunnerResponse: ...

    def ask_resume(
        self,
        session_id: str,
        prompt: str,
        *,
        permission_mode_override: str | None = None,
        image_paths: list[str] | None = None,
    ) -> RunnerResponse: ...

    def stream_new(
        self,
        prompt: str,
        *,
        permission_mode_override: str | None = None,
        image_paths: list[str] | None = None,
    ) -> Iterator[dict]: ...

    def stream_resume(
        self,
        session_id: str,
        prompt: str,
        *,
        permission_mode_override: str | None = None,
        image_paths: list[str] | None = None,
    ) -> Iterator[dict]: ...
