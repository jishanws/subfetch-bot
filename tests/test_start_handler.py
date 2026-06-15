"""Tests for the /start command handler."""

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from bot.handlers.start import (
    REPEATED_START_MESSAGE,
    WELCOME_MESSAGE,
    start_command,
    started_users,
)


class StartHandlerTests(unittest.IsolatedAsyncioTestCase):
    """Start command behavior tests."""

    def setUp(self) -> None:
        started_users.clear()

    async def test_first_start_returns_full_welcome(self) -> None:
        update = build_update(user_id=1001)

        await start_command(update, None)

        update.message.reply_text.assert_awaited_once_with(WELCOME_MESSAGE)
        self.assertIn(1001, started_users)

    async def test_second_start_from_same_user_returns_short_message(self) -> None:
        update = build_update(user_id=1001)

        await start_command(update, None)
        update.message.reply_text.reset_mock()
        await start_command(update, None)

        update.message.reply_text.assert_awaited_once_with(REPEATED_START_MESSAGE)

    async def test_different_user_gets_full_welcome(self) -> None:
        first_update = build_update(user_id=1001)
        second_update = build_update(user_id=2002)

        await start_command(first_update, None)
        await start_command(second_update, None)

        second_update.message.reply_text.assert_awaited_once_with(WELCOME_MESSAGE)
        self.assertIn(1001, started_users)
        self.assertIn(2002, started_users)

    async def test_only_one_reply_per_start_update(self) -> None:
        update = build_update(user_id=1001)

        await start_command(update, None)

        self.assertEqual(update.message.reply_text.await_count, 1)


def build_update(user_id: int) -> SimpleNamespace:
    """Build a minimal Telegram update stand-in for start handler tests."""
    return SimpleNamespace(
        effective_user=SimpleNamespace(id=user_id),
        message=SimpleNamespace(reply_text=AsyncMock()),
    )


if __name__ == "__main__":
    unittest.main()
