from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from reminder_store import ReminderStore
from resume_telegram_session import _load_runtime_settings


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send a scheduled Telegram reminder for the bridge.")
    parser.add_argument("--bot", required=True, help="Bridge bot name")
    parser.add_argument("--store", required=True, help="Path to scheduled_reminders.json")
    parser.add_argument("--reminder-id", required=True, help="Reminder identifier")
    return parser.parse_args()


def _send_telegram_message(*, api_base: str, bot_token: str, chat_id: str, text: str) -> None:
    payload = urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
    request = Request(f"{api_base}/bot{bot_token}/sendMessage", data=payload, method="POST")
    try:
        with urlopen(request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Telegram HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Telegram request failed: {exc}") from exc
    if not data.get("ok"):
        raise RuntimeError(f"Telegram API returned error: {data}")


def _cleanup_systemd_units(unit_name: str | None) -> None:
    if not unit_name or not shutil.which("systemctl"):
        return
    subprocess.run(
        ["systemctl", "--user", "disable", "--now", f"{unit_name}.timer"],
        text=True,
        capture_output=True,
        check=False,
    )
    unit_dir = Path.home() / ".config" / "systemd" / "user"
    for suffix in (".service", ".timer"):
        try:
            (unit_dir / f"{unit_name}{suffix}").unlink()
        except FileNotFoundError:
            continue
    subprocess.run(
        ["systemctl", "--user", "daemon-reload"],
        text=True,
        capture_output=True,
        check=False,
    )


def _cleanup_windows_task(task_name: str | None) -> None:
    if not task_name or not shutil.which("schtasks"):
        return
    subprocess.run(
        ["schtasks", "/Delete", "/TN", task_name, "/F"],
        text=True,
        capture_output=True,
        check=False,
    )


def main() -> int:
    args = _parse_args()
    store = ReminderStore(Path(args.store).expanduser().resolve())
    record = store.get(args.reminder_id)
    if record is None:
        print(f"error: reminder not found: {args.reminder_id}", file=sys.stderr)
        return 1
    if record.channel != "telegram":
        store.update(record.id, status="failed", last_error=f"unsupported channel: {record.channel}")
        print(f"error: unsupported channel: {record.channel}", file=sys.stderr)
        return 1

    settings = next((item for item in _load_runtime_settings() if item.name == args.bot), None)
    if settings is None:
        store.update(record.id, status="failed", last_error=f"unknown bot: {args.bot}")
        print(f"error: unknown bot: {args.bot}", file=sys.stderr)
        return 1

    try:
        _send_telegram_message(
            api_base=settings.telegram_api_base,
            bot_token=settings.telegram_bot_token,
            chat_id=record.chat_id,
            text=record.text,
        )
    except RuntimeError as exc:
        store.update(record.id, status="failed", last_error=str(exc))
        print(f"error: {exc}", file=sys.stderr)
        return 1

    store.update(
        record.id,
        status="sent",
        sent_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        last_error=None,
    )
    scheduler_ref = record.scheduler_ref or record.systemd_unit
    if record.backend == "systemd":
        _cleanup_systemd_units(scheduler_ref)
    elif record.backend == "schtasks":
        _cleanup_windows_task(scheduler_ref)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
