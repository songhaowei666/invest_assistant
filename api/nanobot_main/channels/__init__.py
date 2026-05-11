"""Chat channels module with plugin architecture."""

from nanobot_main.channels.base import BaseChannel
from nanobot_main.channels.manager import ChannelManager

__all__ = ["BaseChannel", "ChannelManager"]
