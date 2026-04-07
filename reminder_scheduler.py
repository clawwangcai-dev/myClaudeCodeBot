from __future__ import annotations

import platform
import shutil
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from channel_keys import ConversationRef
from config import Settings
from reminder_store import ReminderRecord, ReminderStore


class ReminderSchedulerError(RuntimeError):
    pass


@dataclass(frozen=True)
class ScheduledReminder:
    record: ReminderRecord
    timer_path: Path | None
    service_path: Path | None


class ReminderScheduler:
    def __init__(self, settings: Settings, store: ReminderStore) -> None:
        self._settings = settings
        self._store = store
        self._repo_dir = Path(__file__).resolve().parent
        self._python_bin = Path(sys.executable).resolve()

    def schedule_telegram_reminder(
        self,
        *,
        conversation: ConversationRef,
        when: datetime,
        text: str,
    ) -> ScheduledReminder:
        self._ensure_supported()
        if conversation.channel != "telegram":
            raise ReminderSchedulerError("schedule_reminder currently supports Telegram chats only")
        clean = text.strip()
        if not clean:
            raise ReminderSchedulerError("Reminder text must not be empty")
        if when <= datetime.now().replace(second=0, microsecond=0):
            raise ReminderSchedulerError("Reminder time must be in the future")

        backend = self._backend_name()
        record = self._store.create(
            bot_name=self._settings.name,
            conversation=conversation,
            scheduled_for=when.replace(second=0, microsecond=0).isoformat(timespec="minutes"),
            text=clean,
            backend=backend,
        )
        if backend == "systemd":
            return self._schedule_systemd(record, when)
        if backend == "schtasks":
            return self._schedule_windows(record, when)
        raise ReminderSchedulerError(f"Unsupported reminder backend: {backend}")

    def get(self, reminder_id: str) -> ReminderRecord | None:
        return self._store.get(reminder_id)

    def cancel(self, reminder_id: str) -> ReminderRecord | None:
        record = self._store.get(reminder_id)
        if record is None:
            return None
        if record.status != "scheduled":
            raise ReminderSchedulerError(f"reminder {record.id} is already {record.status}")
        scheduler_ref = record.scheduler_ref or record.systemd_unit
        if record.backend == "systemd" and scheduler_ref:
            self._systemctl("--user", "disable", "--now", f"{scheduler_ref}.timer", check=False)
            service_path, timer_path = self._unit_paths(scheduler_ref)
            self._cleanup_unit_files(service_path, timer_path)
            self._systemctl("--user", "daemon-reload", check=False)
        elif record.backend == "schtasks" and scheduler_ref:
            self._schtasks("/Delete", "/TN", scheduler_ref, "/F", check=False)
        elif record.backend not in {"systemd", "schtasks"}:
            raise ReminderSchedulerError(f"Unsupported reminder backend: {record.backend}")
        return self._store.update(record.id, status="cancelled")

    def list_for_conversation(self, conversation: ConversationRef) -> list[ReminderRecord]:
        return self._store.items_for_conversation(conversation)

    def _ensure_supported(self) -> None:
        backend = self._backend_name()
        if backend == "systemd" and not shutil.which("systemctl"):
            raise ReminderSchedulerError("systemctl is not available on this machine")
        if backend == "schtasks" and not shutil.which("schtasks"):
            raise ReminderSchedulerError("schtasks is not available on this machine")

    def _backend_name(self) -> str:
        platform_name = self._platform_name()
        if platform_name == "Linux":
            return "systemd"
        if platform_name == "Windows":
            return "schtasks"
        raise ReminderSchedulerError(
            "schedule_reminder currently supports Linux systemd user timers and Windows Scheduled Tasks only"
        )

    def _platform_name(self) -> str:
        return platform.system()

    def _unit_name_for(self, reminder_id: str) -> str:
        return f"telegram-claude-bridge-reminder-{self._settings.name}-{reminder_id}"

    def _task_name_for(self, reminder_id: str) -> str:
        return self._unit_name_for(reminder_id)

    def _schedule_systemd(self, record: ReminderRecord, when: datetime) -> ScheduledReminder:
        unit_name = self._unit_name_for(record.id)
        record = self._store.update(record.id, scheduler_ref=unit_name, systemd_unit=unit_name) or record
        service_path, timer_path = self._write_unit_files(record, when)
        try:
            self._systemctl("--user", "daemon-reload")
            self._systemctl("--user", "enable", "--now", f"{unit_name}.timer")
        except ReminderSchedulerError as exc:
            self._cleanup_unit_files(service_path, timer_path)
            self._store.update(record.id, status="failed", last_error=str(exc))
            raise
        return ScheduledReminder(record=record, timer_path=timer_path, service_path=service_path)

    def _schedule_windows(self, record: ReminderRecord, when: datetime) -> ScheduledReminder:
        task_name = self._task_name_for(record.id)
        record = self._store.update(record.id, scheduler_ref=task_name) or record
        try:
            self._schtasks(
                "/Create",
                "/TN",
                task_name,
                "/SC",
                "ONCE",
                "/SD",
                when.strftime("%Y/%m/%d"),
                "/ST",
                when.strftime("%H:%M"),
                "/TR",
                self._windows_task_command(record.id),
                "/F",
            )
        except ReminderSchedulerError as exc:
            self._store.update(record.id, status="failed", last_error=str(exc))
            raise
        return ScheduledReminder(record=record, timer_path=None, service_path=None)

    def _unit_dir(self) -> Path:
        return Path.home() / ".config" / "systemd" / "user"

    def _unit_paths(self, unit_name: str) -> tuple[Path, Path]:
        unit_dir = self._unit_dir()
        return unit_dir / f"{unit_name}.service", unit_dir / f"{unit_name}.timer"

    def _write_unit_files(self, record: ReminderRecord, when: datetime) -> tuple[Path, Path]:
        service_path, timer_path = self._unit_paths(record.systemd_unit or self._unit_name_for(record.id))
        service_path.parent.mkdir(parents=True, exist_ok=True)
        service_body = textwrap.dedent(
            f"""\
            [Unit]
            Description=Telegram bridge reminder {record.id}

            [Service]
            Type=oneshot
            WorkingDirectory={self._repo_dir}
            ExecStart={self._python_bin} {self._repo_dir / "scheduled_message_worker.py"} --bot {self._settings.name} --store {self._store_path()} --reminder-id {record.id}
            """
        )
        timer_body = textwrap.dedent(
            f"""\
            [Unit]
            Description=Telegram bridge reminder timer {record.id}

            [Timer]
            Unit={(record.systemd_unit or self._unit_name_for(record.id))}.service
            OnCalendar={when.strftime("%Y-%m-%d %H:%M:00")}
            Persistent=true

            [Install]
            WantedBy=timers.target
            """
        )
        service_path.write_text(service_body, encoding="utf-8")
        timer_path.write_text(timer_body, encoding="utf-8")
        return service_path, timer_path

    def _cleanup_unit_files(self, service_path: Path, timer_path: Path) -> None:
        for path in (service_path, timer_path):
            try:
                path.unlink()
            except FileNotFoundError:
                continue

    def _systemctl(self, *args: str, check: bool = True) -> None:
        completed = subprocess.run(
            ["systemctl", *args],
            text=True,
            capture_output=True,
            check=False,
        )
        if check and completed.returncode != 0:
            raise ReminderSchedulerError(
                f"systemctl {' '.join(args)} failed with code {completed.returncode}\n"
                f"stdout:\n{completed.stdout.strip() or '<empty>'}\n"
                f"stderr:\n{completed.stderr.strip() or '<empty>'}"
            )

    def _schtasks(self, *args: str, check: bool = True) -> None:
        completed = subprocess.run(
            ["schtasks", *args],
            text=True,
            capture_output=True,
            check=False,
        )
        if check and completed.returncode != 0:
            raise ReminderSchedulerError(
                f"schtasks {' '.join(args)} failed with code {completed.returncode}\n"
                f"stdout:\n{completed.stdout.strip() or '<empty>'}\n"
                f"stderr:\n{completed.stderr.strip() or '<empty>'}"
            )

    def _windows_task_command(self, reminder_id: str) -> str:
        command = [
            str(self._python_bin),
            str(self._repo_dir / "scheduled_message_worker.py"),
            "--bot",
            self._settings.name,
            "--store",
            str(self._store_path()),
            "--reminder-id",
            reminder_id,
        ]
        return subprocess.list2cmdline(command)

    def _store_path(self) -> Path:
        return self._store.path
