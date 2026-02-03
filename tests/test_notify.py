"""
Tests for Notification Service.

Tests the NotificationService, MobileBriefFormatter, and delivery endpoints.
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

import httpx
import respx

from src.integrations.notify import (
    NotificationService,
    NotifyChannel,
    NotifyResult,
    MobileBriefFormatter,
    MobileFormatter,
    QuietHoursChecker,
    get_notification_service,
)


# === MobileBriefFormatter Tests ===

class TestMobileBriefFormatter:
    """Tests for mobile-friendly brief formatting."""

    def test_format_brief_with_all_data(self):
        """Test Telegram format with all data present."""
        formatter = MobileBriefFormatter()

        result = formatter.format_brief(
            content="Test brief content",
            date="2026-02-03",
            sleep_hours=7.5,
            readiness_score=75,
            confidence=0.85
        )

        assert "Morning Brief" in result
        assert "Tuesday, Feb 03" in result
        assert "7h 30m sleep" in result
        assert "75% ready" in result
        assert "Test brief content" in result
        assert "85%" in result

    def test_format_brief_minimal_data(self):
        """Test Telegram format with minimal data."""
        formatter = MobileBriefFormatter()

        result = formatter.format_brief(
            content="Just a brief",
            date="2026-02-03"
        )

        assert "Morning Brief" in result
        assert "Just a brief" in result
        # No stats line when no data
        assert "sleep" not in result.lower() or "Sleep" not in result

    def test_format_brief_sleep_emoji_tiers(self):
        """Test correct emoji based on sleep duration."""
        formatter = MobileBriefFormatter()

        # Good sleep (>= 7h)
        result_good = formatter.format_brief(".", "2026-02-03", sleep_hours=7.5)
        assert "😴" in result_good

        # Medium sleep (6-7h)
        result_med = formatter.format_brief(".", "2026-02-03", sleep_hours=6.5)
        assert "⚡" in result_med

        # Low sleep (< 6h)
        result_low = formatter.format_brief(".", "2026-02-03", sleep_hours=5.5)
        assert "☕" in result_low

    def test_format_brief_readiness_emoji_tiers(self):
        """Test correct emoji based on readiness score."""
        formatter = MobileBriefFormatter()

        # High readiness (>= 70)
        result_high = formatter.format_brief(".", "2026-02-03", readiness_score=80)
        assert "💪" in result_high

        # Medium readiness (50-70)
        result_med = formatter.format_brief(".", "2026-02-03", readiness_score=60)
        assert "🙂" in result_med

        # Low readiness (< 50)
        result_low = formatter.format_brief(".", "2026-02-03", readiness_score=40)
        assert "🪫" in result_low

    def test_format_discord_embed(self):
        """Test Discord embed format."""
        formatter = MobileBriefFormatter()

        result = formatter.format_discord(
            content="Discord brief content",
            date="2026-02-03",
            sleep_hours=6.5,
            readiness_score=72,
            confidence=0.85
        )

        assert "embeds" in result
        embed = result["embeds"][0]

        assert embed["title"] == "☀️ Morning Brief"
        assert embed["description"] == "Discord brief content"
        assert len(embed["fields"]) == 2
        assert embed["fields"][0]["name"] == "😴 Sleep"
        assert embed["fields"][0]["value"] == "6h 30m"
        assert embed["fields"][1]["name"] == "💪 Readiness"
        assert embed["fields"][1]["value"] == "72%"

    def test_format_discord_color_by_readiness(self):
        """Test Discord embed color varies by readiness."""
        formatter = MobileBriefFormatter()

        # High readiness = green
        high = formatter.format_discord(".", "2026-02-03", readiness_score=75)
        assert high["embeds"][0]["color"] == 0x2ECC71

        # Medium readiness = yellow
        med = formatter.format_discord(".", "2026-02-03", readiness_score=55)
        assert med["embeds"][0]["color"] == 0xF1C40F

        # Low readiness = red
        low = formatter.format_discord(".", "2026-02-03", readiness_score=40)
        assert low["embeds"][0]["color"] == 0xE74C3C


# === NotificationService Tests ===

class TestNotificationService:
    """Tests for NotificationService."""

    def test_telegram_enabled_check(self):
        """Test Telegram enabled status."""
        # Not configured
        service = NotificationService()
        assert not service.telegram_enabled

        # Only token
        service = NotificationService(telegram_bot_token="token")
        assert not service.telegram_enabled

        # Only chat ID
        service = NotificationService(telegram_chat_id="123")
        assert not service.telegram_enabled

        # Both configured
        service = NotificationService(
            telegram_bot_token="token",
            telegram_chat_id="123"
        )
        assert service.telegram_enabled

    def test_discord_enabled_check(self):
        """Test Discord enabled status."""
        # Not configured
        service = NotificationService()
        assert not service.discord_enabled

        # Configured
        service = NotificationService(
            discord_webhook_url="https://discord.com/api/webhooks/test"
        )
        assert service.discord_enabled

    def test_enabled_channels_list(self):
        """Test listing enabled channels."""
        # None enabled
        service = NotificationService()
        assert service.enabled_channels == []

        # Only Telegram
        service = NotificationService(
            telegram_bot_token="token",
            telegram_chat_id="123"
        )
        assert service.enabled_channels == [NotifyChannel.TELEGRAM]

        # Only Discord
        service = NotificationService(
            discord_webhook_url="https://discord.com/api/webhooks/test"
        )
        assert service.enabled_channels == [NotifyChannel.DISCORD]

        # Both
        service = NotificationService(
            telegram_bot_token="token",
            telegram_chat_id="123",
            discord_webhook_url="https://discord.com/api/webhooks/test"
        )
        assert NotifyChannel.TELEGRAM in service.enabled_channels
        assert NotifyChannel.DISCORD in service.enabled_channels

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_telegram_success(self):
        """Test successful Telegram message send."""
        respx.post("https://api.telegram.org/bottest_token/sendMessage").mock(
            return_value=httpx.Response(200, json={
                "ok": True,
                "result": {"message_id": 123}
            })
        )

        service = NotificationService(
            telegram_bot_token="test_token",
            telegram_chat_id="456"
        )
        result = await service.send_telegram("Hello world")

        assert result.success
        assert result.channel == NotifyChannel.TELEGRAM
        assert result.message_id == "123"

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_telegram_failure(self):
        """Test Telegram message send failure."""
        respx.post("https://api.telegram.org/bottest_token/sendMessage").mock(
            return_value=httpx.Response(400, json={
                "ok": False,
                "description": "Bad Request: chat not found"
            })
        )

        service = NotificationService(
            telegram_bot_token="test_token",
            telegram_chat_id="invalid"
        )
        result = await service.send_telegram("Hello world")

        assert not result.success
        assert result.channel == NotifyChannel.TELEGRAM
        assert "chat not found" in result.error

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_telegram_not_configured(self):
        """Test Telegram send when not configured."""
        service = NotificationService()
        result = await service.send_telegram("Hello")

        assert not result.success
        assert "not configured" in result.error

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_discord_success(self):
        """Test successful Discord webhook send."""
        respx.post("https://discord.com/api/webhooks/test").mock(
            return_value=httpx.Response(204)
        )

        service = NotificationService(
            discord_webhook_url="https://discord.com/api/webhooks/test"
        )
        result = await service.send_discord(content="Hello Discord")

        assert result.success
        assert result.channel == NotifyChannel.DISCORD

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_discord_embed(self):
        """Test Discord webhook with embed."""
        respx.post("https://discord.com/api/webhooks/test").mock(
            return_value=httpx.Response(204)
        )

        service = NotificationService(
            discord_webhook_url="https://discord.com/api/webhooks/test"
        )
        result = await service.send_discord(embed={
            "title": "Test",
            "description": "Test embed"
        })

        assert result.success

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_discord_failure(self):
        """Test Discord webhook failure."""
        respx.post("https://discord.com/api/webhooks/test").mock(
            return_value=httpx.Response(404, text="Unknown Webhook")
        )

        service = NotificationService(
            discord_webhook_url="https://discord.com/api/webhooks/test"
        )
        result = await service.send_discord(content="Hello")

        assert not result.success
        assert "404" in result.error

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_brief_to_all_channels(self):
        """Test sending brief to all configured channels."""
        respx.post("https://api.telegram.org/bottoken/sendMessage").mock(
            return_value=httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})
        )
        respx.post("https://discord.com/api/webhooks/test").mock(
            return_value=httpx.Response(204)
        )

        service = NotificationService(
            telegram_bot_token="token",
            telegram_chat_id="123",
            discord_webhook_url="https://discord.com/api/webhooks/test",
            quiet_hours_enabled=False
        )

        results = await service.send_brief(
            content="Morning brief content",
            date="2026-02-03",
            sleep_hours=7.0,
            readiness_score=70,
            confidence=0.8
        )

        assert len(results) == 2
        assert all(r.success for r in results)

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_brief_specific_channels(self):
        """Test sending brief to specific channels only."""
        respx.post("https://api.telegram.org/bottoken/sendMessage").mock(
            return_value=httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})
        )
        # Discord not mocked - should not be called

        service = NotificationService(
            telegram_bot_token="token",
            telegram_chat_id="123",
            discord_webhook_url="https://discord.com/api/webhooks/test"
        )

        results = await service.send_brief(
            content="Brief",
            date="2026-02-03",
            channels=[NotifyChannel.TELEGRAM]
        )

        assert len(results) == 1
        assert results[0].channel == NotifyChannel.TELEGRAM

    def test_send_brief_sync(self):
        """Test synchronous send_brief wrapper."""
        with respx.mock:
            respx.post("https://api.telegram.org/bottoken/sendMessage").mock(
                return_value=httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})
            )

            service = NotificationService(
                telegram_bot_token="token",
                telegram_chat_id="123",
                quiet_hours_enabled=False
            )

            results = service.send_brief_sync(
                content="Sync brief",
                date="2026-02-03"
            )

            assert len(results) == 1
            assert results[0].success


# === Factory Function Tests ===

class TestGetNotificationService:
    """Tests for the factory function."""

    def test_get_notification_service_from_config(self):
        """Test creating service from config."""
        with patch('src.config.settings') as mock_settings:
            mock_settings.telegram_bot_token = "test_token"
            mock_settings.telegram_chat_id = "123"
            mock_settings.discord_webhook_url = ""

            service = get_notification_service()

            assert service.telegram_enabled
            assert not service.discord_enabled


# === NotifyResult Tests ===

class TestNotifyResult:
    """Tests for NotifyResult dataclass."""

    def test_success_result(self):
        """Test successful result attributes."""
        result = NotifyResult(
            success=True,
            channel=NotifyChannel.TELEGRAM,
            message_id="123"
        )

        assert result.success
        assert result.channel == NotifyChannel.TELEGRAM
        assert result.message_id == "123"
        assert result.error is None

    def test_failure_result(self):
        """Test failure result attributes."""
        result = NotifyResult(
            success=False,
            channel=NotifyChannel.DISCORD,
            error="Webhook not found"
        )

        assert not result.success
        assert result.channel == NotifyChannel.DISCORD
        assert result.message_id is None
        assert result.error == "Webhook not found"


# === Weekly Review Formatter Tests ===

class TestWeeklyReviewFormatter:
    """Tests for weekly review formatting."""

    def test_format_weekly_review_telegram(self):
        """Test Telegram format for weekly review."""
        formatter = MobileFormatter()

        result = formatter.format_weekly_review(
            content="Your week showed steady improvement.",
            week_ending="2026-02-03",
            avg_sleep_hours=7.2,
            avg_readiness=68,
            patterns=[
                {"name": "Late nights → tired mornings"},
                {"name": "Exercise → better sleep"}
            ],
            confidence=0.82
        )

        assert "Weekly Review" in result
        assert "Jan 28 - Feb 03" in result
        assert "Avg 7h 12m sleep" in result
        assert "Avg 68% ready" in result
        assert "Your week showed steady improvement" in result
        assert "Patterns Detected" in result
        assert "Late nights" in result
        assert "82%" in result

    def test_format_weekly_review_minimal_data(self):
        """Test weekly review with minimal data."""
        formatter = MobileFormatter()

        result = formatter.format_weekly_review(
            content="Weekly summary here",
            week_ending="2026-02-03"
        )

        assert "Weekly Review" in result
        assert "Weekly summary here" in result
        # No stats when no data
        assert "Avg" not in result or "sleep" not in result.lower()

    def test_format_weekly_review_discord(self):
        """Test Discord embed format for weekly review."""
        formatter = MobileFormatter()

        result = formatter.format_weekly_review_discord(
            content="Great week overall!",
            week_ending="2026-02-03",
            avg_sleep_hours=7.5,
            avg_readiness=75,
            patterns=[
                {"name": "Consistent bedtime wins"}
            ],
            confidence=0.85
        )

        assert "embeds" in result
        embed = result["embeds"][0]

        assert embed["title"] == "📊 Weekly Review"
        assert embed["description"] == "Great week overall!"
        assert len(embed["fields"]) == 3  # sleep, readiness, patterns
        assert embed["fields"][0]["name"] == "😴 Avg Sleep"
        assert embed["fields"][1]["name"] == "💪 Avg Readiness"
        assert embed["fields"][2]["name"] == "🔍 Patterns"

    def test_format_weekly_review_discord_color(self):
        """Test Discord embed color varies by avg readiness."""
        formatter = MobileFormatter()

        # High avg readiness = green
        high = formatter.format_weekly_review_discord(
            ".", "2026-02-03", avg_readiness=75
        )
        assert high["embeds"][0]["color"] == 0x2ECC71

        # Medium avg readiness = yellow
        med = formatter.format_weekly_review_discord(
            ".", "2026-02-03", avg_readiness=55
        )
        assert med["embeds"][0]["color"] == 0xF1C40F

        # Low avg readiness = red
        low = formatter.format_weekly_review_discord(
            ".", "2026-02-03", avg_readiness=40
        )
        assert low["embeds"][0]["color"] == 0xE74C3C


class TestWeeklyReviewSend:
    """Tests for sending weekly reviews."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_weekly_review_telegram(self):
        """Test sending weekly review via Telegram."""
        respx.post("https://api.telegram.org/bottoken/sendMessage").mock(
            return_value=httpx.Response(200, json={"ok": True, "result": {"message_id": 42}})
        )

        service = NotificationService(
            telegram_bot_token="token",
            telegram_chat_id="123",
            quiet_hours_enabled=False
        )

        results = await service.send_weekly_review(
            content="Weekly summary",
            week_ending="2026-02-03",
            avg_sleep_hours=7.0,
            avg_readiness=70
        )

        assert len(results) == 1
        assert results[0].success
        assert results[0].channel == NotifyChannel.TELEGRAM

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_weekly_review_discord(self):
        """Test sending weekly review via Discord."""
        respx.post("https://discord.com/api/webhooks/test").mock(
            return_value=httpx.Response(204)
        )

        service = NotificationService(
            discord_webhook_url="https://discord.com/api/webhooks/test",
            quiet_hours_enabled=False
        )

        results = await service.send_weekly_review(
            content="Weekly summary",
            week_ending="2026-02-03",
            patterns=[{"name": "Test pattern"}]
        )

        assert len(results) == 1
        assert results[0].success
        assert results[0].channel == NotifyChannel.DISCORD

    def test_send_weekly_review_sync(self):
        """Test synchronous weekly review send."""
        with respx.mock:
            respx.post("https://api.telegram.org/bottoken/sendMessage").mock(
                return_value=httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})
            )

            service = NotificationService(
                telegram_bot_token="token",
                telegram_chat_id="123",
                quiet_hours_enabled=False
            )

            results = service.send_weekly_review_sync(
                content="Weekly sync test",
                week_ending="2026-02-03"
            )

            assert len(results) == 1
            assert results[0].success


