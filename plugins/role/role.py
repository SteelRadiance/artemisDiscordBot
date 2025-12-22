"""
Role Plugin - Role self-management system
"""

import logging
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
    def register(bot):
        """Register the plugin."""
        if Role.is_testing_client(bot):
            bot.log.info("Not adding role commands on testing.")
            return
        
        bot.eventManager.addEventListener(
            EventListener.new()
            .add_command("role")
            .add_command("roles")
            .set_callback(Role.role_entry)
        )
        
        bot.eventManager.addEventListener(
            EventListener.new()
            .add_command("bindrole")
            .set_callback(Role.role_bind)
        )
        
        bot.eventManager.addEventListener(
            EventListener.new()
            .add_command("inheritrole")
            .set_callback(Role.role_inherit)
        )
        
        # Periodic task for inheritance
        bot.eventManager.addEventListener(
            EventListener.new()
            .set_periodic(10)
            .set_callback(Role.poll_inheritance)
        )
    
    @staticmethod
    async def get_valid_options(member: disnake.Member) -> list:
        """Get valid role options for a member."""
        # Get roles from storage
        try:
            storage = member.guild._state._get_client().storage if hasattr(member.guild._state, '_get_client') else None
            if not storage:
                return []
            
            roles_data = await storage.get_all("roles")
            valid_role_ids = []
            for key, value in roles_data.items():
                if isinstance(value, dict) and value.get("guild_id") == str(member.guild.id):
                    valid_role_ids.append(int(key))
            
            return [role for role in member.guild.roles if role.id in valid_role_ids]
        except:
            return []
    
    @staticmethod
    async def role_entry(data):
        """Handle role command."""
        try:
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
            p = Permission("p.roles.list", data.artemis, True)
            p.add_message_context(data.message)
            if not await p.resolve():
                await p.send_unauthorized_message(data.message.channel)
                return
            
            valid_roles = await Role.get_valid_options(data.message.member)
            
            if not valid_roles:
                await data.message.reply("No roles found! Tell the server owner to bug my owner!")
                return
            
            embed = Embed(
                title=f"Roles List - {data.guild.name}",
                description="Use `!role ROLE NAME` to toggle a role.\nDo **not** use an `@`!",
                color=data.message.member.color
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
            valid_roles = await Role.get_valid_options(data.message.member)
            
            # Find exact match
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
            if role in data.message.member.roles:
                await data.message.member.remove_roles(role, reason="Role toggle via bot")
                await data.message.reply(f"Role removed: {role.name}")
            else:
                await data.message.member.add_roles(role, reason="Role toggle via bot")
                await data.message.reply(f"Role added: {role.name}")
        except Exception as e:
            await Role.exception_handler(data.message, e, True)
    
    @staticmethod
    async def role_bind(data):
        """Bind a role to be self-assignable."""
        try:
            p = Permission("p.roles.bind", data.artemis, False)
            p.add_message_context(data.message)
            if not await p.resolve():
                await p.send_unauthorized_message(data.message.channel)
                return
            
            args = Role.split_command(data.message.content)
            if len(args) < 2:
                await Role.error(data.message, "Error", "Usage: `!bindrole ROLE_ID`.")
                return
            
            role_id = int(args[1]) if args[1].isdigit() else None
            if not role_id:
                role = Role.parse_role(data.guild, args[1])
                if not role:
                    await Role.error(data.message, "Error", "Usage: `!bindrole ROLE_ID`.")
                    return
                role_id = role.id
            
            role = data.guild.get_role(role_id)
            if not role:
                await Role.error(data.message, "Error", "Role not found.")
                return
            
            if role.id == data.guild.id:
                await Role.error(data.message, "Error", "`@everyone` is not a bindable role!")
                return
            
            # Store role
            try:
                await data.artemis.storage.set("roles", str(role_id), {
                    "role_id": str(role_id),
                    "guild_id": str(data.guild.id)
                })
                await data.message.reply(f"Role added to server bindings: {role.name}")
            except Exception as e:
                await Role.exception_handler(data.message, e, True)
        except Exception as e:
            await Role.exception_handler(data.message, e, True)
    
    @staticmethod
    async def role_inherit(data):
        """Set up role inheritance."""
        try:
            p = Permission("p.roles.bind", data.artemis, False)
            p.add_message_context(data.message)
            if not await p.resolve():
                await p.send_unauthorized_message(data.message.channel)
                return
            
            args = Role.split_command(data.message.content)
            if len(args) < 3:
                await Role.error(data.message, "Error", "Usage: `!inheritrole SOURCE_ROLE_ID DEST_ROLE_ID`.")
                return
            
            source_id = int(args[1]) if args[1].isdigit() else None
            dest_id = int(args[2]) if args[2].isdigit() else None
            
            if not source_id or not dest_id:
                await Role.error(data.message, "Error", "Usage: `!inheritrole SOURCE_ROLE_ID DEST_ROLE_ID`.")
                return
            
            source = data.guild.get_role(source_id)
            dest = data.guild.get_role(dest_id)
            
            if not source or not dest:
                await Role.error(data.message, "Error", "One or both roles not found.")
                return
            
            if source.id == data.guild.id or dest.id == data.guild.id:
                await Role.error(data.message, "Error", "`@everyone` is not a bindable role!")
                return
            
            # Store inheritance
            try:
                await data.artemis.storage.set("roles_inherit", f"{data.guild.id}_{source_id}_{dest_id}", {
                    "guild_id": str(data.guild.id),
                    "source_role_id": str(source_id),
                    "dest_role_id": str(dest_id)
                })
                await data.message.reply(f"Role added to server role inheritance: Having `@{source.name}` will add `@{dest.name}`.")
            except Exception as e:
                await Role.exception_handler(data.message, e, True)
        except Exception as e:
            await Role.exception_handler(data.message, e, True)
    
    @staticmethod
    async def poll_inheritance(bot):
        """Periodically check and apply role inheritance."""
        try:
            if Role.is_testing_client(bot):
                return
            
            # Get all inheritance rules
            inheritances = await bot.storage.get_all("roles_inherit")
            
            for key, value in inheritances.items():
                if not isinstance(value, dict):
                    continue
                
                guild_id = int(value.get("guild_id", 0))
                source_id = int(value.get("source_role_id", 0))
                dest_id = int(value.get("dest_role_id", 0))
                
                guild = bot.get_guild(guild_id)
                if not guild:
                    continue
                
                source_role = guild.get_role(source_id)
                dest_role = guild.get_role(dest_id)
                
                if not source_role or not dest_role:
                    continue
                
                # Find members with source role but not dest role
                for member in guild.members:
                    if source_role in member.roles and dest_role not in member.roles:
                        try:
                            await member.add_roles(dest_role, reason=f"Inherited from role {source_role.name}")
                            logger.debug(f"{member.display_name} inherits {dest_role.name} from {source_role.name}")
                        except Exception as e:
                            logger.warning(f"Failed to add inherited role: {e}")
        except Exception as e:
            logger.error(f"Error in poll_inheritance: {e}")
