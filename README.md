# Telegram Claude CLI Bridge

Minimal bridge that forwards Telegram text messages to the local `claude` CLI and keeps one Claude session per Telegram chat.

## Environment

Set these variables before starting:

```bash
export TELEGRAM_BOT_TOKEN=...
export CLAUDE_BIN=claude
export CLAUDE_WORKDIR=/home/chao/projects/safe-repo
export CLAUDE_SETTINGS_FILE=/home/chao/.config/telegram-claude-bridge/claude-settings.json
export CLAUDE_PERMISSION_MODE=default
export CLAUDE_ALLOWED_TOOLS=
export CLAUDE_DISALLOWED_TOOLS=Bash(rm),Bash(git reset)
export CLAUDE_TIMEOUT_SECONDS=300
export CLAUDE_STREAMING=true
```

Optional:

```bash
export SESSION_STORE_PATH=sessions.json
export TELEGRAM_POLL_TIMEOUT=30
export TELEGRAM_EDIT_INTERVAL_SECONDS=1.0
export TELEGRAM_API_BASE=https://api.telegram.org
```

## Run

```bash
python3 bot.py
```

## Commands

- `/start`
- `/status`
- `/clear`

## Notes

- Each Telegram chat is serialized with a per-chat lock to avoid concurrent writes into the same Claude session.
- The default path uses `claude -p ... --output-format json` for both new and resumed conversations.
- Set `CLAUDE_STREAMING=true` to switch to `--output-format stream-json --include-partial-messages` and stream partial replies by editing the in-flight Telegram message.
- The bridge can load a service-specific Claude settings override with `CLAUDE_SETTINGS_FILE`; the bundled example disables `semgrep` plus the explanatory/learning output-style plugins only for this Telegram service.
- On this machine, the `systemd` unit also needs `node` on `PATH` because a Claude SessionEnd hook invokes Node.js.
- Keep `CLAUDE_WORKDIR` narrow and set tool permissions conservatively before exposing this bot to real users.

## systemd User Service

Install the provided user unit:

```bash
mkdir -p ~/.config/systemd/user ~/.config/telegram-claude-bridge
cp /home/chao/projects/claudeBot/systemd/telegram-claude-bridge.service ~/.config/systemd/user/
cp /home/chao/projects/claudeBot/systemd/telegram-claude-bridge.env.example ~/.config/telegram-claude-bridge/env
cp /home/chao/projects/claudeBot/systemd/telegram-claude-bridge.claude-settings.json ~/.config/telegram-claude-bridge/claude-settings.json
$EDITOR ~/.config/telegram-claude-bridge/env
systemctl --user daemon-reload
systemctl --user enable --now telegram-claude-bridge.service
journalctl --user -u telegram-claude-bridge.service -f
```

If you want it to survive reboots without an active login session:

```bash
loginctl enable-linger "$USER"
```