# === QuietHoursChecker Tests ===

class TestQuietHoursChecker:
    """Tests for QuietHoursChecker class."""

    def test_overnight_period_before_midnight(self):
        """Test quiet hours check during overnight period (before midnight)."""
        checker = QuietHoursChecker(
            start_time="23:00",
            end_time="08:00",
            timezone_name="UTC"
        )
        # 23:30 UTC should be in quiet hours
        test_time = datetime(2026, 2, 3, 23, 30)
        assert checker.is_quiet_time(test_time) is True

    def test_overnight_period_after_midnight(self):
        """Test quiet hours check during overnight period (after midnight)."""
        checker = QuietHoursChecker(
            start_time="23:00",
            end_time="08:00",
            timezone_name="UTC"
        )
        # 02:00 UTC should be in quiet hours
        test_time = datetime(2026, 2, 3, 2, 0)
        assert checker.is_quiet_time(test_time) is True

    def test_overnight_period_outside(self):
        """Test outside overnight quiet hours."""
        checker = QuietHoursChecker(
            start_time="23:00",
            end_time="08:00",
            timezone_name="UTC"
        )
        # 12:00 UTC should NOT be in quiet hours
        test_time = datetime(2026, 2, 3, 12, 0)
        assert checker.is_quiet_time(test_time) is False

    def test_daytime_period_inside(self):
        """Test daytime quiet hours (e.g., lunch break)."""
        checker = QuietHoursChecker(
            start_time="12:00",
            end_time="13:00",
            timezone_name="UTC"
        )
        # 12:30 UTC should be in quiet hours
        test_time = datetime(2026, 2, 3, 12, 30)
        assert checker.is_quiet_time(test_time) is True

    def test_daytime_period_outside(self):
        """Test outside daytime quiet hours."""
        checker = QuietHoursChecker(
            start_time="12:00",
            end_time="13:00",
            timezone_name="UTC"
        )
        # 14:00 UTC should NOT be in quiet hours
        test_time = datetime(2026, 2, 3, 14, 0)
        assert checker.is_quiet_time(test_time) is False

    def test_boundary_at_start(self):
        """Test boundary condition at start time."""
        checker = QuietHoursChecker(
            start_time="23:00",
            end_time="08:00",
            timezone_name="UTC"
        )
        # 23:00 exactly should be in quiet hours
        test_time = datetime(2026, 2, 3, 23, 0)
        assert checker.is_quiet_time(test_time) is True

    def test_boundary_at_end(self):
        """Test boundary condition at end time."""
        checker = QuietHoursChecker(
            start_time="23:00",
            end_time="08:00",
            timezone_name="UTC"
        )
        # 08:00 exactly should NOT be in quiet hours (end is exclusive)
        test_time = datetime(2026, 2, 3, 8, 0)
        assert checker.is_quiet_time(test_time) is False

    def test_time_until_quiet_ends(self):
        """Test calculating time until quiet hours end."""
        checker = QuietHoursChecker(
            start_time="23:00",
            end_time="08:00",
            timezone_name="UTC"
        )
        # At 02:00, should be 6 hours until 08:00
        test_time = datetime(2026, 2, 3, 2, 0)
        remaining = checker.time_until_quiet_ends(test_time)
        assert remaining is not None
        assert int(remaining.total_seconds() / 60) == 360  # 6 hours * 60 minutes

    def test_get_status(self):
        """Test status dict from get_status()."""
        checker = QuietHoursChecker(
            start_time="23:00",
            end_time="08:00",
            timezone_name="UTC"
        )
        status = checker.get_status()

        assert "enabled" in status
        assert "is_quiet_time" in status
        assert "timezone" in status
        assert status["timezone"] == "UTC"
        assert status["quiet_start"] == "23:00"
        assert status["quiet_end"] == "08:00"

    def test_disabled_checker(self):
        """Test checker when disabled."""
        checker = QuietHoursChecker(
            start_time="00:00",
            end_time="23:59",
            timezone_name="UTC",
            enabled=False
        )
        # Even when time is in range, should return False when disabled
        test_time = datetime(2026, 2, 3, 12, 0)
        assert checker.is_quiet_time(test_time) is False


