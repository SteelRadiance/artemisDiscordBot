"""
Copyright 2025, Vijay Challa - Use of this source code follows the MIT license found in the LICENSE file.

Role Plugin - Role self-management system

This plugin allows users to self-assign roles through commands. Administrators can
bind roles to be self-assignable, and users can toggle them on/off.

Commands:
    !role [role_name] - Toggle a role (or list available roles)
    !roles - List all self-assignable roles
    !bindrole <role_id> - Make a role self-assignable (admin)

Features:
    - Self-service role assignment
    - Fuzzy matching for role names
    - Per-guild role binding
    - Permission-based access control
"""

import logging
import json
import aiofiles
import aiofiles.os
from pathlib import Path
from typing import Dict, Any
import disnake
from disnake import Embed
from difflib import SequenceMatcher

from artemis.plugin.base import PluginInterface, PluginHelper
from artemis.events.listener import EventListener
from artemis.permissions.resolver import Permission

logger = logging.getLogger("artemis.plugin.role")


class Role(PluginInterface, PluginHelper):
    """Role plugin for role self-management."""
    
    @staticmethod
    def _get_roles_file() -> Path:
        """Get the roles file path in logs directory."""
        return Path("logs") / "roles.json"
    
    @staticmethod
    async def _load_roles() -> Dict[str, Any]:
        """Load all roles from the roles file."""
        roles_file = Role._get_roles_file()
        try:
            if await aiofiles.os.path.exists(roles_file):
                async with aiofiles.open(roles_file, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    if content.strip():
                        return json.loads(content)
            return {}
        except Exception as e:
            logger.error(f"Error loading roles: {e}")
            return {}
    
    @staticmethod
    async def _save_roles(roles_data: Dict[str, Any]) -> bool:
        """Save all roles to the roles file."""
        roles_file = Role._get_roles_file()
        try:
            # Ensure logs directory exists
            await aiofiles.os.makedirs(roles_file.parent, exist_ok=True)
            
            async with aiofiles.open(roles_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(roles_data, indent=2, ensure_ascii=False))
            return True
        except Exception as e:
            logger.error(f"Error saving roles: {e}")
            return False
    
    @staticmethod
    def register(bot):
        """Register the plugin."""
        if Role.is_testing_client(bot):
            bot.log.info("Not adding role commands on testing.")
            return
        
        role_help = "**Usage**: `!role [role_name]` or `!roles`\n\nToggle a self-assignable role on/off. If no role is specified or you use `!roles`, lists all available self-assignable roles. Requires permission `p.roles.toggle`."
        for cmd in ["role", "roles"]:
            bot.eventManager.add_listener(
                EventListener.new()
                .add_command(cmd)
                .set_callback(Role.role_entry)
                .set_help(role_help)
            )
        
        bot.eventManager.add_listener(
            EventListener.new()
            .add_command("bindrole")
            .set_callback(Role.role_bind)
            .set_help("**Usage**: `!bindrole <role_id>`\n\nMake a role self-assignable by users. Requires admin permissions.")
        )
    
    @staticmethod
    async def get_valid_options(member: disnake.Member) -> list:
        """Get valid role options for a member."""
        try:
            roles_data = await Role._load_roles()
            valid_role_ids = []
            for key, value in roles_data.items():
                if isinstance(value, dict) and value.get("guild_id") == str(member.guild.id):
                    valid_role_ids.append(int(key))
            
            return [role for role in member.guild.roles if role.id in valid_role_ids]
        except Exception as e:
            logger.error(f"Error getting valid role options: {e}")
            return []
    
    @staticmethod
    async def role_entry(data):
        """Handle role command."""
        try:
            if not data.guild:
                await data.message.reply("This command can only be used in a server.")
                return
            
            p = Permission("p.roles.toggle", data.artemis, True)
            p.add_message_context(data.message)
            if not await p.resolve():
                await p.send_unauthorized_message(data.message.channel)
                return
            
            args = Role.split_command(data.message.content)
            if len(args) < 2:
                await Role.give_list(data)
                return
            
            role_name = Role.arg_substr(data.message.content, 1).strip()
            if role_name.lower() in ["landlord", "landlords"]:
                # Special case - send landlords.jpg if it exists
                await data.message.reply("Landlords feature not implemented")
                return
            
            await Role.toggle_role(data, role_name)
        except Exception as e:
            await Role.exception_handler(data.message, e, True)
    
    @staticmethod
    async def give_list(data):
        """Show list of available roles."""
        try:
            if not data.guild:
                await data.message.reply("This command can only be used in a server.")
                return
            
            p = Permission("p.roles.list", data.artemis, True)
            p.add_message_context(data.message)
            if not await p.resolve():
                await p.send_unauthorized_message(data.message.channel)
                return
            
            # Get member from author - message.member might not always be available
            member = data.guild.get_member(data.message.author.id)
            if not member:
                member = data.message.author if isinstance(data.message.author, disnake.Member) else None
            
            if not member:
                await data.message.reply("Could not find member information.")
                return
            
            valid_roles = await Role.get_valid_options(member)
            
            if not valid_roles:
                await data.message.reply("No roles found! Tell the server owner to bug my owner!")
                return
            
            embed = Embed(
                title=f"Roles List - {data.guild.name}",
                description="Use `!role ROLE NAME` to toggle a role.\nDo **not** use an `@`!",
                color=member.color if member.color.value else 0x00ff00
            )
            
            roles_text = "\n".join([f"{role.mention} (`!role {role.name}`)" for role in sorted(valid_roles, key=lambda r: r.position, reverse=True)])
            
            if len(roles_text) > 1024:
                chunks = [roles_text[i:i+1024] for i in range(0, len(roles_text), 1024)]
                for i, chunk in enumerate(chunks):
                    embed.add_field(
                        name="Roles" if i == 0 else "Roles (cont.)",
                        value=chunk,
                        inline=False
                    )
            else:
                embed.add_field(name="Roles", value=roles_text, inline=False)
            
            await data.message.reply(embed=embed)
        except Exception as e:
            await Role.exception_handler(data.message, e, True)
    
    @staticmethod
    async def toggle_role(data, role_name: str):
        """Toggle a role for a member."""
        try:
            if not data.guild:
                await data.message.reply("This command can only be used in a server.")
                return
            
            # Get member from author - message.member might not always be available
            member = data.guild.get_member(data.message.author.id)
            if not member:
                member = data.message.author if isinstance(data.message.author, disnake.Member) else None
            
            if not member:
                await data.message.reply("Could not find member information.")
                return
            
            valid_roles = await Role.get_valid_options(member)
            
            role = None
            for r in valid_roles:
                if r.name.lower() == role_name.lower():
                    role = r
                    break
            
            if not role:
                # Try similarity matching
                best_match = None
                best_score = 0
                for r in valid_roles:
                    score = SequenceMatcher(None, role_name.lower(), r.name.lower()).ratio()
                    if score > best_score:
                        best_score = score
                        best_match = r
                
                if best_match and best_score > 0.5:
                    await data.message.reply(f"`{role_name}` not found! Did you mean `!role {best_match.name}`?")
                else:
                    await data.message.reply("No roles found! Tell the server owner to bug my owner!")
                return
            
            # Toggle role
            if role in member.roles:
                await member.remove_roles(role, reason="Role toggle via bot")
                await data.message.reply(f"Role removed: {role.name}")
            else:
                await member.add_roles(role, reason="Role toggle via bot")
                await data.message.reply(f"Role added: {role.name}")
        except Exception as e:
            await Role.exception_handler(data.message, e, True)
    
    @staticmethod
    async def role_bind(data):
        """Bind a role to be self-assignable."""
        try:
            if not data.guild:
                await data.message.reply("This command can only be used in a server.")
                return
            
            p = Permission("p.roles.bind", data.artemis, False)
            p.add_message_context(data.message)
            if not await p.resolve():
                await p.send_unauthorized_message(data.message.channel)
                return
            
            args = Role.split_command(data.message.content)
            if len(args) < 2:
                await data.message.reply("Usage: `!bindrole ROLE_ID` or `!bindrole @Role`")
                return
            
            role_id = None
            # Try to parse as integer first
            try:
                role_id = int(args[1])
            except ValueError:
                pass
            
            # If not an integer, try to parse as role mention or name
            if not role_id:
                role = Role.parse_role(data.guild, args[1])
                if not role:
                    await data.message.reply("Role not found. Use a role ID, mention (@Role), or role name.")
                    return
                role_id = role.id
            
            role = data.guild.get_role(role_id)
            if not role:
                await data.message.reply("Role not found.")
                return
            
            if role.id == data.guild.id:
                await data.message.reply("`@everyone` is not a bindable role!")
                return
            
            # Store role
            try:
                roles_data = await Role._load_roles()
                roles_data[str(role_id)] = {
                    "role_id": str(role_id),
                    "guild_id": str(data.guild.id)
                }
                if await Role._save_roles(roles_data):
                    await data.message.reply(f"✅ Role `{role.name}` has been added to self-assignable roles!")
                else:
                    await data.message.reply("❌ Failed to save role binding. Please try again.")
            except Exception as e:
                logger.error(f"Error storing role binding: {e}")
                await Role.exception_handler(data.message, e, True)
        except ValueError as e:
            await data.message.reply("Invalid role ID. Please provide a valid role ID, mention, or name.")
        except Exception as e:
            await Role.exception_handler(data.message, e, True)
    
