from __future__ import annotations

from bridge_runner import BridgeRunner
from claude_runner import ClaudeRunner
from codex_runner import CodexRunner
from config import Settings


def build_runner(settings: Settings) -> BridgeRunner:
    if settings.provider == "codex":
        return CodexRunner(settings)
    return ClaudeRunner(settings)