# === NotificationService Quiet Hours Tests ===

class TestNotificationServiceQuietHours:
    """Tests for NotificationService quiet hours integration."""

    def test_quiet_hours_enabled_by_default(self):
        """Test that quiet hours can be enabled."""
        service = NotificationService(
            quiet_hours_start="23:00",
            quiet_hours_end="08:00",
            quiet_hours_enabled=True
        )
        assert service.quiet_hours.enabled is True

    def test_quiet_hours_disabled(self):
        """Test quiet hours disabled."""
        service = NotificationService(
            quiet_hours_start="23:00",
            quiet_hours_end="08:00",
            quiet_hours_enabled=False
        )
        assert service.quiet_hours.enabled is False

    def test_is_quiet_time_when_disabled(self):
        """Test is_quiet_time returns False when disabled."""
        service = NotificationService(
            quiet_hours_start="23:00",
            quiet_hours_end="08:00",
            quiet_hours_enabled=False
        )
        # Even during quiet hours, should return False when disabled
        assert service.is_quiet_time() is False

    def test_get_quiet_hours_status(self):
        """Test getting quiet hours status."""
        service = NotificationService(
            quiet_hours_start="22:00",
            quiet_hours_end="07:00",
            user_timezone="UTC",
            quiet_hours_enabled=True
        )
        status = service.get_quiet_hours_status()

        assert "enabled" in status
        assert "quiet_start" in status
        assert "quiet_end" in status
        assert status["quiet_start"] == "22:00"
        assert status["quiet_end"] == "07:00"

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_brief_blocked_by_quiet_hours(self):
        """Test that send_brief respects quiet hours."""
        service = NotificationService(
            telegram_bot_token="token",
            telegram_chat_id="123",
            quiet_hours_start="00:00",
            quiet_hours_end="23:59",  # Always quiet
            quiet_hours_enabled=True
        )

        results = await service.send_brief(
            content="Should be blocked",
            date="2026-02-03"
        )

        assert len(results) == 1
        assert results[0].success is False
        assert results[0].blocked_by_quiet_hours is True
        assert "quiet hours" in results[0].error.lower()

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_brief_bypass_quiet_hours(self):
        """Test that bypass_quiet_hours overrides quiet hours."""
        respx.post("https://api.telegram.org/bottoken/sendMessage").mock(
            return_value=httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})
        )

        service = NotificationService(
            telegram_bot_token="token",
            telegram_chat_id="123",
            quiet_hours_start="00:00",
            quiet_hours_end="23:59",  # Always quiet
            quiet_hours_enabled=True
        )

        results = await service.send_brief(
            content="Should bypass",
            date="2026-02-03",
            bypass_quiet_hours=True
        )

        assert len(results) == 1
        assert results[0].success is True

    @pytest.mark.asyncio
    @respx.mock
    async def test_send_weekly_review_blocked_by_quiet_hours(self):
        """Test that send_weekly_review respects quiet hours."""
        service = NotificationService(
            telegram_bot_token="token",
            telegram_chat_id="123",
            quiet_hours_start="00:00",
            quiet_hours_end="23:59",  # Always quiet
            quiet_hours_enabled=True
        )

        results = await service.send_weekly_review(
            content="Should be blocked",
            week_ending="2026-02-03"
        )

        assert len(results) == 1
        assert results[0].success is False
        assert results[0].blocked_by_quiet_hours is True

    def test_send_brief_sync_respects_quiet_hours(self):
        """Test sync wrapper respects quiet hours."""
        service = NotificationService(
            telegram_bot_token="token",
            telegram_chat_id="123",
            quiet_hours_start="00:00",
            quiet_hours_end="23:59",
            quiet_hours_enabled=True
        )

        results = service.send_brief_sync(
            content="Should be blocked",
            date="2026-02-03"
        )

        assert len(results) == 1
        assert results[0].blocked_by_quiet_hours is True
