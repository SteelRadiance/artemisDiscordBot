"""
Copyright 2025, Vijay Challa - Use of this source code follows the MIT license found in the LICENSE file.

Permission resolver for checking user permissions
"""

from typing import Optional
import logging
from artemis.permissions.guild_permissions import has_admin_access

logger = logging.getLogger("artemis.permissions")


class Permission:
    """
    Permission checker for commands and features.
    """
    
    def __init__(self, permission: str, bot, default: bool = False):
        """
        Initialize permission checker.
        
        Args:
            permission: Permission string (e.g., "p.plugin.command")
            bot: Bot instance
            default: Default value if permission not found
        """
        self.permission = permission
        self.bot = bot
        self.default = default
        self.message = None
    
    def add_message_context(self, message) -> "Permission":
        """Add message context for permission checking."""
        self.message = message
        return self
    
    async def resolve(self) -> bool:
        """
        Resolve whether the permission is granted.
        
        Returns:
            True if permission granted, False otherwise
        """
        if self.message and self.message.author:
            user_id = str(self.message.author.id)
            guild_id = str(self.message.guild.id) if self.message.guild else None
            
            if await has_admin_access(user_id, guild_id, self.bot):
                return True
        
        return self.default
    
    async def send_unauthorized_message(self, channel) -> None:
        """Send unauthorized message to channel."""
        await channel.send("You are not authorized to use this command.")
