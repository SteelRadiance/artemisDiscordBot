"""
Copyright 2025, Vijay Challa - Use of this source code follows the MIT license found in the LICENSE file.

PermissionFrontend Plugin - Frontend for managing permissions via commands

This plugin provides a command-line interface for managing bot permissions. It allows
checking permission status, adding permissions with various scopes (global, guild,
channel), and targeting different entities (users, roles, admins). Permissions can
be allowed or denied at different levels.

Commands:
    !permission check <permission> [user] - Check if a user has a permission
    !permission add <permission> [options] - Add a permission
    !perm - Alias for !permission
    !hpm - Alias for !permission

Features:
    - Permission checking with detailed results
    - Multi-scope permissions (global, guild, channel)
    - Multiple target types (users, roles, admins, bot owners)
    - Allow/deny permission control
    - Permission modification permission checks
    - Stores permissions persistently
"""

import logging
import disnake
from disnake import Embed

from artemis.plugin.base import PluginInterface, PluginHelper
from artemis.events.listener import EventListener
from artemis.permissions.resolver import Permission

logger = logging.getLogger("artemis.plugin.permissionfrontend")


class PermissionFrontend(PluginInterface, PluginHelper):
    """PermissionFrontend plugin for permission management."""
    
    # Permission setting types
    SETTING_GLOBAL = 0
    SETTING_GUILD = 1
    SETTING_CHANNEL = 2
    
    # Target types
    TARGET_GLOBAL = 0
    TARGET_ROLE = 1
    TARGET_USER = 2
    TARGET_GUILDOWNER = 3
    TARGET_BOTADMIN = 4
    
    @staticmethod
    def register(bot):
        """Register the plugin."""
        if PermissionFrontend.is_testing_client(bot):
            bot.log.info("Not adding permission frontend commands on testing.")
            return
        
        for cmd in ["permission", "perm", "hpm"]:
            bot.eventManager.add_listener(
                EventListener.new()
                .add_command(cmd)
                .set_callback(PermissionFrontend.hpm)
                .set_help(PermissionFrontend.get_help)
            )
    
    @staticmethod
    async def hpm(data):
        """Handle permission management command."""
        try:
            args = PermissionFrontend.split_command(data.message.content)
            if len(args) < 2:
                await data.message.reply(PermissionFrontend.get_help())
                return
            
            command = args[1].lower()
            
            if command == "check":
                await PermissionFrontend.check_perm(data, args[2:])
            elif command == "add":
                await PermissionFrontend.add_perm(data, args[2:])
            else:
                await data.message.reply(PermissionFrontend.get_help())
        except Exception as e:
            await PermissionFrontend.exception_handler(data.message, e)
    
    @staticmethod
    def get_help() -> str:
        """Get help text."""
        return (
            "**Usage**: `!permission <command> [options]`\n\n"
            "Commands:\n"
            "- `check <permission> [user]` - Check permission status\n"
            "- `add <permission> [options]` - Add permission\n"
            "  Options:\n"
            "  - `--deny` - Deny instead of allow\n"
            "  - `--scope <global|guild|channel>` - Set scope (default: guild)\n"
            "  - `--all` - Target all users\n"
            "  - `--role <role>` - Target role\n"
            "  - `--user <user>` - Target user\n"
            "  - `--admins` - Target guild admins\n"
            "  - `--evalusers` - Target bot owners"
        )
    
    @staticmethod
    async def check_perm(data, args: list):
        """Check permission."""
        try:
            if not args:
                await data.message.reply("Usage: `!permission check <permission> [user]`")
                return
            
            permission = args[0]
            user_text = args[1] if len(args) > 1 else "@self"
            
            if user_text == "@self":
                member = data.message.member
            else:
                member = await PermissionFrontend.parse_guild_user(data.guild, user_text)
            
            if not member:
                await data.message.reply("Unknown user.")
                return
            
            p = Permission(permission, data.artemis, False)
            p.add_message_context(data.message)
            result = await p.resolve()
            
            embed = Embed(
                title=f"Permission Check: {permission}",
                description=f"Permission `{permission}` for user {member.mention}",
                color=0x00ff00 if result else 0xff0000
            )
            embed.add_field(name="Result", value="**Allowed**" if result else "~~Denied~~", inline=False)
            
            await data.message.reply(embed=embed)
        except Exception as e:
            await PermissionFrontend.exception_handler(data.message, e)
    
    @staticmethod
    async def add_perm(data, args: list):
        """Add permission."""
        try:
            if not args:
                await data.message.reply("Usage: `!permission add <permission> [options]`")
                return
            
            permission = args[0]
            
            allow = True
            scope = "guild"
            target = "all"
            target_value = None
            
            i = 1
            while i < len(args):
                arg = args[i]
                if arg == "--deny":
                    allow = False
                elif arg == "--scope" and i + 1 < len(args):
                    scope = args[i + 1]
                    i += 1
                elif arg == "--all":
                    target = "all"
                elif arg == "--role" and i + 1 < len(args):
                    target = "role"
                    target_value = args[i + 1]
                    i += 1
                elif arg == "--user" and i + 1 < len(args):
                    target = "user"
                    target_value = args[i + 1]
                    i += 1
                elif arg == "--admins":
                    target = "admins"
                elif arg == "--evalusers":
                    target = "evalusers"
                i += 1
            
            if scope not in ["global", "guild", "channel"]:
                await data.message.reply("Invalid scope. Must be global, guild, or channel.")
                return
            
            if scope == "global":
                setting = PermissionFrontend.SETTING_GLOBAL
                setting_value = 0
            elif scope == "guild":
                setting = PermissionFrontend.SETTING_GUILD
                setting_value = data.guild.id
            else:  # channel
                setting = PermissionFrontend.SETTING_CHANNEL
                setting_value = data.message.channel.id
            
            target_type = PermissionFrontend.TARGET_GLOBAL
            if target == "role":
                role = PermissionFrontend.parse_role(data.guild, target_value)
                if not role:
                    await data.message.reply("Invalid role.")
                    return
                target_type = PermissionFrontend.TARGET_ROLE
                target_value = role.id
            elif target == "user":
                member = await PermissionFrontend.parse_guild_user(data.guild, target_value)
                if not member:
                    await data.message.reply("Invalid user.")
                    return
                target_type = PermissionFrontend.TARGET_USER
                target_value = member.id
            elif target == "admins":
                target_type = PermissionFrontend.TARGET_GUILDOWNER
                target_value = 0
            elif target == "evalusers":
                target_type = PermissionFrontend.TARGET_BOTADMIN
                target_value = 0
            
            can_modify = await PermissionFrontend.has_permission_permission(
                setting, target_type, data
            )
            
            if not can_modify:
                await data.message.reply("You don't have permission to modify this permission.")
                return
            
            perm_key = f"{permission}_{setting}_{setting_value}_{target_type}_{target_value}"
            await data.artemis.storage.set("permissions", perm_key, {
                "permission": permission,
                "allow": allow,
                "setting": setting,
                "setting_value": setting_value,
                "target_type": target_type,
                "target_value": target_value
            })
            
            scope_pretty = {
                "global": "Everywhere",
                "guild": f"Within this guild (`{data.guild.name}`)",
                "channel": f"Inside this channel ({data.message.channel.mention})"
            }[scope]
            
            target_pretty = {
                "all": "Anybody",
                "role": f"Users with the @{data.guild.get_role(target_value).name} role",
                "user": f"The user {data.guild.get_member(target_value).mention}",
                "admins": "Administrators",
                "evalusers": "Bot owners"
            }[target]
            
            await data.message.reply(
                f"The following permission has been added:\n"
                f"**{'Allow' if allow else 'Deny'}**: `{permission}`\n"
                f"**Scope**: {scope_pretty}\n"
                f"**Target**: {target_pretty}"
            )
        except Exception as e:
            await PermissionFrontend.exception_handler(data.message, e, True)
    
    @staticmethod
    async def has_permission_permission(setting: int, target: int, data) -> bool:
        """Check if user can modify permissions."""
        admin_ids = getattr(data.artemis.config, 'ADMIN_USER_IDS', [])
        is_admin = str(data.message.author.id) in admin_ids
        
        if setting == PermissionFrontend.SETTING_GLOBAL or target == PermissionFrontend.TARGET_BOTADMIN:
            return is_admin
        elif setting == PermissionFrontend.SETTING_GUILD:
            is_owner = data.message.member.id == data.guild.owner_id
            is_guild_admin = data.message.member.guild_permissions.administrator
            return is_admin or is_owner or is_guild_admin
        elif setting == PermissionFrontend.SETTING_CHANNEL:
            return data.message.member.permissions_in(data.message.channel).manage_channels or is_admin
        return False
