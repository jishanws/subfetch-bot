"""Tests for Telegram handler registration."""

import unittest

from telegram.ext import CommandHandler, MessageHandler

from main import create_application


class MainHandlerRegistrationTests(unittest.TestCase):
    """Main application handler registration tests."""

    def test_start_command_handler_registered_once(self) -> None:
        application = create_application("123:ABC")
        handlers = [
            handler
            for group_handlers in application.handlers.values()
            for handler in group_handlers
        ]

        start_handlers = [
            handler
            for handler in handlers
            if isinstance(handler, CommandHandler) and "start" in handler.commands
        ]

        self.assertEqual(len(start_handlers), 1)

    def test_text_handler_excludes_commands_and_is_last(self) -> None:
        application = create_application("123:ABC")
        handlers = application.handlers[0]
        text_handler = handlers[-1]

        self.assertIsInstance(text_handler, MessageHandler)
        self.assertEqual(text_handler.callback.__name__, "handle_text_message")
        self.assertIn("filters.TEXT", str(text_handler.filters))
        self.assertIn("inverted filters.COMMAND", str(text_handler.filters))


if __name__ == "__main__":
    unittest.main()
