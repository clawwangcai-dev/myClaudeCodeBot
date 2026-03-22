from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class CodexUsageSnapshot:
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int
    reasoning_output_tokens: int
    total_tokens: int
    limit_id: str | None
    plan_type: str | None
    primary_used_percent: float | None
    primary_window_minutes: int | None
    primary_resets_at: int | None
    secondary_used_percent: float | None
    secondary_window_minutes: int | None
    secondary_resets_at: int | None

    def to_dict(self) -> dict[str, int | float | str | None]:
        return asdict(self)


def load_codex_usage(session_id: str) -> CodexUsageSnapshot | None:
    if not session_id:
        return None

    session_file = _find_session_file(session_id)
    if session_file is None:
        return None

    latest_snapshot: CodexUsageSnapshot | None = None
    try:
        for raw_line in session_file.read_text(encoding="utf-8").splitlines():
            latest_snapshot = _parse_usage_line(raw_line) or latest_snapshot
    except OSError:
        return None

    return latest_snapshot


def _find_session_file(session_id: str) -> Path | None:
    sessions_root = Path.home() / ".codex" / "sessions"
    if not sessions_root.exists():
        return None

    matches = sorted(sessions_root.glob(f"**/rollout-*{session_id}.jsonl"))
    if not matches:
        return None
    return matches[-1]


def _parse_usage_line(raw_line: str) -> CodexUsageSnapshot | None:
    try:
        payload = json.loads(raw_line)
    except json.JSONDecodeError:
        return None

    if payload.get("type") != "event_msg":
        return None

    event_payload = payload.get("payload") or {}
    if event_payload.get("type") != "token_count":
        return None

    info = event_payload.get("info") or {}
    usage = info.get("total_token_usage") or {}
    rate_limits = event_payload.get("rate_limits") or {}
    primary = rate_limits.get("primary") or {}
    secondary = rate_limits.get("secondary") or {}

    return CodexUsageSnapshot(
        input_tokens=int(usage.get("input_tokens") or 0),
        cached_input_tokens=int(usage.get("cached_input_tokens") or 0),
        output_tokens=int(usage.get("output_tokens") or 0),
        reasoning_output_tokens=int(usage.get("reasoning_output_tokens") or 0),
        total_tokens=int(usage.get("total_tokens") or 0),
        limit_id=rate_limits.get("limit_id"),
        plan_type=rate_limits.get("plan_type"),
        primary_used_percent=_to_float(primary.get("used_percent")),
        primary_window_minutes=_to_int(primary.get("window_minutes")),
        primary_resets_at=_to_int(primary.get("resets_at")),
        secondary_used_percent=_to_float(secondary.get("used_percent")),
        secondary_window_minutes=_to_int(secondary.get("window_minutes")),
        secondary_resets_at=_to_int(secondary.get("resets_at")),
    )


def _to_int(value: object) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
