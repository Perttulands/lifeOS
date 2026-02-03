"""
LifeOS Notification Service

Send messages via Telegram and Discord for morning briefs and alerts.
Integrates with Clawdbot or directly with platform APIs.
"""

import httpx
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List
from datetime import datetime


class NotifyChannel(Enum):
    """Notification delivery channels."""
    TELEGRAM = "telegram"
    DISCORD = "discord"


@dataclass
class NotifyResult:
    """Result of a notification attempt."""
    success: bool
    channel: NotifyChannel
    message_id: Optional[str] = None
    error: Optional[str] = None


class MobileBriefFormatter:
    """
    Format daily briefs for mobile-friendly display.

    Optimizes for quick scanning on Telegram/Discord:
    - Clear emoji indicators
    - Compact but readable
    - Key metrics highlighted
    """

    @staticmethod
    def format_brief(
        content: str,
        date: str,
        sleep_hours: Optional[float] = None,
        readiness_score: Optional[int] = None,
        confidence: Optional[float] = None
    ) -> str:
        """
        Format a daily brief for mobile delivery.

        Args:
            content: The AI-generated brief content
            date: Date string (YYYY-MM-DD)
            sleep_hours: Optional sleep duration
            readiness_score: Optional Oura readiness score
            confidence: AI confidence score (0-1)

        Returns:
            Mobile-formatted message string
        """
        # Parse date for display
        try:
            dt = datetime.strptime(date, "%Y-%m-%d")
            date_display = dt.strftime("%A, %b %d")
        except ValueError:
            date_display = date

        # Build header with key metrics
        header_parts = [f"☀️ *Morning Brief*", f"_{date_display}_"]

        # Add quick stats line if we have data
        stats = []
        if sleep_hours is not None:
            hours = int(sleep_hours)
            mins = int((sleep_hours - hours) * 60)
            sleep_emoji = "😴" if sleep_hours >= 7 else "⚡" if sleep_hours >= 6 else "☕"
            stats.append(f"{sleep_emoji} {hours}h {mins}m sleep")

        if readiness_score is not None:
            ready_emoji = "💪" if readiness_score >= 70 else "🙂" if readiness_score >= 50 else "🪫"
            stats.append(f"{ready_emoji} {readiness_score}% ready")

        # Assemble message
        lines = [
            "\n".join(header_parts),
        ]

        if stats:
            lines.append("─" * 20)
            lines.append(" • ".join(stats))

        lines.append("")
        lines.append(content)

        # Add footer
        if confidence is not None:
            conf_pct = int(confidence * 100)
            lines.append("")
            lines.append(f"_AI confidence: {conf_pct}%_")

        return "\n".join(lines)

    @staticmethod
    def format_discord(
        content: str,
        date: str,
        sleep_hours: Optional[float] = None,
        readiness_score: Optional[int] = None,
        confidence: Optional[float] = None
    ) -> dict:
        """
        Format a daily brief as a Discord embed.

        Returns dict suitable for Discord webhook payload.
        """
        # Parse date
        try:
            dt = datetime.strptime(date, "%Y-%m-%d")
            date_display = dt.strftime("%A, %B %d, %Y")
        except ValueError:
            date_display = date

        # Build fields
        fields = []

        if sleep_hours is not None:
            hours = int(sleep_hours)
            mins = int((sleep_hours - hours) * 60)
            fields.append({
                "name": "😴 Sleep",
                "value": f"{hours}h {mins}m",
                "inline": True
            })

        if readiness_score is not None:
            fields.append({
                "name": "💪 Readiness",
                "value": f"{readiness_score}%",
                "inline": True
            })

        # Determine color based on readiness
        if readiness_score is not None:
            if readiness_score >= 70:
                color = 0x2ECC71  # Green
            elif readiness_score >= 50:
                color = 0xF1C40F  # Yellow
            else:
                color = 0xE74C3C  # Red
        else:
            color = 0x3498DB  # Blue default

        embed = {
            "title": "☀️ Morning Brief",
            "description": content,
            "color": color,
            "fields": fields,
            "footer": {
                "text": f"LifeOS • {date_display}"
            },
            "timestamp": datetime.utcnow().isoformat()
        }

        if confidence is not None:
            embed["footer"]["text"] += f" • {int(confidence * 100)}% confidence"

        return {"embeds": [embed]}


