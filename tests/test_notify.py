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
            discord_webhook_url="https://discord.com/api/webhooks/test"
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
                telegram_chat_id="123"
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
