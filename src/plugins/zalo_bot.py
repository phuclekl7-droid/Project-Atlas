"""
Zalo OA Integration (Feature #85).
Connects Project Atlas with Zalo Official Account for messaging.

Uses the Zalo Official Account API (OpenAPI) to:
- Send text messages to followers
- Get user/profile info
- Handle simple message flows

API Reference: https://developers.zalo.me/docs/official-account

Usage:
    ZaloPlugin.execute("send <user_id> Hello!")
    ZaloPlugin.execute("me")
    ZaloPlugin.execute("help")

Requirements:
- ZALO_OA_ACCESS_TOKEN env var (Zalo OA access token)
- ZALO_OA_APP_ID env var (optional, for API calls)
"""

import json
import os
import re
from typing import Optional

from src.core import setup_logger
from src.plugin import BasePlugin, PluginResult

logger = setup_logger("zalo")

try:
    import requests as req_lib
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

ZALO_API_BASE = "https://openapi.zalo.me/v2.0"


def _get_access_token() -> Optional[str]:
    """Get Zalo OA access token from environment."""
    return os.environ.get("ZALO_OA_ACCESS_TOKEN")


def _get_app_id() -> str:
    """Get Zalo OA App ID from environment."""
    return os.environ.get("ZALO_OA_APP_ID", "")


def _api_get(endpoint: str, params: Optional[dict] = None) -> Optional[dict]:
    """Make a GET request to Zalo API."""
    token = _get_access_token()
    if not token or not _HAS_REQUESTS:
        logger.warning("Zalo API not available")
        return None
    try:
        url = f"{ZALO_API_BASE}/{endpoint}"
        headers = {"access_token": token}
        resp = req_lib.get(url, headers=headers, params=params, timeout=10)
        data = resp.json()
        if data.get("error") == 0:
            return data.get("data")
        logger.warning(f"Zalo API error {data.get('error')}: {data.get('message', 'unknown')}")
        return None
    except Exception as e:
        logger.warning(f"Zalo API GET failed: {e}")
        return None


def _api_post(endpoint: str, data: dict) -> Optional[dict]:
    """Make a POST request to Zalo API."""
    token = _get_access_token()
    if not token or not _HAS_REQUESTS:
        return None
    try:
        url = f"{ZALO_API_BASE}/{endpoint}"
        headers = {
            "access_token": token,
            "Content-Type": "application/json",
        }
        resp = req_lib.post(url, headers=headers, json=data, timeout=10)
        result = resp.json()
        if result.get("error") == 0:
            return result.get("data")
        logger.warning(f"Zalo API POST error: {result}")
        return None
    except Exception as e:
        logger.warning(f"Zalo API POST failed: {e}")
        return None


class ZaloPlugin(BasePlugin):
    """
    Integrates Project Atlas with Zalo Official Account.

    Commands:
    - "me" / "info": Get OA profile info
    - "send <user_id> <message>": Send text message to a follower
    - "help": Show available commands

    Setup:
    1. Go to https://developers.zalo.me
    2. Create an Official Account app
    3. Get access_token from the app credentials
    4. Set ZALO_OA_ACCESS_TOKEN environment variable

    Examples:
        "me"
        "send 123456789 Xin chào! Tôi là Atlas, trợ lý AI của bạn."
        "help"
    """

    name = "zalo"
    description = "Kết nối Project Atlas với Zalo Official Account"

    def execute(self, input_str: str) -> PluginResult:
        """Execute a Zalo command."""
        text = input_str.strip()
        if not text:
            return self._show_help()

        token = _get_access_token()
        if not token:
            return PluginResult(
                success=False,
                error=(
                    "❌ **Chưa cấu hình Zalo OA Token.**\\n\\n"
                    "1. Truy cập https://developers.zalo.me\\n"
                    "2. Tạo ứng dụng Official Account\\n"
                    "3. Lấy access_token từ app credentials\\n"
                    "4. Set: `ZALO_OA_ACCESS_TOKEN=...`"
                )
            )

        cmd = text.lower()

        if cmd in ("me", "info"):
            return self._cmd_me()
        elif cmd.startswith("send "):
            return self._cmd_send(text[5:].strip())
        elif cmd in ("help", ""):
            return self._show_help()
        else:
            return PluginResult(
                success=False,
                error=f"Lệnh không hợp lệ: `{text}`\\n\\nLệnh: me, send, help"
            )

    def _show_help(self) -> PluginResult:
        """Show help message."""
        return PluginResult(
            success=True,
            output=(
                "## 💬 Zalo OA Commands\\n\\n"
                "| Command | Description |\\n"
                "|:--------|:------------|\\n"
                "| `me` | OA profile info |\\n"
                "| `send <user_id> <msg>` | Send message to follower |\\n"
                "| `help` | Show this help |\\n\\n"
                "**Setup:**\\n"
                "1. `ZALO_OA_ACCESS_TOKEN` env var must be set\\n"
                "2. OA must have messaging permission"
            )
        )

    def _cmd_me(self) -> PluginResult:
        """Get OA profile info."""
        data = _api_get("oa/getprofile")
        if data:
            return PluginResult(
                success=True,
                output=(
                    f"## 💬 Zalo OA Profile\\n\\n"
                    f"- **Name:** {data.get('name', 'N/A')}\\n"
                    f"- **ID:** {data.get('oaid', 'N/A')}\\n"
                    f"- **Description:** {data.get('description', 'N/A')[:200]}\\n"
                    f"- **Followers:** {data.get('followers', 0):,}\\n"
                    f"- **Verified:** {data.get('verified', False)}"
                )
            )
        return PluginResult(
            success=False,
            error="❌ Cannot connect to Zalo API. Check your access token."
        )

    def _cmd_send(self, body: str) -> PluginResult:
        """Send a text message to a follower."""
        parts = body.split(maxsplit=1)
        if len(parts) < 2:
            return PluginResult(
                success=False,
                error="Thiếu nội dung tin nhắn.\\n\\nĐịnh dạng: `send <user_id> <message>`"
            )

        user_id = parts[0].strip()
        message = parts[1].strip()

        result = _api_post("oa/message", {
            "recipient": {"user_id": user_id},
            "message": {"text": message},
        })

        if result:
            return PluginResult(
                success=True,
                output=f"✅ **Message sent** to user `{user_id}`\\n\\n> {message[:200]}"
            )
        return PluginResult(
            success=False,
            error=f"❌ Cannot send message to `{user_id}`.\\nCheck the user ID and OA permissions."
        )
