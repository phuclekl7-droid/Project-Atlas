"""
Discord Bot Integration (Feature #84).
Connects Project Atlas to Discord for chatting via Discord servers.

Uses the Discord REST API via requests (no discord.py dependency).

Supports:
- HTTP-based message reading and sending via Discord API
- Token-based authentication
- Channel message history reading
- Send messages to channels

Usage:
    DiscordPlugin.execute("channels")  # List available channels
    DiscordPlugin.execute("send #general Hello!")  # Send message
    DiscordPlugin.execute("read")  # Read recent messages

Requirements:
- DISCORD_BOT_TOKEN env var set (from Discord Developer Portal)
"""

import json
import os
import time
from dataclasses import dataclass, field
from typing import Optional

from src.core import setup_logger
from src.plugin import BasePlugin, PluginResult

logger = setup_logger("discord")

try:
    import requests as req_lib
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

DISCORD_API_BASE = "https://discord.com/api/v10"


def _get_token() -> Optional[str]:
    """Get Discord bot token from environment."""
    return os.environ.get("DISCORD_BOT_TOKEN")


def _api_headers(token: str) -> dict:
    """Get API headers with bot authentication."""
    return {
        "Authorization": f"Bot {token}",
        "Content-Type": "application/json",
        "User-Agent": "ProjectAtlas/1.0",
    }