class NotificationService:
    """
    Service for sending notifications via Telegram and Discord.

    Supports:
    - Direct Telegram Bot API
    - Direct Discord Webhooks
    - Clawdbot proxy (future)
    """

    def __init__(
        self,
        telegram_bot_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
        discord_webhook_url: Optional[str] = None,
        timeout: float = 10.0
    ):
        """
        Initialize the notification service.

        Args:
            telegram_bot_token: Telegram Bot API token
            telegram_chat_id: Default Telegram chat ID to send to
            discord_webhook_url: Discord webhook URL
            timeout: HTTP request timeout in seconds
        """
        self.telegram_bot_token = telegram_bot_token
        self.telegram_chat_id = telegram_chat_id
        self.discord_webhook_url = discord_webhook_url
        self.timeout = timeout
        self.formatter = MobileBriefFormatter()

    @property
    def telegram_enabled(self) -> bool:
        """Check if Telegram is configured."""
        return bool(self.telegram_bot_token and self.telegram_chat_id)

    @property
    def discord_enabled(self) -> bool:
        """Check if Discord is configured."""
        return bool(self.discord_webhook_url)

    @property
    def enabled_channels(self) -> List[NotifyChannel]:
        """Get list of enabled channels."""
        channels = []
        if self.telegram_enabled:
            channels.append(NotifyChannel.TELEGRAM)
        if self.discord_enabled:
            channels.append(NotifyChannel.DISCORD)
        return channels

    async def send_telegram(
        self,
        text: str,
        chat_id: Optional[str] = None,
        parse_mode: str = "Markdown"
    ) -> NotifyResult:
        """
        Send a message via Telegram Bot API.

        Args:
            text: Message text
            chat_id: Override default chat ID
            parse_mode: Telegram parse mode (Markdown, HTML, etc.)

        Returns:
            NotifyResult with success status
        """
        if not self.telegram_bot_token:
            return NotifyResult(
                success=False,
                channel=NotifyChannel.TELEGRAM,
                error="Telegram bot token not configured"
            )

        target_chat = chat_id or self.telegram_chat_id
        if not target_chat:
            return NotifyResult(
                success=False,
                channel=NotifyChannel.TELEGRAM,
                error="No chat ID specified"
            )

        url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
        payload = {
            "chat_id": target_chat,
            "text": text,
            "parse_mode": parse_mode
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                data = response.json()

                if response.status_code == 200 and data.get("ok"):
                    return NotifyResult(
                        success=True,
                        channel=NotifyChannel.TELEGRAM,
                        message_id=str(data.get("result", {}).get("message_id"))
                    )
                else:
                    error_desc = data.get("description", f"HTTP {response.status_code}")
                    return NotifyResult(
                        success=False,
                        channel=NotifyChannel.TELEGRAM,
                        error=error_desc
                    )

        except httpx.TimeoutException:
            return NotifyResult(
                success=False,
                channel=NotifyChannel.TELEGRAM,
                error="Request timed out"
            )
        except Exception as e:
            return NotifyResult(
                success=False,
                channel=NotifyChannel.TELEGRAM,
                error=str(e)
            )

    async def send_discord(
        self,
        content: Optional[str] = None,
        embed: Optional[dict] = None
    ) -> NotifyResult:
        """
        Send a message via Discord webhook.

        Args:
            content: Plain text content
            embed: Discord embed dict (or full payload with embeds key)

        Returns:
            NotifyResult with success status
        """
        if not self.discord_webhook_url:
            return NotifyResult(
                success=False,
                channel=NotifyChannel.DISCORD,
                error="Discord webhook URL not configured"
            )

        # Build payload
        if embed and "embeds" in embed:
            payload = embed  # Already formatted
        elif embed:
            payload = {"embeds": [embed]}
        elif content:
            payload = {"content": content}
        else:
            return NotifyResult(
                success=False,
                channel=NotifyChannel.DISCORD,
                error="No content or embed provided"
            )

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.discord_webhook_url,
                    json=payload
                )

                # Discord returns 204 No Content on success
                if response.status_code in (200, 204):
                    return NotifyResult(
                        success=True,
                        channel=NotifyChannel.DISCORD
                    )
                else:
                    return NotifyResult(
                        success=False,
                        channel=NotifyChannel.DISCORD,
                        error=f"HTTP {response.status_code}: {response.text}"
                    )

        except httpx.TimeoutException:
            return NotifyResult(
                success=False,
                channel=NotifyChannel.DISCORD,
                error="Request timed out"
            )
        except Exception as e:
            return NotifyResult(
                success=False,
                channel=NotifyChannel.DISCORD,
                error=str(e)
            )

    async def send_brief(
        self,
        content: str,
        date: str,
        sleep_hours: Optional[float] = None,
        readiness_score: Optional[int] = None,
        confidence: Optional[float] = None,
        channels: Optional[List[NotifyChannel]] = None
    ) -> List[NotifyResult]:
        """
        Send a formatted daily brief to all configured channels.

        Args:
            content: The brief content from AI
            date: Date string (YYYY-MM-DD)
            sleep_hours: Optional sleep duration for display
            readiness_score: Optional readiness score for display
            confidence: AI confidence score
            channels: Specific channels to use (defaults to all enabled)

        Returns:
            List of NotifyResult for each channel attempted
        """
        target_channels = channels or self.enabled_channels
        results = []

        for channel in target_channels:
            if channel == NotifyChannel.TELEGRAM and self.telegram_enabled:
                formatted = self.formatter.format_brief(
                    content=content,
                    date=date,
                    sleep_hours=sleep_hours,
                    readiness_score=readiness_score,
                    confidence=confidence
                )
                result = await self.send_telegram(formatted)
                results.append(result)

            elif channel == NotifyChannel.DISCORD and self.discord_enabled:
                embed_payload = self.formatter.format_discord(
                    content=content,
                    date=date,
                    sleep_hours=sleep_hours,
                    readiness_score=readiness_score,
                    confidence=confidence
                )
                result = await self.send_discord(embed=embed_payload)
                results.append(result)

        return results

    def send_brief_sync(
        self,
        content: str,
        date: str,
        sleep_hours: Optional[float] = None,
        readiness_score: Optional[int] = None,
        confidence: Optional[float] = None,
        channels: Optional[List[NotifyChannel]] = None
    ) -> List[NotifyResult]:
        """
        Synchronous wrapper for send_brief.

        Use this from cron jobs or non-async contexts.
        """
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            self.send_brief(
                content=content,
                date=date,
                sleep_hours=sleep_hours,
                readiness_score=readiness_score,
                confidence=confidence,
                channels=channels
            )
        )


def get_notification_service() -> NotificationService:
    """
    Factory function to create NotificationService from config.
    """
    from ..config import settings

    return NotificationService(
        telegram_bot_token=settings.telegram_bot_token,
        telegram_chat_id=settings.telegram_chat_id,
        discord_webhook_url=settings.discord_webhook_url
    )
