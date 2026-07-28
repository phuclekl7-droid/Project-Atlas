"""
Telegram Bot Integration (Feature #83).
Connects Project Atlas to Telegram for chatting via mobile.

Uses the Telegram Bot HTTP API (no extra libraries needed — only requests).
Supports:
- Long-polling for updates (getUpdates)
- Send/receive text messages
- Markdown formatting
- Session management per chat

Usage:
    TelegramBotPlugin.execute("start")  # Start polling
    TelegramBotPlugin.execute("stop")   # Stop polling
    TelegramBotPlugin.execute("status") # Bot status
    TelegramBotPlugin.execute("send @username Hello!")  # Send message

Requirements:
- BOT_TOKEN: Set TELEGRAM_BOT_TOKEN env var (get from @BotFather)
"""

import json
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

from src.core import setup_logger
from src.plugin import BasePlugin, PluginResult

logger = setup_logger("telegram_bot")

try:
    import requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/{method}"

_POLLING_THREAD: Optional[threading.Thread] = None
_POLLING_ACTIVE = False


@dataclass
class TelegramMessage:
    """Parsed Telegram message."""
    chat_id: int = 0
    text: str = ""
    username: str = ""
    message_id: int = 0
    date: int = 0


def _get_bot_token() -> Optional[str]:
    """Get the Telegram bot token from environment."""
    return os.environ.get("TELEGRAM_BOT_TOKEN") or os.environ.get("BOT_TOKEN")


def _api_call(token: str, method: str, data: Optional[dict] = None) -> Optional[dict]:
    """Make a Telegram Bot API call."""
    if not _HAS_REQUESTS:
        logger.error("requests not installed")
        return None
    try:
        url = TELEGRAM_API_URL.format(token=token, method=method)
        if data:
            resp = requests.post(url, json=data, timeout=10)
        else:
            resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        result = resp.json()
        if result.get("ok"):
            return result.get("result")
        logger.warning(f"Telegram API error: {result.get('description', 'unknown')}")
        return None
    except Exception as e:
        logger.warning(f"Telegram API call failed: {e}")
        return None


def _polling_loop(
    bot_token: str,
    message_handler: callable,
    poll_interval: float = 1.0,
):
    """Continuous polling loop for Telegram updates."""
    global _POLLING_ACTIVE
    last_update_id = 0
    logger.info("Telegram polling started")

    while _POLLING_ACTIVE:
        try:
            result = _api_call(bot_token, "getUpdates", {
                "offset": last_update_id + 1,
                "timeout": 30,
                "allowed_updates": ["message"],
            })
            if result:
                for update in result:
                    update_id = update.get("update_id", 0)
                    if update_id > last_update_id:
                        last_update_id = update_id
                    msg_data = update.get("message", {})
                    if msg_data:
                        chat_id = msg_data.get("chat", {}).get("id", 0)
                        text = msg_data.get("text", "")
                        username = msg_data.get("from", {}).get("username", "unknown")
                        msg_id = msg_data.get("message_id", 0)
                        msg_date = msg_data.get("date", 0)

                        if text:
                            msg = TelegramMessage(
                                chat_id=chat_id, text=text,
                                username=username, message_id=msg_id,
                                date=msg_date,
                            )
                            try:
                                message_handler(msg)
                            except Exception as e:
                                logger.error(f"Message handler error: {e}")
        except Exception as e:
            logger.warning(f"Polling error: {e}")

        time.sleep(poll_interval)

    logger.info("Telegram polling stopped")


def _handle_message(msg: TelegramMessage):
    """Default message handler — logs the message."""
    logger.info(f"Telegram [{msg.username}]: {msg.text[:100]}")


