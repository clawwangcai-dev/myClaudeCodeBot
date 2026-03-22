from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class PendingApproval:
    chat_id: int
    session_id: str | None
    original_prompt: str
    permission_mode: str
    requested_at: str
    assistant_message: str


class ApprovalState:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._pending: dict[int, PendingApproval] = {}
        self._always: dict[int, str] = {}
        self._last_auto_request: dict[int, tuple[str, int]] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        always = raw.get("always") or {}
        self._always = {
            int(chat_id): str(mode)
            for chat_id, mode in always.items()
            if str(chat_id).lstrip("-").isdigit() and str(mode).strip()
        }

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "always": {str(chat_id): mode for chat_id, mode in sorted(self._always.items())},
        }
        self._path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def get(self, chat_id: int) -> PendingApproval | None:
        with self._lock:
            return self._pending.get(chat_id)

    def set(
        self,
        *,
        chat_id: int,
        session_id: str | None,
        original_prompt: str,
        permission_mode: str,
        assistant_message: str,
    ) -> PendingApproval:
        approval = PendingApproval(
            chat_id=chat_id,
            session_id=session_id,
            original_prompt=original_prompt,
            permission_mode=permission_mode,
            requested_at=_utc_now_iso(),
            assistant_message=assistant_message,
        )
        with self._lock:
            self._pending[chat_id] = approval
        return approval

    def pop(self, chat_id: int) -> PendingApproval | None:
        with self._lock:
            return self._pending.pop(chat_id, None)

    def clear(self, chat_id: int) -> bool:
        with self._lock:
            self._last_auto_request.pop(chat_id, None)
            return self._pending.pop(chat_id, None) is not None

    def count(self) -> int:
        with self._lock:
            return len(self._pending)

    def get_always_mode(self, chat_id: int) -> str | None:
        with self._lock:
            return self._always.get(chat_id)

    def set_always_mode(self, chat_id: int, permission_mode: str) -> None:
        with self._lock:
            self._always[chat_id] = permission_mode
            self._last_auto_request.pop(chat_id, None)
            self._save()

    def clear_always_mode(self, chat_id: int) -> bool:
        with self._lock:
            removed = self._always.pop(chat_id, None)
            self._last_auto_request.pop(chat_id, None)
            if removed is None:
                return False
            self._save()
            return True

    def always_count(self) -> int:
        with self._lock:
            return len(self._always)

    def record_auto_request(self, chat_id: int, fingerprint: str) -> int:
        with self._lock:
            last_fingerprint, last_count = self._last_auto_request.get(chat_id, ("", 0))
            if last_fingerprint == fingerprint:
                next_count = last_count + 1
            else:
                next_count = 1
            self._last_auto_request[chat_id] = (fingerprint, next_count)
            return next_count

    def reset_auto_request(self, chat_id: int) -> None:
        with self._lock:
            self._last_auto_request.pop(chat_id, None)
