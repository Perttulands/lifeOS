"""
LifeOS Notification Service

Send messages via Telegram and Discord for morning briefs and alerts.
Integrates with Clawdbot or directly with platform APIs.
Supports quiet hours to avoid notifications during sleep.
"""

import httpx
from dataclasses import dataclass
from enum import Enum
from typing import Optional, List, Tuple
from datetime import datetime, timezone, timedelta, time

try:
    from zoneinfo import ZoneInfo
except ImportError:
    from backports.zoneinfo import ZoneInfo


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
    blocked_by_quiet_hours: bool = False


class QuietHoursChecker:
    """
    Check if current time is within quiet hours (no notifications).

    Respects user timezone and handles overnight quiet periods
    (e.g., 23:00-08:00 crossing midnight).
    """

    def __init__(
        self,
        start_time: str = "23:00",
        end_time: str = "08:00",
        timezone_name: str = "UTC",
        enabled: bool = True
    ):
        """
        Initialize quiet hours checker.

        Args:
            start_time: Start of quiet hours (HH:MM format, 24h)
            end_time: End of quiet hours (HH:MM format, 24h)
            timezone_name: IANA timezone name (e.g., "Europe/Helsinki")
            enabled: Whether quiet hours checking is enabled
        """
        self.enabled = enabled
        self.timezone_name = timezone_name

        # Parse times
        self.start_hour, self.start_minute = self._parse_time(start_time)
        self.end_hour, self.end_minute = self._parse_time(end_time)

        # Get timezone
        try:
            self.tz = ZoneInfo(timezone_name)
        except Exception:
            self.tz = timezone.utc

    @staticmethod
    def _parse_time(time_str: str) -> Tuple[int, int]:
        """Parse HH:MM string into hour and minute."""
        try:
            parts = time_str.split(":")
            return int(parts[0]), int(parts[1])
        except (ValueError, IndexError):
            return 0, 0

    def _time_to_minutes(self, hour: int, minute: int) -> int:
        """Convert hour:minute to minutes since midnight."""
        return hour * 60 + minute

    def is_quiet_time(self, check_time: Optional[datetime] = None) -> bool:
        """
        Check if the given time (or now) is within quiet hours.

        Args:
            check_time: Time to check (defaults to now in user timezone)

        Returns:
            True if notifications should be suppressed
        """
        if not self.enabled:
            return False

        # Get current time in user's timezone
        if check_time is None:
            check_time = datetime.now(self.tz)
        elif check_time.tzinfo is None:
            check_time = check_time.replace(tzinfo=self.tz)
        else:
            check_time = check_time.astimezone(self.tz)

        current_minutes = self._time_to_minutes(check_time.hour, check_time.minute)
        start_minutes = self._time_to_minutes(self.start_hour, self.start_minute)
        end_minutes = self._time_to_minutes(self.end_hour, self.end_minute)

        # Handle overnight quiet period (e.g., 23:00 - 08:00)
        if start_minutes > end_minutes:
            # Quiet period crosses midnight
            return current_minutes >= start_minutes or current_minutes < end_minutes
        else:
            # Normal period (e.g., 13:00 - 14:00)
            return start_minutes <= current_minutes < end_minutes

    def time_until_quiet_ends(self, check_time: Optional[datetime] = None) -> Optional[timedelta]:
        """
        Get time remaining until quiet hours end.

        Returns:
            timedelta until quiet hours end, or None if not in quiet hours
        """
        if not self.is_quiet_time(check_time):
            return None

        if check_time is None:
            check_time = datetime.now(self.tz)
        elif check_time.tzinfo is None:
            check_time = check_time.replace(tzinfo=self.tz)
        else:
            check_time = check_time.astimezone(self.tz)

        # Calculate end time today or tomorrow
        end_today = check_time.replace(
            hour=self.end_hour,
            minute=self.end_minute,
            second=0,
            microsecond=0
        )

        if end_today <= check_time:
            # End time is tomorrow
            end_today += timedelta(days=1)

        return end_today - check_time

    def get_status(self) -> dict:
        """Get current quiet hours status."""
        now = datetime.now(self.tz)
        is_quiet = self.is_quiet_time(now)
        time_remaining = self.time_until_quiet_ends(now)

        return {
            "enabled": self.enabled,
            "is_quiet_time": is_quiet,
            "current_time": now.strftime("%H:%M"),
            "timezone": self.timezone_name,
            "quiet_start": f"{self.start_hour:02d}:{self.start_minute:02d}",
            "quiet_end": f"{self.end_hour:02d}:{self.end_minute:02d}",
            "minutes_until_end": int(time_remaining.total_seconds() / 60) if time_remaining else None
        }


