from __future__ import annotations

import json
import threading
import uuid
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path

from channel_keys import ConversationRef, parse_conversation_key


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass(frozen=True)
class ReminderRecord:
    id: str
    bot_name: str
    conversation_key: str
    channel: str
    chat_id: str
    scheduled_for: str
    text: str
    backend: str
    status: str
    created_at: str
    updated_at: str
    scheduler_ref: str | None = None
    systemd_unit: str | None = None
    sent_at: str | None = None
    last_error: str | None = None


class ReminderStore:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._data: dict[str, ReminderRecord] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        raw = json.loads(self._path.read_text(encoding="utf-8"))
        data: dict[str, ReminderRecord] = {}
        if isinstance(raw, dict):
            items = raw.values()
        else:
            items = raw
        for item in items:
            if not isinstance(item, dict):
                continue
            try:
                record = ReminderRecord(**item)
            except TypeError:
                continue
            data[record.id] = record
        self._data = data

    @property
    def path(self) -> Path:
        return self._path

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            reminder_id: asdict(record)
            for reminder_id, record in sorted(self._data.items(), key=lambda item: item[0])
        }
        self._path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def create(
        self,
        *,
        bot_name: str,
        conversation: ConversationRef,
        scheduled_for: str,
        text: str,
        backend: str,
        scheduler_ref: str | None = None,
        systemd_unit: str | None = None,
    ) -> ReminderRecord:
        reminder_id = uuid.uuid4().hex[:10]
        now = _utc_now_iso()
        record = ReminderRecord(
            id=reminder_id,
            bot_name=bot_name,
            conversation_key=conversation.key,
            channel=conversation.channel,
            chat_id=conversation.chat_id,
            scheduled_for=scheduled_for,
            text=text,
            backend=backend,
            status="scheduled",
            created_at=now,
            updated_at=now,
            scheduler_ref=scheduler_ref,
            systemd_unit=systemd_unit,
        )
        with self._lock:
            self._data[record.id] = record
            self._save()
        return record

    def get(self, reminder_id: str) -> ReminderRecord | None:
        with self._lock:
            return self._data.get(reminder_id)

    def update(self, reminder_id: str, **changes: object) -> ReminderRecord | None:
        with self._lock:
            current = self._data.get(reminder_id)
            if current is None:
                return None
            next_record = replace(current, updated_at=_utc_now_iso(), **changes)
            self._data[reminder_id] = next_record
            self._save()
            return next_record

    def remove(self, reminder_id: str) -> ReminderRecord | None:
        with self._lock:
            record = self._data.pop(reminder_id, None)
            if record is None:
                return None
            self._save()
            return record

    def items(self) -> list[ReminderRecord]:
        with self._lock:
            return sorted(self._data.values(), key=lambda item: (item.scheduled_for, item.id))

    def items_for_conversation(self, conversation: ConversationRef) -> list[ReminderRecord]:
        with self._lock:
            return sorted(
                (item for item in self._data.values() if item.conversation_key == conversation.key),
                key=lambda item: (item.scheduled_for, item.id),
            )

    @staticmethod
    def parse_conversation(value: str) -> ConversationRef:
        return parse_conversation_key(value)
