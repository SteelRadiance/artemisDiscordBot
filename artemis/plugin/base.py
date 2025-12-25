"""
Copyright 2025, Vijay Challa - Use of this source code follows the MIT license found in the LICENSE file.

Plugin base classes and helpers
"""

from abc import ABC, abstractmethod
from typing import Optional, TYPE_CHECKING
import logging
import re
import disnake
from dateutil import parser as date_parser
from dateutil.relativedelta import relativedelta
from datetime import datetime
import pytz

if TYPE_CHECKING:
    from artemis.bot import ArtemisBot

logger = logging.getLogger("artemis.plugin")


class PluginInterface(ABC):
    """
    Base interface for all plugins.
    Plugins must implement the register method.
    """
    
    @staticmethod
    @abstractmethod
    def register(bot: "ArtemisBot") -> None:
        """
        Register the plugin with the bot.
        This method is called when the plugin is loaded.
        
        Args:
            bot: The bot instance
        """
        pass


class PluginHelper:
    """
    Mixin class providing common utilities for plugins.
    """
    
    @staticmethod
    def is_testing_client(bot: "ArtemisBot") -> bool:
        """Check if bot is in testing mode."""
        return getattr(bot.config, 'TESTING_MODE', False)
    
    @staticmethod
    def split_command(content: str, prefix: str = "!") -> list:
        """Split command content into parts."""
        from artemis.utils.helpers import split_command
        return split_command(content, prefix)
    
    @staticmethod
    def arg_substr(content: str, index: int, length: Optional[int] = None) -> Optional[str]:
        """Extract substring argument from command."""
        from artemis.utils.helpers import arg_substr
        return arg_substr(content, index, length)
    
    @staticmethod
    async def send(channel, content: str = "", **kwargs):
        """Send a message to a channel."""
        return await channel.send(content, **kwargs)
    
    @staticmethod
    async def exception_handler(message, exception: Exception, show_traceback: bool = False):
        """Handle exceptions in plugin commands."""
        error_msg = f"Error: {str(exception)}"
        if show_traceback:
            import traceback
            error_msg += f"\n```\n{traceback.format_exc()}\n```"
        try:
            return await message.channel.send(error_msg)
        except:
            logger.exception("Failed to send error message")
            return None
    
    @staticmethod
    async def unauthorized(message):
        """Send unauthorized message."""
        return await message.channel.send("You are not authorized to use this command.")
    
    @staticmethod
    async def parse_guild_user(guild: disnake.Guild, text: str) -> Optional[disnake.Member]:
        """
        Parse a user from text (mention, username#discriminator, username, or ID).
        Tries to fetch member if not in cache.
        
        Args:
            guild: Guild to search in
            text: Text to parse
            
        Returns:
            Member if found, None otherwise
        """
        if not text:
            return None
        
        text = text.strip()
        
        # Try mention format <@123456789> or <@!123456789>
        mention_match = re.match(r'<@!?(\d+)>', text)
        if mention_match:
            user_id = int(mention_match.group(1))
            member = guild.get_member(user_id)
            if not member:
                # Try fetching if not in cache
                try:
                    member = await guild.fetch_member(user_id)
                except (disnake.NotFound, disnake.HTTPException):
                    pass
            return member
        
        # Try user ID
        try:
            user_id = int(text)
            member = guild.get_member(user_id)
            if not member:
                # Try fetching if not in cache
                try:
                    member = await guild.fetch_member(user_id)
                except (disnake.NotFound, disnake.HTTPException):
                    pass
            return member
        except ValueError:
            pass
        
        # Try username#discriminator format (legacy Discord format)
        if '#' in text:
            username, discriminator = text.rsplit('#', 1)
            for member in guild.members:
                if member.name == username and member.discriminator == discriminator:
                    return member
        
        # Try username or display name (case-insensitive, partial match)
        text_lower = text.lower()
        matches = []
        for member in guild.members:
            if (member.name.lower() == text_lower or 
                (member.display_name and member.display_name.lower() == text_lower)):
                return member  # Exact match
            # Partial matches for better search
            if (member.name.lower().startswith(text_lower) or 
                (member.display_name and member.display_name.lower().startswith(text_lower))):
                matches.append(member)
        
        # Return first partial match if found
        if matches:
            return matches[0]
        
        return None
    
    @staticmethod
    def parse_role(guild: disnake.Guild, text: str) -> Optional[disnake.Role]:
        """
        Parse a role from text (mention, name, or ID).
        
        Args:
            guild: Guild to search in
            text: Text to parse
            
        Returns:
            Role if found, None otherwise
        """
        if not text:
            return None
        
        text = text.strip()
        
        # Try mention format <@&123456789>
        mention_match = re.match(r'<@&(\d+)>', text)
        if mention_match:
            role_id = int(mention_match.group(1))
            return guild.get_role(role_id)
        
        # Try role ID
        try:
            role_id = int(text)
            return guild.get_role(role_id)
        except ValueError:
            pass
        
        # Try role name
        text_lower = text.lower()
        for role in guild.roles:
            if role.name.lower() == text_lower:
                return role
        
        return None
    
    @staticmethod
    def channel_mention(text: str, guild: disnake.Guild) -> Optional[disnake.TextChannel]:
        """
        Parse a channel mention from text.
        
        Args:
            text: Text to parse
            guild: Guild to search in
            
        Returns:
            TextChannel if found, None otherwise
        """
        match = re.match(r'<#(\d+)>', text)
        if match:
            channel_id = int(match.group(1))
            channel = guild.get_channel(channel_id)
            if isinstance(channel, disnake.TextChannel):
                return channel
        return None
    
    @staticmethod
    def read_time(time_str: str, timezone: str = "UTC") -> datetime:
        """
        Parse a time string (relative or absolute).
        
        Args:
            time_str: Time string to parse
            timezone: Timezone to use (default: UTC)
            
        Returns:
            datetime object
        """
        time_str = time_str.strip()
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
        
        # Try relative time first (e.g., "5 hours", "next tuesday")
        # Simple relative parsing
        relative_patterns = [
            (r'(\d+)\s*h(?:ours?)?', lambda m: relativedelta(hours=int(m.group(1)))),
            (r'(\d+)\s*m(?:inutes?)?', lambda m: relativedelta(minutes=int(m.group(1)))),
            (r'(\d+)\s*d(?:ays?)?', lambda m: relativedelta(days=int(m.group(1)))),
            (r'(\d+)\s*w(?:eeks?)?', lambda m: relativedelta(weeks=int(m.group(1)))),
        ]
        
        delta = relativedelta()
        remaining = time_str.lower()
        for pattern, func in relative_patterns:
            match = re.search(pattern, remaining)
            if match:
                delta += func(match)
                remaining = remaining.replace(match.group(0), '').strip()
        
        if delta != relativedelta():
            result = now + delta
            return result
        
        # Try absolute time parsing
        try:
            parsed = date_parser.parse(time_str, default=now)
            if parsed.tzinfo is None:
                parsed = tz.localize(parsed)
            return parsed
        except:
            raise ValueError(f"Could not parse time: {time_str}")
    
    @staticmethod
    async def fetch_message(bot, text: str) -> Optional[disnake.Message]:
        """
        Fetch a message from a URL or message ID.
        
        Args:
            bot: Bot instance
            text: Message URL or ID
            
        Returns:
            Message if found, None otherwise
        """
        # Extract message ID from URL or use as-is
        message_id_match = re.search(r'/(\d+)/(\d+)/(\d+)', text)
        if message_id_match:
            guild_id = int(message_id_match.group(1))
            channel_id = int(message_id_match.group(2))
            msg_id = int(message_id_match.group(3))
        else:
            try:
                msg_id = int(text)
                # Need guild and channel context - this is simplified
                # In practice, you'd need to search across channels
                return None
            except ValueError:
                return None
        
        try:
            guild = bot.get_guild(guild_id)
            if not guild:
                return None
            channel = guild.get_channel(channel_id)
            if not channel:
                return None
            return await channel.fetch_message(msg_id)
        except:
            return None
    
    @staticmethod
    async def error(message, title: str, description: str):
        """Send an error embed."""
        embed = disnake.Embed(title=title, description=description, color=0xff0000)
        return await message.channel.send(embed=embed)
