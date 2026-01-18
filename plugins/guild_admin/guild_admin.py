"""
Copyright 2025, Vijay Challa - Use of this source code follows the MIT license found in the LICENSE file.

GuildAdmin Plugin - Guild admin and moderator management

This plugin provides commands for managing guild administrators and moderators.
Guild admins can add/remove moderators and transfer admin privileges.
Super admin can set guild admins when a guild has no admin.

Commands:
    !admin addmod <user> - Add moderator (guild admin only)
    !admin removemod <user> - Remove moderator (guild admin only)
    !admin transfer <user> - Transfer admin to moderator, becomes mod (guild admin only)
    !admin setadmin <user> - Set guild admin (super_admin only, works only when guild has no admin)
    !admin list - List current admin and moderators
    !admin help - Show command help
"""

import logging
import disnake
from disnake import Embed

from artemis.plugin.base import PluginInterface, PluginHelper
from artemis.events.listener import EventListener
from artemis.permissions.guild_permissions import (
    is_super_admin,
    is_guild_admin,
    get_guild_permissions,
    set_guild_admin,
    add_guild_moderator,
    remove_guild_moderator,
    transfer_guild_admin,
    has_admin_access
)

logger = logging.getLogger("artemis.plugin.guildadmin")


class GuildAdmin(PluginInterface, PluginHelper):
    """GuildAdmin plugin for managing guild permissions."""
    
    @staticmethod
    def register(bot):
        """Register the plugin."""
        if GuildAdmin.is_testing_client(bot):
            bot.log.info("Not adding guild admin commands on testing.")
            return
        
        bot.eventManager.add_listener(
            EventListener.new()
            .add_command("admin")
            .set_callback(GuildAdmin.admin_handler)
            .set_help(GuildAdmin.get_help)
        )
    
    @staticmethod
    def get_help() -> str:
        """Get help text."""
        return (
            "**Usage**: `!admin <command>`\n\n"
            "Commands:\n"
            "- `addmod <user>` - Add moderator (guild admin only)\n"
            "- `removemod <user>` - Remove moderator (guild admin only)\n"
            "- `transfer <user>` - Transfer admin to moderator, becomes mod (guild admin only)\n"
            "- `setadmin <user>` - Set guild admin (super_admin only, works only when guild has no admin)\n"
            "- `list` - List current admin and moderators\n"
            "- `help` - Show this help message"
        )
    
    @staticmethod
    async def admin_handler(data):
        """Handle admin command."""
        try:
            if not data.guild:
                await data.message.reply("This command can only be used in a server.")
                return
            
            args = GuildAdmin.split_command(data.message.content)
            if len(args) < 2:
                await data.message.reply(GuildAdmin.get_help())
                return
            
            command = args[1].lower()
            
            if command == "addmod":
                await GuildAdmin.add_mod(data, args[2:])
            elif command == "removemod":
                await GuildAdmin.remove_mod(data, args[2:])
            elif command == "transfer":
                await GuildAdmin.transfer_admin(data, args[2:])
            elif command == "setadmin":
                await GuildAdmin.set_admin(data, args[2:])
            elif command == "list":
                await GuildAdmin.list_permissions(data)
            elif command == "help":
                await data.message.reply(GuildAdmin.get_help())
            else:
                await data.message.reply(GuildAdmin.get_help())
        except Exception as e:
            await GuildAdmin.exception_handler(data.message, e)
    
    @staticmethod
    async def add_mod(data, args: list):
        """Add moderator."""
        try:
            # Check if user is guild admin
            user_id = str(data.message.author.id)
            guild_id = str(data.guild.id)
            
            if not await is_guild_admin(user_id, guild_id, data.artemis):
                await GuildAdmin.unauthorized(data.message)
                return
            
            if not args:
                await data.message.reply("Usage: `!admin addmod <user>`")
                return
            
            user_text = " ".join(args)
            member = await GuildAdmin.parse_guild_user(data.guild, user_text)
            
            if not member:
                await data.message.reply("Could not find that user.")
                return
            
            mod_id = str(member.id)
            
            # Check if already admin or moderator
            if await is_guild_admin(mod_id, guild_id, data.artemis):
                await data.message.reply(f"{member.mention} is already the guild admin.")
                return
            
            if await add_guild_moderator(guild_id, mod_id, data.artemis):
                await data.message.reply(f"{member.mention} has been added as a moderator.")
            else:
                await data.message.reply("Failed to add moderator.")
        except Exception as e:
            await GuildAdmin.exception_handler(data.message, e)
    
    @staticmethod
    async def remove_mod(data, args: list):
        """Remove moderator."""
        try:
            # Check if user is guild admin
            user_id = str(data.message.author.id)
            guild_id = str(data.guild.id)
            
            if not await is_guild_admin(user_id, guild_id, data.artemis):
                await GuildAdmin.unauthorized(data.message)
                return
            
            if not args:
                await data.message.reply("Usage: `!admin removemod <user>`")
                return
            
            user_text = " ".join(args)
            member = await GuildAdmin.parse_guild_user(data.guild, user_text)
            
            if not member:
                await data.message.reply("Could not find that user.")
                return
            
            mod_id = str(member.id)
            
            if await remove_guild_moderator(guild_id, mod_id, data.artemis):
                await data.message.reply(f"{member.mention} has been removed as a moderator.")
            else:
                await data.message.reply(f"{member.mention} is not a moderator, or failed to remove.")
        except Exception as e:
            await GuildAdmin.exception_handler(data.message, e)
    
    @staticmethod
    async def transfer_admin(data, args: list):
        """Transfer admin to moderator."""
        try:
            # Check if user is guild admin
            user_id = str(data.message.author.id)
            guild_id = str(data.guild.id)
            
            if not await is_guild_admin(user_id, guild_id, data.artemis):
                await GuildAdmin.unauthorized(data.message)
                return
            
            if not args:
                await data.message.reply("Usage: `!admin transfer <user>`")
                return
            
            user_text = " ".join(args)
            member = await GuildAdmin.parse_guild_user(data.guild, user_text)
            
            if not member:
                await data.message.reply("Could not find that user.")
                return
            
            new_admin_id = str(member.id)
            
            # Verify the new admin is a moderator
            from artemis.permissions.guild_permissions import is_guild_moderator
            if not await is_guild_moderator(new_admin_id, guild_id, data.artemis):
                await data.message.reply(f"{member.mention} is not a moderator. Please add them as a moderator first.")
                return
            
            if await transfer_guild_admin(guild_id, new_admin_id, user_id, data.artemis):
                await data.message.reply(
                    f"Admin privileges have been transferred to {member.mention}. "
                    f"{data.message.author.mention} is now a moderator."
                )
            else:
                await data.message.reply("Failed to transfer admin privileges.")
        except Exception as e:
            await GuildAdmin.exception_handler(data.message, e)
    
    @staticmethod
    async def set_admin(data, args: list):
        """Set guild admin (super_admin only, works only when guild has no admin)."""
        try:
            # Check if user is super admin
            user_id = str(data.message.author.id)
            if not is_super_admin(user_id, data.artemis.config):
                await GuildAdmin.unauthorized(data.message)
                return
            
            if not args:
                await data.message.reply("Usage: `!admin setadmin <user>`")
                return
            
            user_text = " ".join(args)
            member = await GuildAdmin.parse_guild_user(data.guild, user_text)
            
            if not member:
                await data.message.reply("Could not find that user.")
                return
            
            guild_id = str(data.guild.id)
            
            # Check if guild already has an admin
            permissions = await get_guild_permissions(guild_id, data.artemis)
            if permissions and permissions.get("admin_id"):
                await data.message.reply(
                    f"This guild already has an admin. "
                    f"Only the current admin can transfer privileges using `!admin transfer`."
                )
                return
            
            new_admin_id = str(member.id)
            
            if await set_guild_admin(guild_id, new_admin_id, data.artemis):
                await data.message.reply(f"{member.mention} has been set as the guild admin.")
            else:
                await data.message.reply("Failed to set guild admin.")
        except Exception as e:
            await GuildAdmin.exception_handler(data.message, e)
    
    @staticmethod
    async def list_permissions(data):
        """List current admin and moderators."""
        try:
            guild_id = str(data.guild.id)
            permissions = await get_guild_permissions(guild_id, data.artemis)
            
            if not permissions or not permissions.get("admin_id"):
                await data.message.reply("This guild has no admin configured.")
                return
            
            admin_id = permissions.get("admin_id")
            mods = permissions.get("mods", {})
            
            # Get admin member
            admin_member = data.guild.get_member(int(admin_id)) if admin_id else None
            admin_text = admin_member.mention if admin_member else f"<@{admin_id}> (not in server)"
            
            # Get moderator members
            moderator_list = []
            for mod_id in mods.keys():
                try:
                    mod_member = data.guild.get_member(int(mod_id))
                    if mod_member:
                        moderator_list.append(mod_member.mention)
                    else:
                        moderator_list.append(f"<@{mod_id}> (not in server)")
                except (ValueError, KeyError):
                    continue
            
            response = f"**Guild Admin:** {admin_text}\n"
            
            if moderator_list:
                response += f"**Moderators ({len(moderator_list)}):**\n"
                for mod_text in moderator_list:
                    response += f"- {mod_text}\n"
            else:
                response += "**Moderators:** None\n"
            
            await data.message.reply(response)
        except Exception as e:
            await GuildAdmin.exception_handler(data.message, e)