class TelegramBotPlugin(BasePlugin):
    """
    Connects Project Atlas to Telegram via the Bot API.

    Commands:
    - "start": Start the polling loop in background
    - "stop": Stop the polling loop
    - "status": Check bot status
    - "send <chat_id/username> <message>": Send a message
    - "me": Get bot info

    Setup:
    1. Message @BotFather on Telegram to create a bot
    2. Set the token: export TELEGRAM_BOT_TOKEN="your_token_here"
    3. Start the bot: "start"

    Examples:
        "status"
        "send 123456789 Hello from Atlas!"
        "start"
    """

    name = "telegram_bot"
    description = "Kết nối Project Atlas với Telegram"

    def __init__(self):
        super().__init__()
        self._handler = _handle_message

    def execute(self, input_str: str) -> PluginResult:
        """Execute a Telegram bot command."""
        global _POLLING_ACTIVE, _POLLING_THREAD
        text = input_str.strip().lower()

        if not text:
            return PluginResult(
                success=False,
                error="Vui lòng nhập lệnh: start, stop, status, send, me"
            )

        # Check token exists
        token = _get_bot_token()
        if not token:
            return PluginResult(
                success=False,
                error=(
                    "❌ **Chưa cấu hình Telegram Bot Token.**\n\n"
                    "1. Mở Telegram, tìm @BotFather\n"
                    "2. Gửi `/newbot` và làm theo hướng dẫn\n"
                    "3. Đặt token vào biến môi trường:\n"
                    "   `TELEGRAM_BOT_TOKEN=your_token_here`\n\n"
                    "Hoặc thêm vào file `.env`:\n"
                    "   `TELEGRAM_BOT_TOKEN=your_token_here`"
                )
            )

        if text == "start":
            if _POLLING_ACTIVE:
                return PluginResult(success=True, output="ℹ️ Bot polling **already running**.")
            _POLLING_ACTIVE = True
            _POLLING_THREAD = threading.Thread(
                target=_polling_loop,
                args=(token, self._handler),
                daemon=True,
            )
            _POLLING_THREAD.start()
            return PluginResult(
                success=True,
                output="✅ **Telegram bot started!** 🎉\n\n"
                       "Bot đang lắng nghe tin nhắn từ Telegram.\n"
                       "Gửi tin nhắn đến bot của bạn trên Telegram để test.\n\n"
                       "Lệnh: `stop` để dừng | `status` để kiểm tra"
            )

        elif text == "stop":
            if not _POLLING_ACTIVE:
                return PluginResult(success=True, output="ℹ️ Bot polling **already stopped**.")
            _POLLING_ACTIVE = False
            if _POLLING_THREAD:
                _POLLING_THREAD.join(timeout=3)
                _POLLING_THREAD = None
            return PluginResult(success=True, output="⏹️ **Telegram bot stopped.**")

        elif text == "status":
            # Get bot info from API
            me = _api_call(token, "getMe")
            status_lines = [
                "## 🤖 Telegram Bot Status",
                "",
                f"- **Polling:** {'🟢 Active' if _POLLING_ACTIVE else '🔴 Stopped'}",
            ]
            if me:
                status_lines.extend([
                    f"- **Bot Name:** {me.get('first_name', 'N/A')}",
                    f"- **Username:** @{me.get('username', 'N/A')}",
                    f"- **ID:** {me.get('id', 'N/A')}",
                    f"- **Can read messages:** {me.get('can_read_all_group_messages', False)}",
                ])
            else:
                status_lines.append("- ⚠️ **Cannot connect to Telegram API**")
                status_lines.append("  Kiểm tra token hoặc kết nối mạng.")

            return PluginResult(success=True, output="\n".join(status_lines))

        elif text.startswith("send "):
            # Send a message: "send <chat_id> <text>"
            body = text[5:].strip()
            space_idx = body.find(" ")
            if space_idx < 0:
                return PluginResult(success=False, error="Thiếu nội dung tin nhắn.\n\nĐịnh dạng: `send <chat_id> <message>`")

            target = body[:space_idx].strip()
            message = body[space_idx:].strip()
            chat_id = target

            # Try to resolve @username to chat_id (just use as-is for now)
            result = _api_call(token, "sendMessage", {
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown",
            })
            if result:
                return PluginResult(
                    success=True,
                    output=f"✅ **Message sent to** `{target}`\n\n> {message[:200]}"
                )
            return PluginResult(
                success=False,
                error=f"❌ Không thể gửi tin nhắn đến `{target}`.\n\n"
                      "Đảm bảo chat_id đúng và bot đã được thêm vào cuộc trò chuyện."
            )

        elif text == "me":
            me = _api_call(token, "getMe")
            if me:
                return PluginResult(
                    success=True,
                    output=(
                        f"## 🤖 Bot Info\n\n"
                        f"- **Name:** {me.get('first_name', 'N/A')}\n"
                        f"- **Username:** @{me.get('username', 'N/A')}\n"
                        f"- **ID:** {me.get('id', 'N/A')}\n"
                        f"- **Can join groups:** {me.get('can_join_groups', False)}"
                    )
                )
            return PluginResult(
                success=False,
                error="Không thể kết nối Telegram API. Kiểm tra token."
            )

        else:
            return PluginResult(
                success=False,
                error=f"Lệnh không hợp lệ: `{text}`\n\n"
                      "Các lệnh: start, stop, status, send, me"
            )