def _api_get(token: str, endpoint: str, params: Optional[dict] = None) -> Optional[dict]:
    """Make a GET request to Discord API."""
    if not _HAS_REQUESTS:
        logger.warning("requests not installed")
        return None
    try:
        url = f"{DISCORD_API_BASE}/{endpoint}"
        resp = req_lib.get(url, headers=_api_headers(token), params=params, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 429:
            retry = int(resp.headers.get("Retry-After", 5))
            logger.warning(f"Discord rate limited, retry after {retry}s")
            return {"error": "rate_limited", "retry_after": retry}
        else:
            logger.warning(f"Discord API error {resp.status_code}: {resp.text[:200]}")
            return None
    except Exception as e:
        logger.warning(f"Discord API GET failed: {e}")
        return None


def _api_post(token: str, endpoint: str, data: dict) -> Optional[dict]:
    """Make a POST request to Discord API."""
    if not _HAS_REQUESTS:
        return None
    try:
        url = f"{DISCORD_API_BASE}/{endpoint}"
        resp = req_lib.post(url, headers=_api_headers(token), json=data, timeout=10)
        if resp.status_code in (200, 201, 204):
            return resp.json() if resp.text else {"success": True}
        else:
            logger.warning(f"Discord API POST error {resp.status_code}: {resp.text[:200]}")
            return None
    except Exception as e:
        logger.warning(f"Discord API POST failed: {e}")
        return None


class DiscordPlugin(BasePlugin):
    """
    Integrates Project Atlas with Discord via the REST API.

    Commands:
    - "me" / "info": Get bot info
    - "channels" / "guilds": List channels/guilds
    - "send <channel_id/name> <message>": Send a message
    - "read [channel_id] [limit]": Read recent messages
    - "help": Show command help

    Setup:
    1. Go to https://discord.com/developers/applications
    2. Create a new application → Bot → Copy token
    3. Set DISCORD_BOT_TOKEN environment variable
    4. Invite bot to your server with 'Send Messages' and 'Read Message History' permissions

    Examples:
        "me"
        "channels"
        "send 123456789 Hello from Atlas!"
        "read 123456789 5"
    """

    name = "discord"
    description = "Kết nối Project Atlas với Discord"

    def execute(self, input_str: str) -> PluginResult:
        """Execute a Discord command."""
        text = input_str.strip()
        if not text:
            return self._show_help()

        token = _get_token()
        if not token:
            return PluginResult(
                success=False,
                error=(
                    "❌ **Chưa cấu hình Discord Bot Token.**\\n\\n"
                    "1. Truy cập https://discord.com/developers/applications\\n"
                    "2. Tạo ứng dụng mới → Bot → Copy token\\n"
                    "3. Set biến môi trường: `DISCORD_BOT_TOKEN=...`"
                )
            )

        cmd = text.lower()
        if cmd in ("me", "info"):
            return self._cmd_me(token)
        elif cmd in ("channels", "guilds"):
            return self._cmd_channels(token)
        elif cmd.startswith("send "):
            return self._cmd_send(token, text[5:].strip())
        elif cmd.startswith("read "):
            return self._cmd_read(token, text[5:].strip())
        elif cmd in ("help", ""):
            return self._show_help()
        else:
            return PluginResult(
                success=False,
                error=f"Lệnh không hợp lệ: `{text}`\\n\\nGõ `help` để xem danh sách lệnh."
            )

    def _show_help(self) -> PluginResult:
        """Show help message."""
        return PluginResult(
            success=True,
            output=(
                "## 🤖 Discord Bot Commands\\n\\n"
                "| Command | Description |\\n"
                "|:--------|:------------|\\n"
                "| `me` | Bot info and status |\\n"
                "| `channels` | List available channels |\\n"
                "| `send <id/name> <msg>` | Send message to channel |\\n"
                "| `read <id> [limit]` | Read recent messages |\\n"
                "| `help` | Show this help |\\n\\n"
                "**Setup:**\\n"
                "1. `DISCORD_BOT_TOKEN` env var must be set\\n"
                "2. Bot must be invited to your server"
            )
        )

    def _cmd_me(self, token: str) -> PluginResult:
        """Get bot info."""
        user = _api_get(token, "users/@me")
        if user:
            return PluginResult(
                success=True,
                output=(
                    f"## 🤖 Discord Bot Info\\n\\n"
                    f"- **Name:** {user.get('username', 'N/A')}\\n"
                    f"- **ID:** {user.get('id', 'N/A')}\\n"
                    f"- **Verified:** {user.get('verified', False)}\\n"
                    f"- **MFA Enabled:** {user.get('mfa_enabled', False)}"
                )
            )
        return PluginResult(
            success=False,
            error="❌ Cannot connect to Discord API. Check your bot token."
        )

    def _cmd_channels(self, token: str) -> PluginResult:
        """List available channels/guilds."""
        guilds = _api_get(token, "users/@me/guilds")
        if not guilds:
            return PluginResult(
                success=False,
                error="❌ Cannot fetch guilds. Make sure the bot is in at least one server."
            )

        lines = ["## 📡 Discord Channels", ""]
        for guild in guilds[:5]:
            gid = guild.get("id", "")
            gname = guild.get("name", "Unknown")
            lines.append(f"### 🏠 {gname} (`{gid}`)")

            # Get channels for this guild
            channels = _api_get(token, f"guilds/{gid}/channels")
            if channels:
                for ch in channels[:10]:
                    ch_name = ch.get("name", "unknown")
                    ch_id = ch.get("id", "")
                    ch_type = "💬" if ch.get("type") == 0 else "🔊" if ch.get("type") == 2 else "📋"
                    lines.append(f"  {ch_type} `{ch_name}` ({ch_id})")
            lines.append("")

        return PluginResult(success=True, output="\n".join(lines))

    def _cmd_send(self, token: str, body: str) -> PluginResult:
        """Send a message to a channel."""
        parts = body.split(maxsplit=1)
        if len(parts) < 2:
            return PluginResult(
                success=False,
                error="Thiếu nội dung tin nhắn.\\n\\nĐịnh dạng: `send <channel_id> <message>`"
            )
        channel_id = parts[0].strip()
        message = parts[1].strip()

        result = _api_post(token, f"channels/{channel_id}/messages", {"content": message})
        if result:
            return PluginResult(
                success=True,
                output=f"✅ **Message sent** to channel `{channel_id}`\\n\\n> {message[:200]}"
            )
        return PluginResult(
            success=False,
            error=f"❌ Cannot send message to `{channel_id}`.\\nCheck the channel ID and bot permissions."
        )

    def _cmd_read(self, token: str, body: str) -> PluginResult:
        """Read recent messages from a channel."""
        parts = body.split()
        if not parts:
            return PluginResult(
                success=False,
                error="Thiếu channel ID.\\n\\nĐịnh dạng: `read <channel_id> [limit]`"
            )

        channel_id = parts[0]
        limit = min(int(parts[1]) if len(parts) > 1 else 10, 50)

        messages = _api_get(token, f"channels/{channel_id}/messages", {"limit": limit})
        if messages and isinstance(messages, list):
            lines = [f"## 📨 Recent Messages (last {len(messages)})", ""]
            for msg in reversed(messages):
                author = msg.get("author", {}).get("username", "Unknown")
                content = msg.get("content", "")[:150]
                timestamp = msg.get("timestamp", "")[:10]
                lines.append(f"**{author}** ({timestamp}): {content}")
            return PluginResult(success=True, output="\n".join(lines))
        elif messages and isinstance(messages, dict) and "error" in messages:
            return PluginResult(
                success=False,
                error=f"⚠️ Discord rate limited. Retry after {messages.get('retry_after', 5)}s."
            )
        else:
            return PluginResult(
                success=False,
                error="❌ Cannot read messages. Check channel ID and bot permissions."
            )
