"""
Command parser for handling prefix commands
"""

from typing import Optional, Tuple
from dataclasses import dataclass

from artemis.utils.helpers import split_command


@dataclass
class ParsedCommand:
    """Represents a parsed command."""
    command: str
    args: list
    content: str


class CommandParser:
    """Parses command messages."""
    
    def __init__(self, prefix: str = "!"):
        """
        Initialize command parser.
        
        Args:
            prefix: Command prefix
        """
        self.prefix = prefix
    
    def parse(self, content: str) -> Optional[ParsedCommand]:
        """
        Parse a command message.
        
        Args:
            content: Message content
            
        Returns:
            ParsedCommand or None if not a command
        """
        if not content.startswith(self.prefix):
            return None
        
        parts = split_command(content, self.prefix)
        if not parts:
            return None
        
        return ParsedCommand(
            command=parts[0].lower(),
            args=parts[1:],
            content=content
        )
