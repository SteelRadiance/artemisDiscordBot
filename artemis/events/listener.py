"""
Copyright 2025, Vijay Challa - Use of this source code follows the MIT license found in the LICENSE file.

EventListener class for registering event handlers
"""

from typing import Callable, Optional, Any, Union
from dataclasses import dataclass


@dataclass
class EventListener:
    """
    Represents an event listener configuration.
    """
    event_name: Optional[str] = None
    command: Optional[str] = None
    periodic: Optional[int] = None  # Interval in seconds
    callback: Optional[Callable] = None
    guild_id: Optional[int] = None  # Optional guild ID filter
    help_text: Optional[Union[str, Callable]] = None  # Help text or callable returning help text
    
    @classmethod
    def new(cls) -> "EventListener":
        """Create a new EventListener builder."""
        return cls()
    
    def add_event(self, event_name: str) -> "EventListener":
        """Add a Discord event to listen to."""
        self.event_name = event_name
        return self
    
    def add_command(self, command: str) -> "EventListener":
        """Add a command to listen to."""
        self.command = command
        return self
    
    def set_periodic(self, interval: int) -> "EventListener":
        """Set a periodic task interval in seconds."""
        self.periodic = interval
        return self
    
    def set_callback(self, callback: Callable) -> "EventListener":
        """Set the callback function."""
        self.callback = callback
        return self
    
    def add_guild(self, guild_id: int) -> "EventListener":
        """Add a guild ID filter (command will only work in this guild)."""
        self.guild_id = guild_id
        return self
    
    def set_help(self, help_text: Union[str, Callable]) -> "EventListener":
        """Set help text for the command (string or callable returning string)."""
        self.help_text = help_text
        return self
