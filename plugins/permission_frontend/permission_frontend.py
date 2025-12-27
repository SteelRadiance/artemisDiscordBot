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
            elif command == "list":
                await PermissionFrontend.list_perm(data)
            elif command == "listall":
                await PermissionFrontend.listall_perm(data)
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
            "- `list` - List all your permissions\n"
            "- `listall` - List all configured permissions in the system\n"
            "- `add <permission> [options]` - Add permission\n"
            "  Options:\n"
            "  - `--deny` - Deny instead of allow\n"
            "  - `--scope <global|guild|channel>` - Set scope (default: guild)\n"
            "  - `--all` - Target all users\n"
            "  - `--role <role>` - Target role\n"
            "  - `--user <user>` - Target user\n"
            "  - `--admins` - Target guild admins\n"
            "  - `--evalusers` - Target bot owners\n\n"
            "**Examples**:\n"
            "- `!permission list` - List all your permissions\n"
            "- `!permission listall` - List all configured permissions in the system\n"
            "- `!permission check p.moderation.state` - Check your own permission\n"
            "- `!permission check p.auditlog.view @user` - Check permission for another user\n"
            "- `!permission add p.auditlog.view --scope guild --all` - Allow all users to view audit logs\n"
            "- `!permission add p.roles.toggle --role Moderator` - Allow Moderator role to toggle roles\n"
            "- `!permission add p.moderation.state --user @user` - Allow a specific user to post mod statements\n"
            "- `!permission add p.roles.bind --deny --role Member` - Deny members from binding roles\n"
            "- `!permission add p.auditlog.view --scope channel --all` - Allow audit log viewing in this channel only\n"
            "- `!permission add p.moderation.state --scope guild --admins` - Allow guild admins to post mod statements"
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
                member = data.guild.get_member(data.message.author.id) if data.guild else None
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
    async def list_perm(data):
        """List all permissions for the calling user."""
        try:
            member = data.guild.get_member(data.message.author.id) if data.guild else None
            if not member:
                await data.message.reply("Cannot determine user information.")
                return
            
            # Check if user is bot admin
            admin_ids = getattr(data.artemis.config, 'ADMIN_USER_IDS', [])
            is_admin = str(data.message.author.id) in admin_ids
            
            # Get all permissions from storage
            all_perms = await data.artemis.storage.get_all("permissions")
            
            # Filter permissions that apply to this user
            user_perms = {}
            
            for perm_key, perm_data in all_perms.items():
                if not isinstance(perm_data, dict):
                    continue
                
                permission = perm_data.get("permission")
                allow = perm_data.get("allow", True)
                setting = perm_data.get("setting")
                setting_value = perm_data.get("setting_value")
                target_type = perm_data.get("target_type")
                target_value = perm_data.get("target_value")
                
                # Check if scope applies
                scope_applies = False
                if setting == PermissionFrontend.SETTING_GLOBAL:
                    scope_applies = True
                elif setting == PermissionFrontend.SETTING_GUILD:
                    scope_applies = (data.guild and setting_value == data.guild.id)
                elif setting == PermissionFrontend.SETTING_CHANNEL:
                    scope_applies = (data.message.channel and setting_value == data.message.channel.id)
                
                if not scope_applies:
                    continue
                
                # Check if target applies
                target_applies = False
                if target_type == PermissionFrontend.TARGET_GLOBAL:
                    target_applies = True
                elif target_type == PermissionFrontend.TARGET_ROLE:
                    if data.guild and target_value:
                        role = data.guild.get_role(target_value)
                        target_applies = (role and role in member.roles)
                elif target_type == PermissionFrontend.TARGET_USER:
                    target_applies = (target_value == member.id)
                elif target_type == PermissionFrontend.TARGET_GUILDOWNER:
                    target_applies = (data.guild and member.id == data.guild.owner_id) or member.guild_permissions.administrator
                elif target_type == PermissionFrontend.TARGET_BOTADMIN:
                    target_applies = is_admin
                
                if target_applies:
                    # Store permission with its allow/deny status
                    # If permission already exists, prioritize deny over allow (deny takes precedence)
                    if permission not in user_perms:
                        user_perms[permission] = allow
                    elif not allow:
                        # Deny takes precedence over allow
                        user_perms[permission] = False
            
            # If user is bot admin, they have all permissions
            if is_admin:
                embed = Embed(
                    title="Your Permissions",
                    description=f"**Bot Admin** - You have access to all permissions.",
                    color=0x00ff00
                )
                embed.add_field(
                    name="Note",
                    value="As a bot admin, you bypass all permission checks.",
                    inline=False
                )
            else:
                allowed_perms = [perm for perm, allowed in user_perms.items() if allowed]
                denied_perms = [perm for perm, allowed in user_perms.items() if not allowed]
                
                embed = Embed(
                    title="Your Permissions",
                    description=f"Permissions for {member.mention}",
                    color=0x0099ff
                )
                
                if allowed_perms:
                    # Split into chunks if too long
                    allowed_text = "\n".join(f"✅ `{perm}`" for perm in sorted(allowed_perms))
                    if len(allowed_text) > 1024:
                        # Split into multiple fields if needed
                        chunk_size = 1000
                        chunks = [allowed_text[i:i+chunk_size] for i in range(0, len(allowed_text), chunk_size)]
                        for i, chunk in enumerate(chunks[:5]):  # Limit to 5 fields
                            embed.add_field(
                                name=f"Allowed Permissions{' (cont.)' if i > 0 else ''}",
                                value=chunk,
                                inline=False
                            )
                    else:
                        embed.add_field(
                            name="Allowed Permissions",
                            value=allowed_text,
                            inline=False
                        )
                
                if denied_perms:
                    denied_text = "\n".join(f"❌ `{perm}`" for perm in sorted(denied_perms))
                    if len(denied_text) > 1024:
                        chunk_size = 1000
                        chunks = [denied_text[i:i+chunk_size] for i in range(0, len(denied_text), chunk_size)]
                        for i, chunk in enumerate(chunks[:5]):
                            embed.add_field(
                                name=f"Denied Permissions{' (cont.)' if i > 0 else ''}",
                                value=chunk,
                                inline=False
                            )
                    else:
                        embed.add_field(
                            name="Denied Permissions",
                            value=denied_text,
                            inline=False
                        )
                
                if not allowed_perms and not denied_perms:
                    embed.add_field(
                        name="No Permissions Found",
                        value="You don't have any custom permissions configured.",
                        inline=False
                    )
            
            await data.message.reply(embed=embed)
        except Exception as e:
            await PermissionFrontend.exception_handler(data.message, e)
    
    @staticmethod
    async def listall_perm(data):
        """List all permissions stored in the system."""
        try:
            # Get all permissions from storage
            all_perms = await data.artemis.storage.get_all("permissions")
            
            if not all_perms:
                embed = Embed(
                    title="All Permissions",
                    description="No permissions are currently configured in the system.",
                    color=0x0099ff
                )
                await data.message.reply(embed=embed)
                return
            
            # Group permissions by permission name
            perm_groups = {}
            
            for perm_key, perm_data in all_perms.items():
                if not isinstance(perm_data, dict):
                    continue
                
                permission = perm_data.get("permission")
                allow = perm_data.get("allow", True)
                setting = perm_data.get("setting")
                setting_value = perm_data.get("setting_value")
                target_type = perm_data.get("target_type")
                target_value = perm_data.get("target_value")
                
                if permission not in perm_groups:
                    perm_groups[permission] = []
                
                # Format scope
                scope_str = ""
                if setting == PermissionFrontend.SETTING_GLOBAL:
                    scope_str = "🌐 Global"
                elif setting == PermissionFrontend.SETTING_GUILD:
                    if data.guild and setting_value:
                        guild_obj = data.guild if setting_value == data.guild.id else None
                        if guild_obj:
                            scope_str = f"🏠 Guild: {guild_obj.name}"
                        else:
                            scope_str = f"🏠 Guild: {setting_value}"
                    else:
                        scope_str = f"🏠 Guild: {setting_value}"
                elif setting == PermissionFrontend.SETTING_CHANNEL:
                    if data.message.channel and setting_value == data.message.channel.id:
                        scope_str = f"📺 Channel: {data.message.channel.mention}"
                    else:
                        scope_str = f"📺 Channel: {setting_value}"
                
                # Format target
                target_str = ""
                if target_type == PermissionFrontend.TARGET_GLOBAL:
                    target_str = "👥 All users"
                elif target_type == PermissionFrontend.TARGET_ROLE:
                    if data.guild and target_value:
                        role = data.guild.get_role(target_value)
                        if role:
                            target_str = f"🎭 Role: @{role.name}"
                        else:
                            target_str = f"🎭 Role: {target_value}"
                    else:
                        target_str = f"🎭 Role: {target_value}"
                elif target_type == PermissionFrontend.TARGET_USER:
                    if data.guild and target_value:
                        member = data.guild.get_member(target_value)
                        if member:
                            target_str = f"👤 User: {member.mention}"
                        else:
                            target_str = f"👤 User: {target_value}"
                    else:
                        target_str = f"👤 User: {target_value}"
                elif target_type == PermissionFrontend.TARGET_GUILDOWNER:
                    target_str = "👑 Guild admins"
                elif target_type == PermissionFrontend.TARGET_BOTADMIN:
                    target_str = "🤖 Bot owners"
                
                perm_groups[permission].append({
                    "allow": allow,
                    "scope": scope_str,
                    "target": target_str
                })
            
            # Create embed with all permissions
            embed = Embed(
                title="All Configured Permissions",
                description=f"Total: {len(perm_groups)} unique permission(s), {len(all_perms)} rule(s)",
                color=0x0099ff
            )
            
            # Sort permissions alphabetically
            sorted_perms = sorted(perm_groups.items())
            
            # Limit to 25 permissions to stay within Discord embed limits
            max_perms = 25
            display_perms = sorted_perms[:max_perms]
            
            # Build permission list
            for permission, rules in display_perms:
                rules_text = []
                for rule in rules:
                    status = "✅ Allow" if rule["allow"] else "❌ Deny"
                    rules_text.append(f"{status} | {rule['scope']} | {rule['target']}")
                
                perm_text = "\n".join(rules_text)
                
                # Truncate if too long
                if len(perm_text) > 1024:
                    perm_text = perm_text[:1020] + "..."
                
                embed.add_field(
                    name=f"`{permission}`",
                    value=perm_text or "No rules",
                    inline=False
                )
            
            # Add footer if there are more permissions
            if len(sorted_perms) > max_perms:
                embed.set_footer(text=f"Showing first {max_perms} of {len(sorted_perms)} permissions")
            
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
            member = data.guild.get_member(data.message.author.id) if data.guild else None
            if not member:
                return False
            is_owner = member.id == data.guild.owner_id
            is_guild_admin = member.guild_permissions.administrator
            return is_admin or is_owner or is_guild_admin
        elif setting == PermissionFrontend.SETTING_CHANNEL:
            member = data.guild.get_member(data.message.author.id) if data.guild else None
            if not member:
                return False
            return member.permissions_in(data.message.channel).manage_channels or is_admin
        return False
