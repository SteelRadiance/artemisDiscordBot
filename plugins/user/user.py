"""
Copyright 2025, Vijay Challa - Use of this source code follows the MIT license found in the LICENSE file.

User Plugin - User information and utilities

This plugin provides user information and utility commands. It displays detailed
user profiles including roles, permissions, and account information. It also
provides roster functionality to list members with specific roles.

Commands:
    !user [user] - Display user information
    !roster <role> - List all members with a role
    !av [user] - Get a user's avatar URL

Features:
    - Comprehensive user information display
    - Role listing with IDs
    - Permission display (guild and channel-level)
    - Roster generation sorted by join date
    - Avatar URL retrieval
    - Formatted output with proper spacing
"""

import logging
from datetime import datetime
import disnake
from disnake import Embed

from artemis.plugin.base import PluginInterface, PluginHelper
from artemis.events.listener import EventListener
from artemis.permissions.resolver import Permission

logger = logging.getLogger("artemis.plugin.user")


class User(PluginInterface, PluginHelper):
    """User plugin for user information."""
    
    @staticmethod
    def register(bot):
        """Register the plugin."""
        if User.is_testing_client(bot):
            bot.log.info("Not adding user commands on testing.")
            return
        
        bot.eventManager.add_listener(
            EventListener.new()
            .add_command("user")
            .set_callback(User.process)
            .set_help("**Usage**: `!user [user]`\n\nDisplay detailed user information including ID, username, nickname, roles, permissions, and account creation date. If no user is specified, shows your own information.")
        )
        
        bot.eventManager.add_listener(
            EventListener.new()
            .add_command("roster")
            .set_callback(User.roster)
            .set_help("**Usage**: `!roster <role>`\n\nList all members with a specific role, sorted by join date. Requires permission `p.userutils.roster`.")
        )
        
        bot.eventManager.add_listener(
            EventListener.new()
            .add_command("av")
            .set_callback(User.av)
            .set_help("**Usage**: `!av [user]`\n\nGet a user's avatar URL. If no user is specified, shows your own avatar.")
        )
    
    @staticmethod
    async def process(data):
        """Handle user command."""
        try:
            args = User.split_command(data.message.content)
            user_text = " ".join(args[1:]) if len(args) > 1 else ""
            
            if user_text:
                member = await User.parse_guild_user(data.message.guild, user_text)
            else:
                member = data.guild.get_member(data.message.author.id) if data.guild else None
            
            if not member:
                await data.message.reply("Could not find that user.")
                return
            
            roles = []
            for role in sorted(member.roles, key=lambda r: r.position, reverse=True):
                if role.name != "@everyone":
                    roles.append(f"{role.mention} ({role.id})")
            
            if not roles:
                roles = ["<no roles>"]
            
            perms = [perm for perm, value in member.guild_permissions if value] 
            embed = Embed(title="User Information", color=member.color)
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="ID", value=str(member.id), inline=True)
            embed.add_field(name="Username", value=f"{member.name}#{member.discriminator}", inline=True)
            embed.add_field(name="Nick", value=member.display_name if member.display_name != member.name else "<unset>", inline=True)
            embed.add_field(name="Color", value=str(member.color) if member.color.value else "<unset>", inline=True)
            
            roles_text = "\n".join(roles)
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
            
            embed.add_field(name="Permissions", value="\n".join(perms[:20]) if perms else "None", inline=True)
             
            await data.message.channel.send(embed=embed)
        except Exception as e:
            await User.exception_handler(data.message, e, True)
    
    @staticmethod
    async def roster(data):
        """Handle roster command."""
        try:
            if not data.guild:
                await data.message.reply("Must be run in a server, not in DMs.")
                return
            
            p = Permission("p.userutils.roster", data.artemis, True)
            p.add_message_context(data.message)
            if not await p.resolve():
                await p.send_unauthorized_message(data.message.channel)
                return
            
            role_str = User.arg_substr(data.message.content, 1)
            if not role_str:
                await data.message.reply("Usage: `!roster ROLE`")
                return
            
            role = User.parse_role(data.guild, role_str)
            if not role:
                await data.message.reply("Unknown role. Type it out, @ it, or paste in the role ID.")
                return
            
            # Chunk the guild to ensure all members are loaded
            # Check if we have significantly fewer members cached than the server reports
            cached_count = len(data.guild.members)
            server_count = data.guild.member_count or cached_count
            
            if cached_count < server_count * 0.9:  # If we're missing more than 10% of members
                status_msg = await data.message.channel.send("Loading all members... This may take a moment.")
                try:
                    await data.guild.chunk()
                    if status_msg:
                        await status_msg.delete()
                except Exception as e:
                    logger.warning(f"Failed to chunk guild {data.guild.id}: {e}")
                    if status_msg:
                        await status_msg.edit(content=f"Warning: Could not load all members. Showing only {cached_count} cached members.")
            
            members_with_role = [
                member for member in data.guild.members
                if role in member.roles
            ]
            members_with_role.sort(key=lambda m: m.joined_at or datetime.min)
            
            if not members_with_role:
                await data.message.reply(f"No members found with role {role.mention}")
                return
            
            lines = []
            max_name_len = 0
            for member in members_with_role:
                name = f"{member.display_name} ({member.name}#{member.discriminator})"
                max_name_len = max(max_name_len, len(name))
            
            for member in members_with_role:
                name = f"{member.display_name} ({member.name}#{member.discriminator})"
                joined = member.joined_at.strftime("%Y-%m-%d %H:%M:%S") if member.joined_at else "Unknown"
                lines.append(f"{name:<{max_name_len}}  {joined}")
            
            output = "```\n" + "\n".join(lines) + "\n```"
            await data.message.reply(output)
        except Exception as e:
            await User.exception_handler(data.message, e, True)
    
    @staticmethod
    async def av(data):
        """Handle av command."""
        try:
            user_text = User.arg_substr(data.message.content, 1) or ""
            member = await User.parse_guild_user(data.message.guild, user_text) if user_text else (data.guild.get_member(data.message.author.id) if data.guild else None)
            
            if not member:
                await data.message.reply("Could not find that user.")
                return
            
            await data.message.reply(f"{member.display_name}'s av: {member.display_avatar.url}")
        except Exception as e:
            await User.exception_handler(data.message, e)
