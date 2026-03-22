from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(',') if item.strip()]


@dataclass(frozen=True)
class Settings:
    provider: str
    telegram_bot_token: str
    claude_bin: str
    claude_workdir: Path
    claude_settings_file: Path | None
    claude_output_format: str
    claude_streaming: bool
    claude_permission_mode: str | None
    claude_approval_permission_mode: str
    claude_allowed_tools: list[str]
    claude_disallowed_tools: list[str]
    claude_timeout_seconds: int
    telegram_poll_timeout: int
    telegram_edit_interval_seconds: float
    telegram_api_base: str
    session_store_path: Path
    approval_store_path: Path
    media_store_path: Path
    whisper_bin: str
    whisper_model: str
    whisper_fallback_models: list[str]
    whisper_language: str | None
    whisper_threads: int
    codex_bin: str
    codex_model: str | None
    codex_sandbox: str
    codex_approval_policy: str
    status_web_enabled: bool
    status_web_host: str
    status_web_port: int
    status_web_token: str | None


def _parse_bool(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"Invalid boolean value: {value}")


def load_settings() -> Settings:
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '').strip()
    if not token:
        raise RuntimeError('Missing TELEGRAM_BOT_TOKEN')

    workdir = Path(os.environ.get('CLAUDE_WORKDIR', os.getcwd())).expanduser().resolve()
    settings_file_raw = os.environ.get('CLAUDE_SETTINGS_FILE', '').strip()
    settings_file = Path(settings_file_raw).expanduser().resolve() if settings_file_raw else None
    output_format = os.environ.get('CLAUDE_OUTPUT_FORMAT', 'json').strip() or 'json'

    if output_format != 'json':
        raise RuntimeError('CLAUDE_OUTPUT_FORMAT must be json for this bridge')

    base_dir = Path(__file__).resolve().parent
    store_path = Path(os.environ.get('SESSION_STORE_PATH', 'sessions.json')).expanduser()
    if not store_path.is_absolute():
        store_path = base_dir / store_path

    approval_store_path = Path(
        os.environ.get('APPROVAL_STORE_PATH', 'approval_prefs.json')
    ).expanduser()
    if not approval_store_path.is_absolute():
        approval_store_path = base_dir / approval_store_path

    media_store_path = Path(
        os.environ.get('MEDIA_STORE_PATH', str(workdir / '.telegram-media'))
    ).expanduser()
    if not media_store_path.is_absolute():
        media_store_path = base_dir / media_store_path

    poll_timeout_raw = os.environ.get('TELEGRAM_POLL_TIMEOUT', '30').strip() or '30'
    claude_timeout_raw = os.environ.get('CLAUDE_TIMEOUT_SECONDS', '300').strip() or '300'
    edit_interval_raw = os.environ.get('TELEGRAM_EDIT_INTERVAL_SECONDS', '1.0').strip() or '1.0'
    status_web_port_raw = os.environ.get('STATUS_WEB_PORT', '8765').strip() or '8765'

    return Settings(
        provider=os.environ.get('BRIDGE_PROVIDER', 'claude').strip().lower() or 'claude',
        telegram_bot_token=token,
        claude_bin=os.environ.get('CLAUDE_BIN', 'claude').strip() or 'claude',
        claude_workdir=workdir,
        claude_settings_file=settings_file,
        claude_output_format=output_format,
        claude_streaming=_parse_bool(os.environ.get('CLAUDE_STREAMING'), default=False),
        claude_permission_mode=os.environ.get('CLAUDE_PERMISSION_MODE', '').strip() or None,
        claude_approval_permission_mode=(
            os.environ.get('CLAUDE_APPROVAL_PERMISSION_MODE', 'acceptEdits').strip()
            or 'acceptEdits'
        ),
        claude_allowed_tools=_parse_csv(os.environ.get('CLAUDE_ALLOWED_TOOLS')),
        claude_disallowed_tools=_parse_csv(os.environ.get('CLAUDE_DISALLOWED_TOOLS')),
        claude_timeout_seconds=max(1, int(claude_timeout_raw)),
        telegram_poll_timeout=max(1, int(poll_timeout_raw)),
        telegram_edit_interval_seconds=max(0.2, float(edit_interval_raw)),
        telegram_api_base=os.environ.get('TELEGRAM_API_BASE', 'https://api.telegram.org').rstrip('/'),
        session_store_path=store_path,
        approval_store_path=approval_store_path,
        media_store_path=media_store_path,
        whisper_bin=os.environ.get('WHISPER_BIN', 'whisper').strip() or 'whisper',
        whisper_model=os.environ.get('WHISPER_MODEL', 'base').strip() or 'base',
        whisper_fallback_models=_parse_csv(
            os.environ.get('WHISPER_FALLBACK_MODELS', 'tiny')
        ),
        whisper_language=os.environ.get('WHISPER_LANGUAGE', '').strip() or None,
        whisper_threads=max(1, int(os.environ.get('WHISPER_THREADS', '2').strip() or '2')),
        codex_bin=os.environ.get('CODEX_BIN', 'codex').strip() or 'codex',
        codex_model=os.environ.get('CODEX_MODEL', '').strip() or None,
        codex_sandbox=os.environ.get('CODEX_SANDBOX', 'workspace-write').strip() or 'workspace-write',
        codex_approval_policy=(
            os.environ.get('CODEX_APPROVAL_POLICY', 'on-request').strip() or 'on-request'
        ),
        status_web_enabled=_parse_bool(os.environ.get('STATUS_WEB_ENABLED'), default=True),
        status_web_host=os.environ.get('STATUS_WEB_HOST', '127.0.0.1').strip() or '127.0.0.1',
        status_web_port=max(1, int(status_web_port_raw)),
        status_web_token=os.environ.get('STATUS_WEB_TOKEN', '').strip() or None,
    )
