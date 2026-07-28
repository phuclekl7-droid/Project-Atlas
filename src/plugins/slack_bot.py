"""
Slack App Integration (Feature #86).
Connects Project Atlas to Slack for team communication.

Uses the Slack Web API via REST (no slack-sdk dependency required).

Supports:
- Send messages to channels
- List channels
- Read channel history
- Bot info

Usage:
    SlackPlugin.execute("channels")
    SlackPlugin.execute("send #general Hello from Atlas!")
    SlackPlugin.execute("read C12345")

Requirements:
- SLACK_BOT_TOKEN env var (from Slack API: OAuth & Permissions)
- Bot token with scopes: chat:write, channels:read, channels:history
"""

import json
import os
from typing import Optional

from src.core import setup_logger
from src.plugin import BasePlugin, PluginResult

logger = setup_logger("slack")

try:
    import requests as req_lib
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

SLACK_API_BASE = "https://slack.com/api"


def _get_token() -> Optional[str]:
    """Get Slack bot token from environment."""
    return os.environ.get("SLACK_BOT_TOKEN")


def _api_call(method: str, data: Optional[dict] = None) -> Optional[dict]:
    """Make a Slack Web API call."""
    token = _get_token()
    if not token or not _HAS_REQUESTS:
        return None
    try:
        url = f"{SLACK_API_BASE}/{method}"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        resp = req_lib.post(url, headers=headers, json=data, timeout=10) if data \
            else req_lib.get(url, headers=headers, timeout=10)
        result = resp.json()
        if result.get("ok"):
            return result
        logger.warning(f"Slack API error ({method}): {result.get('error', 'unknown')}")
        return None
    except Exception as e:
        logger.warning(f"Slack API call failed: {e}")
        return None


class SlackPlugin(BasePlugin):
    """
    Integrates Project Atlas with Slack workspaces.

    Commands:
    - "me" / "info": Bot info
    - "channels": List public channels
    - "send <channel> <message>": Send a message
    - "read <channel> [limit]": Read recent messages
    - "help": Show help

    Setup:
    1. Go to https://api.slack.com/apps
    2. Create a new app → Bot Tokens → Add OAuth Scopes
    3. Required scopes: chat:write, channels:read, channels:history
    4. Install to workspace → Copy Bot User OAuth Token
    5. Set SLACK_BOT_TOKEN env var

    Examples:
        "me"
        "channels"
        "send #general Hello from Project Atlas!"
        "read C0123ABCDEF 5"
    """

    name = "slack"
    description = "Kết nối Project Atlas với Slack"

    def execute(self, input_str: str) -> PluginResult:
        """Execute a Slack command."""
        text = input_str.strip()
        if not text:
            return self._show_help()

        token = _get_token()
        if not token:
            return PluginResult(
                success=False,
                error=(
                    "❌ **Chưa cấu hình Slack Bot Token.**\\n\\n"
                    "1. Truy cập https://api.slack.com/apps\\n"
                    "2. Tạo app → Bot Tokens\\n"
                    "3. Scopes: chat:write, channels:read, channels:history\\n"
                    "4. Set: `SLACK_BOT_TOKEN=xoxb-...`"
                )
            )

        cmd = text.lower()

        if cmd in ("me", "info"):
            return self._cmd_me()
        elif cmd in ("channels", "channels list"):
            return self._cmd_channels()
        elif cmd.startswith("send "):
            return self._cmd_send(text[5:].strip())
        elif cmd.startswith("read "):
            return self._cmd_read(text[5:].strip())
        elif cmd in ("help", ""):
            return self._show_help()
        else:
            return PluginResult(
                success=False,
                error=f"Lệnh không hợp lệ: `{text}`\\n\\nLệnh: me, channels, send, read, help"
            )

    def _show_help(self) -> PluginResult:
        return PluginResult(
            success=True,
            output=(
                "## 💬 Slack Bot Commands\\n\\n"
                "| Command | Description |\\n"
                "|:--------|:------------|\\n"
                "| `me` | Bot info |\\n"
                "| `channels` | List public channels |\\n"
                "| `send <ch> <msg>` | Send message |\\n"
                "| `read <ch> [limit]` | Read messages |\\n"
                "| `help` | Show this help |\\n\\n"
                "**Setup:** `SLACK_BOT_TOKEN` env var required."
            )
        )

    def _cmd_me(self) -> PluginResult:
        auth_test = _api_call("auth.test")
        if auth_test:
            bot_info = auth_test
            return PluginResult(
                success=True,
                output=(
                    f"## 💬 Slack Bot Info\\n\\n"
                    f"- **Bot Name:** {bot_info.get('user', 'N/A')}\\n"
                    f"- **Workspace:** {bot_info.get('team', 'N/A')}\\n"
                    f"- **Bot ID:** {bot_info.get('user_id', 'N/A')}"
                )
            )
        return PluginResult(
            success=False,
            error="❌ Cannot connect to Slack API. Check your token."
        )

    def _cmd_channels(self) -> PluginResult:
        result = _api_call("conversations.list", {
            "types": "public_channel",
            "limit": 20,
            "exclude_archived": True,
        })
        if result and result.get("channels"):
            lines = ["## 📡 Slack Channels", ""]
            for ch in result["channels"]:
                name = ch.get("name", "unknown")
                cid = ch.get("id", "")
                members = ch.get("num_members", "?")
                topic = ch.get("topic", {}).get("value", "")
                lines.append(f"- **#{name}** (`{cid}`) — {members} members")
                if topic:
                    lines.append(f"  {topic[:100]}")
                lines.append("")
            return PluginResult(success=True, output="\n".join(lines))
        return PluginResult(
            success=False,
            error="❌ Cannot list channels. Check bot permissions (channels:read)."
        )

    def _cmd_send(self, body: str) -> PluginResult:
        parts = body.split(maxsplit=1)
        if len(parts) < 2:
            return PluginResult(
                success=False,
                error="Thiếu nội dung.\\n\\nĐịnh dạng: `send <#channel> <message>`"
            )

        channel = parts[0].strip().lstrip("#")
        message = parts[1].strip()

        result = _api_call("chat.postMessage", {
            "channel": channel,
            "text": message,
            "mrkdwn": True,
        })

        if result:
            return PluginResult(
                success=True,
                output=f"✅ **Message sent** to `#{channel}`\\n\\n> {message[:300]}"
            )
        return PluginResult(
            success=False,
            error=f"❌ Cannot send to `#{channel}`. Check channel ID and bot permissions."
        )

    def _cmd_read(self, body: str) -> PluginResult:
        parts = body.split()
        if not parts:
            return PluginResult(
                success=False,
                error="Thiếu channel.\\n\\nĐịnh dạng: `read <channel> [limit]`"
            )

        channel = parts[0]
        limit = min(int(parts[1]) if len(parts) > 1 else 10, 50)

        result = _api_call("conversations.history", {
            "channel": channel,
            "limit": limit,
        })

        if result and result.get("messages"):
            lines = [f"## 📨 Recent Messages (last {len(result['messages'])})", ""]
            for msg in reversed(result["messages"]):
                user = msg.get("user", "unknown")
                text = msg.get("text", "")[:200]
                ts = msg.get("ts", "")
                lines.append(f"**<@{user}>** ({ts}): {text}")
            return PluginResult(success=True, output="\n".join(lines))
        return PluginResult(
            success=False,
            error="❌ Cannot read messages. Check channel ID and bot permissions."
        )
