"""
Copyright 2025, Vijay Challa - Use of this source code follows the MIT license found in the LICENSE file.

Feedback Plugin - User feedback submission system
"""

import logging
import disnake
from typing import Optional

from artemis.plugin.base import PluginInterface, PluginHelper
from artemis.events.listener import EventListener

logger = logging.getLogger("artemis.plugin.feedback")


class Feedback(PluginInterface, PluginHelper):
    """Feedback plugin for user feedback submission."""
    
    @staticmethod
    def register(bot):
        """Register the plugin."""
        if Feedback.is_testing_client(bot):
            bot.log.info("Not adding feedback on testing.")
            return
        
        bot.eventManager.add_listener(
            EventListener.new()
            .add_command("feedback")
            .set_callback(Feedback.feedback_handler)
            .set_help("**Usage**: `!feedback <server> <text>` (DM) or `!feedback <channel_id>` (guild)\n\nSubmit feedback via DM or configure feedback channel in a guild.")
        )
    
    @staticmethod
    async def get_info(guild: disnake.Guild, bot=None) -> Optional[dict]:
        """Get feedback configuration for guild."""
        try:
            if bot and hasattr(bot, 'storage'):
                storage = bot.storage
            else:
                storage = guild._state._get_client().storage if hasattr(guild._state, '_get_client') else None
            
            if not storage:
                return None
            
            info = await storage.get("feedback", str(guild.id))
            return info if isinstance(info, dict) else None
        except Exception as e:
            logger.warning(f"Failed to get feedback info for guild {guild.id}: {e}")
            return None
    
    @staticmethod
    async def set_feedback_channel(guild: disnake.Guild, channel: disnake.TextChannel, bot=None):
        """Set feedback channel for guild."""
        try:
            if bot and hasattr(bot, 'storage'):
                storage = bot.storage
            else:
                storage = guild._state._get_client().storage if hasattr(guild._state, '_get_client') else None
            
            if not storage:
                return False
            
            await storage.set("feedback", str(guild.id), {
                "guild_id": str(guild.id),
                "channel_id": str(channel.id)
            })
            return True
        except Exception as e:
            logger.error(f"Failed to set feedback channel: {e}")
            return False
    
    @staticmethod
    async def get_staff_role_id(guild: disnake.Guild, bot=None) -> Optional[int]:
        try:
            if bot and hasattr(bot, 'storage'):
                storage = bot.storage
            else:
                storage = guild._state._get_client().storage if hasattr(guild._state, '_get_client') else None
            
            if not storage:
                return None
            
            info = await storage.get("feedback", str(guild.id))
            if info and isinstance(info, dict) and info.get("mod_role_id"):
                return int(info["mod_role_id"])
            
            info = await storage.get("talkingstick", str(guild.id))
            if info and isinstance(info, dict) and info.get("staff_role_id"):
                return int(info["staff_role_id"])
            
            return None
        except Exception:
            return None
    
    @staticmethod
    async def find_guild_by_name_or_id(bot, identifier: str) -> Optional[disnake.Guild]:
        try:
            guild_id = int(identifier)
            guild = bot.get_guild(guild_id)
            if guild:
                return guild
        except ValueError:
            pass
        
        identifier_lower = identifier.lower()
        for guild in bot.guilds:
            if guild.name.lower() == identifier_lower:
                return guild
            if identifier_lower in guild.name.lower():
                return guild
        
        return None
    
    @staticmethod
    async def feedback_handler(data):
        try:
            if data.message.guild is None:
                await Feedback.handle_dm_feedback(data)
            else:
                await Feedback.handle_guild_config(data)
        except Exception as e:
            await Feedback.exception_handler(data.message, e)
    
    @staticmethod
    async def handle_dm_feedback(data):
        try:
            args = Feedback.split_command(data.message.content)
            if len(args) < 3:
                await data.message.reply(
                    "**Usage**: `!feedback <server> <text>`\n\n"
                    "Submit feedback to a server. The server can be specified by name or ID.\n"
                    "Example: `!feedback MyServer This is my feedback`"
                )
                return
            
            server_identifier = args[1]
            feedback_text = " ".join(args[2:])
            
            if not feedback_text.strip():
                await data.message.reply("Please provide feedback text.")
                return
            
            guild = await Feedback.find_guild_by_name_or_id(data.artemis, server_identifier)
            if not guild:
                await data.message.reply(
                    f"Could not find server '{server_identifier}'. "
                    "Make sure the bot is in that server and you've spelled the name correctly, or use the server ID."
                )
                return
            
            info = await Feedback.get_info(guild, data.artemis)
            if not info or not info.get("channel_id"):
                await data.message.reply(
                    f"Feedback is not configured for '{guild.name}'. "
                    "An admin needs to set up a feedback channel using `!feedback <channel_id>` in that server."
                )
                return
            
            channel_id = int(info["channel_id"])
            channel = guild.get_channel(channel_id)
            if not channel:
                await data.message.reply(
                    f"The feedback channel for '{guild.name}' no longer exists. "
                    "An admin needs to reconfigure it."
                )
                return
            
            mod_role_id = await Feedback.get_staff_role_id(guild, data.artemis)
            mod_ping = ""
            if mod_role_id:
                mod_role = guild.get_role(mod_role_id)
                if mod_role:
                    mod_ping = f"{mod_role.mention} "
            
            await channel.send(
                f"{mod_ping}**New Feedback**\n\n{feedback_text}"
            )
            
            await data.message.reply(
                f"✅ Your feedback has been submitted to '{guild.name}'."
            )
        except Exception as e:
            await Feedback.exception_handler(data.message, e)
    
    @staticmethod
    async def handle_guild_config(data):
        try:
            admin_ids = getattr(data.artemis.config, 'ADMIN_USER_IDS', [])
            if str(data.message.author.id) not in admin_ids:
                await Feedback.unauthorized(data.message)
                return
            
            args = Feedback.split_command(data.message.content)
            if len(args) != 2:
                await data.message.reply(
                    "**Usage**: `!feedback <channel_id>`\n\n"
                    "Designate a channel for receiving feedback submissions.\n"
                    "Users can submit feedback via DM using `!feedback <server> <text>`."
                )
                return
            
            try:
                channel_id = int(args[1])
                channel = data.message.guild.get_channel(channel_id)
                if not channel or not isinstance(channel, disnake.TextChannel):
                    await data.message.reply("Invalid channel ID or channel not found.")
                    return
                
                await Feedback.set_feedback_channel(data.message.guild, channel, data.artemis)
                await data.message.reply(
                    f"✅ {channel.mention} has been set as the feedback channel for this server."
                )
            except ValueError:
                await data.message.reply("Invalid channel ID. Please provide a numeric channel ID.")
        except Exception as e:
            await Feedback.exception_handler(data.message, e)