class MobileFormatter:
    """
    Format insights for mobile-friendly display.

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
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        if confidence is not None:
            embed["footer"]["text"] += f" • {int(confidence * 100)}% confidence"

        return {"embeds": [embed]}

    @staticmethod
    def format_weekly_review(
        content: str,
        week_ending: str,
        avg_sleep_hours: Optional[float] = None,
        avg_readiness: Optional[int] = None,
        patterns: Optional[List[dict]] = None,
        confidence: Optional[float] = None
    ) -> str:
        """
        Format a weekly review for Telegram delivery.

        Args:
            content: The AI-generated review content
            week_ending: End date of the week (YYYY-MM-DD)
            avg_sleep_hours: Average sleep duration for the week
            avg_readiness: Average readiness score for the week
            patterns: List of detected patterns with name/description
            confidence: AI confidence score (0-1)

        Returns:
            Mobile-formatted message string
        """
        # Parse date for display
        try:
            dt = datetime.strptime(week_ending, "%Y-%m-%d")
            week_start = dt - timedelta(days=6)
            date_display = f"{week_start.strftime('%b %d')} - {dt.strftime('%b %d')}"
        except ValueError:
            date_display = week_ending

        # Build header
        lines = [
            "📊 *Weekly Review*",
            f"_{date_display}_",
            "─" * 20,
        ]

        # Add weekly stats
        stats = []
        if avg_sleep_hours is not None:
            hours = int(avg_sleep_hours)
            mins = int((avg_sleep_hours - hours) * 60)
            stats.append(f"😴 Avg {hours}h {mins}m sleep")

        if avg_readiness is not None:
            ready_emoji = "💪" if avg_readiness >= 70 else "🙂" if avg_readiness >= 50 else "🪫"
            stats.append(f"{ready_emoji} Avg {avg_readiness}% ready")

        if stats:
            lines.append(" • ".join(stats))
            lines.append("")

        # Add main content
        lines.append(content)

        # Add patterns section if available
        if patterns:
            lines.append("")
            lines.append("*Patterns Detected:*")
            for p in patterns[:3]:  # Limit to top 3
                name = p.get('name', 'Pattern')
                lines.append(f"• {name}")

        # Add footer
        if confidence is not None:
            lines.append("")
            lines.append(f"_AI confidence: {int(confidence * 100)}%_")

        return "\n".join(lines)

    @staticmethod
    def format_weekly_review_discord(
        content: str,
        week_ending: str,
        avg_sleep_hours: Optional[float] = None,
        avg_readiness: Optional[int] = None,
        patterns: Optional[List[dict]] = None,
        confidence: Optional[float] = None
    ) -> dict:
        """
        Format a weekly review as a Discord embed.

        Returns dict suitable for Discord webhook payload.
        """
        # Parse date
        try:
            dt = datetime.strptime(week_ending, "%Y-%m-%d")
            week_start = dt - timedelta(days=6)
            date_display = f"{week_start.strftime('%B %d')} - {dt.strftime('%B %d, %Y')}"
        except ValueError:
            date_display = week_ending

        # Build fields
        fields = []

        if avg_sleep_hours is not None:
            hours = int(avg_sleep_hours)
            mins = int((avg_sleep_hours - hours) * 60)
            fields.append({
                "name": "😴 Avg Sleep",
                "value": f"{hours}h {mins}m",
                "inline": True
            })

        if avg_readiness is not None:
            fields.append({
                "name": "💪 Avg Readiness",
                "value": f"{avg_readiness}%",
                "inline": True
            })

        # Add patterns as a field
        if patterns:
            pattern_text = "\n".join([f"• {p.get('name', 'Pattern')}" for p in patterns[:3]])
            fields.append({
                "name": "🔍 Patterns",
                "value": pattern_text or "None detected",
                "inline": False
            })

        # Determine color based on avg readiness
        if avg_readiness is not None:
            if avg_readiness >= 70:
                color = 0x2ECC71  # Green
            elif avg_readiness >= 50:
                color = 0xF1C40F  # Yellow
            else:
                color = 0xE74C3C  # Red
        else:
            color = 0x9B59B6  # Purple for weekly review

        embed = {
            "title": "📊 Weekly Review",
            "description": content,
            "color": color,
            "fields": fields,
            "footer": {
                "text": f"LifeOS • {date_display}"
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

        if confidence is not None:
            embed["footer"]["text"] += f" • {int(confidence * 100)}% confidence"

        return {"embeds": [embed]}


# Alias for backwards compatibility
MobileBriefFormatter = MobileFormatter


class NotificationService:
    """
    Service for sending notifications via Telegram and Discord.

    Supports:
    - Direct Telegram Bot API
    - Direct Discord Webhooks
    - Quiet hours (no notifications during sleep)
    - User timezone support
    """

    def __init__(
        self,
        telegram_bot_token: Optional[str] = None,
        telegram_chat_id: Optional[str] = None,
        discord_webhook_url: Optional[str] = None,
        timeout: float = 10.0,
        quiet_hours_start: str = "23:00",
        quiet_hours_end: str = "08:00",
        user_timezone: str = "UTC",
        quiet_hours_enabled: bool = True
    ):
        """
        Initialize the notification service.

        Args:
            telegram_bot_token: Telegram Bot API token
            telegram_chat_id: Default Telegram chat ID to send to
            discord_webhook_url: Discord webhook URL
            timeout: HTTP request timeout in seconds
            quiet_hours_start: Start of quiet period (HH:MM)
            quiet_hours_end: End of quiet period (HH:MM)
            user_timezone: User's timezone (IANA format)
            quiet_hours_enabled: Whether to enforce quiet hours
        """
        self.telegram_bot_token = telegram_bot_token
        self.telegram_chat_id = telegram_chat_id
        self.discord_webhook_url = discord_webhook_url
        self.timeout = timeout
        self.formatter = MobileBriefFormatter()

        # Initialize quiet hours checker
        self.quiet_hours = QuietHoursChecker(
            start_time=quiet_hours_start,
            end_time=quiet_hours_end,
            timezone_name=user_timezone,
            enabled=quiet_hours_enabled
        )

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

    def is_quiet_time(self) -> bool:
        """Check if current time is within quiet hours."""
        return self.quiet_hours.is_quiet_time()

    def get_quiet_hours_status(self) -> dict:
        """Get current quiet hours status."""
        return self.quiet_hours.get_status()

    def _check_quiet_hours(self, bypass: bool = False) -> Optional[NotifyResult]:
        """
        Check if notifications are blocked by quiet hours.

        Args:
            bypass: If True, skip quiet hours check

        Returns:
            NotifyResult with blocked_by_quiet_hours=True if blocked, None otherwise
        """
        if not bypass and self.quiet_hours.is_quiet_time():
            status = self.quiet_hours.get_status()
            return NotifyResult(
                success=False,
                channel=NotifyChannel.TELEGRAM,  # placeholder
                error=f"Quiet hours active ({status['quiet_start']}-{status['quiet_end']} {status['timezone']}). "
                      f"Notifications resume in {status['minutes_until_end']} minutes.",
                blocked_by_quiet_hours=True
            )
        return None

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
        channels: Optional[List[NotifyChannel]] = None,
        bypass_quiet_hours: bool = False
    ) -> List[NotifyResult]:
        """
        Send a formatted daily brief to all configured channels.

        Respects quiet hours unless bypass_quiet_hours=True.

        Args:
            content: The brief content from AI
            date: Date string (YYYY-MM-DD)
            sleep_hours: Optional sleep duration for display
            readiness_score: Optional readiness score for display
            confidence: AI confidence score
            channels: Specific channels to use (defaults to all enabled)
            bypass_quiet_hours: Skip quiet hours check (for urgent messages)

        Returns:
            List of NotifyResult for each channel attempted
        """
        # Check quiet hours
        quiet_check = self._check_quiet_hours(bypass=bypass_quiet_hours)
        if quiet_check:
            # Return blocked result for each requested channel
            target_channels = channels or self.enabled_channels
            return [
                NotifyResult(
                    success=False,
                    channel=ch,
                    error=quiet_check.error,
                    blocked_by_quiet_hours=True
                )
                for ch in target_channels
            ]

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
        channels: Optional[List[NotifyChannel]] = None,
        bypass_quiet_hours: bool = False
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
                channels=channels,
                bypass_quiet_hours=bypass_quiet_hours
            )
        )

    async def send_weekly_review(
        self,
        content: str,
        week_ending: str,
        avg_sleep_hours: Optional[float] = None,
        avg_readiness: Optional[int] = None,
        patterns: Optional[List[dict]] = None,
        confidence: Optional[float] = None,
        channels: Optional[List[NotifyChannel]] = None,
        bypass_quiet_hours: bool = False
    ) -> List[NotifyResult]:
        """
        Send a formatted weekly review to all configured channels.

        Respects quiet hours unless bypass_quiet_hours=True.

        Args:
            content: The review content from AI
            week_ending: End date of the week (YYYY-MM-DD)
            avg_sleep_hours: Average sleep duration for the week
            avg_readiness: Average readiness score for the week
            patterns: List of detected patterns
            bypass_quiet_hours: Skip quiet hours check
            confidence: AI confidence score
            channels: Specific channels to use (defaults to all enabled)

        Returns:
            List of NotifyResult for each channel attempted
        """
        # Check quiet hours
        quiet_check = self._check_quiet_hours(bypass=bypass_quiet_hours)
        if quiet_check:
            target_channels = channels or self.enabled_channels
            return [
                NotifyResult(
                    success=False,
                    channel=ch,
                    error=quiet_check.error,
                    blocked_by_quiet_hours=True
                )
                for ch in target_channels
            ]

        target_channels = channels or self.enabled_channels
        results = []

        for channel in target_channels:
            if channel == NotifyChannel.TELEGRAM and self.telegram_enabled:
                formatted = self.formatter.format_weekly_review(
                    content=content,
                    week_ending=week_ending,
                    avg_sleep_hours=avg_sleep_hours,
                    avg_readiness=avg_readiness,
                    patterns=patterns,
                    confidence=confidence
                )
                result = await self.send_telegram(formatted)
                results.append(result)

            elif channel == NotifyChannel.DISCORD and self.discord_enabled:
                embed_payload = self.formatter.format_weekly_review_discord(
                    content=content,
                    week_ending=week_ending,
                    avg_sleep_hours=avg_sleep_hours,
                    avg_readiness=avg_readiness,
                    patterns=patterns,
                    confidence=confidence
                )
                result = await self.send_discord(embed=embed_payload)
                results.append(result)

        return results

    def send_weekly_review_sync(
        self,
        content: str,
        week_ending: str,
        avg_sleep_hours: Optional[float] = None,
        avg_readiness: Optional[int] = None,
        patterns: Optional[List[dict]] = None,
        confidence: Optional[float] = None,
        channels: Optional[List[NotifyChannel]] = None,
        bypass_quiet_hours: bool = False
    ) -> List[NotifyResult]:
        """
        Synchronous wrapper for send_weekly_review.

        Use this from cron jobs or non-async contexts.
        """
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            self.send_weekly_review(
                content=content,
                week_ending=week_ending,
                avg_sleep_hours=avg_sleep_hours,
                avg_readiness=avg_readiness,
                patterns=patterns,
                confidence=confidence,
                channels=channels,
                bypass_quiet_hours=bypass_quiet_hours
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
        discord_webhook_url=settings.discord_webhook_url,
        quiet_hours_start=settings.quiet_hours_start,
        quiet_hours_end=settings.quiet_hours_end,
        user_timezone=settings.user_timezone,
        quiet_hours_enabled=settings.quiet_hours_enabled
    )
