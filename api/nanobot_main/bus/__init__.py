"""Message bus module for decoupled channel-agent communication."""

from nanobot_main.bus.events import InboundMessage, OutboundMessage
from nanobot_main.bus.queue import MessageBus

__all__ = ["MessageBus", "InboundMessage", "OutboundMessage"]
