"""Slash command routing and built-in handlers."""

from nanobot_main.command.builtin import register_builtin_commands
from nanobot_main.command.router import CommandContext, CommandRouter

__all__ = ["CommandContext", "CommandRouter", "register_builtin_commands"]
