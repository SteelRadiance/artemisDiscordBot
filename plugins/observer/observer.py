"""
Copyright 2025, Vijay Challa - Use of this source code follows the MIT license found in the LICENSE file.

Observer Plugin - Moderation logging and user reporting

This plugin provides comprehensive moderation logging and user reporting functionality.
It logs message deletions, member joins/leaves, invite creation, and handles user
reports via reactions. All logs are sent to a configured monitoring channel.

Commands:
    !observer <channel_id> - Set monitoring channel
    !observer <emote_id> - Set report emote

Features:
    - Message deletion logging with content and metadata
    - Member join/leave tracking with roles and account info
    - Invite creation monitoring
    - User reporting via reaction (configurable emote)
    - Per-guild configuration for monitoring channels
    - Detailed embed formatting for all logged events
    - Automatic reaction removal after reporting
"""

import logging
import disnake
from disnake import Embed
from datetime import datetime

from artemis.plugin.base import PluginInterface, PluginHelper
from artemis.events.listener import EventListener

logger = logging.getLogger("artemis.plugin.observer")


class Observer(PluginInterface, PluginHelper):
    """Observer plugin for moderation logging."""
    
    @staticmethod
    def register(bot):
        """Register the plugin."""
        if Observer.is_testing_client(bot):
            bot.log.info("Not adding observer on testing.")
            return
        
        bot.eventManager.add_listener(
            EventListener.new()
            .add_command("observer")
            .set_callback(Observer.config)
            .set_help("**Usage**: `!observer`\n\nConfigure moderation logging settings. This command is admin only. The observer plugin automatically logs message deletions, member joins/leaves, and other moderation events.")
        )
        
        # Register Discord events
        @bot.event
        async def on_message_delete(message):
            await Observer.observer_handler(message)
        
        @bot.event
        async def on_bulk_message_delete(messages):
            for msg in messages:
                await Observer.observer_handler(msg)
        
        @bot.event
        async def on_member_join(member):
            await Observer.join_handler(member)
        
        @bot.event
        async def on_member_remove(member):
            await Observer.leave_handler(member)
        
        @bot.event
        async def on_invite_create(invite):
            await Observer.invite_handler(invite)
        
        @bot.event
        async def on_raw_reaction_add(payload):
            await Observer.report_handler(bot, payload)
    
    @staticmethod
    async def get_info(guild: disnake.Guild, bot=None) -> dict:
        """Get observer configuration for guild."""
        try:
            if bot and hasattr(bot, 'storage'):
                storage = bot.storage
            else:
                # Fall back to getting storage from guild state
                storage = guild._state._get_client().storage if hasattr(guild._state, '_get_client') else None
            
            if not storage:
                return None
            
            info = await storage.get("observer", str(guild.id))
            return info if isinstance(info, dict) else None
        except Exception as e:
            logger.warning(f"Failed to get observer info for guild {guild.id}: {e}")
            return None
    
    @staticmethod
    async def config(data):
        """Handle observer config command."""
        try:
            admin_ids = getattr(data.artemis.config, 'ADMIN_USER_IDS', [])
            if str(data.message.author.id) not in admin_ids:
                await Observer.unauthorized(data.message)
                return
            
            args = Observer.split_command(data.message.content)
            if len(args) != 2:
                await data.message.channel.send("Malformed command.")
                return
            
            try:
                channel_id = int(args[1])
                channel = data.message.guild.get_channel(channel_id)
                if channel:
                    await Observer.set_monitor(data.message.guild, channel)
                    await data.message.channel.send(f"{channel.mention} set as reporting channel for guild `{data.message.guild.name}`")
                    return
            except ValueError:
                pass
            
            try:
                emote_id = int(args[1])
                await Observer.set_report(data.message.guild, emote_id)
                await data.message.channel.send(f"`{args[1]}` set as reporting emote for guild `{data.message.guild.name}`")
            except ValueError:
                await data.message.channel.send("Invalid channel or emote ID.")
        except Exception as e:
            await Observer.exception_handler(data.message, e)
    
    @staticmethod
    async def set_monitor(guild: disnake.Guild, channel: disnake.TextChannel):
        """Set monitoring channel."""
        try:
            storage = guild._state._get_client().storage if hasattr(guild._state, '_get_client') else None
            if storage:
                await storage.set("observer", str(guild.id), {
                    "guild_id": str(guild.id),
                    "channel_id": str(channel.id),
                    "report_emote": None
                })
        except Exception as e:
            logger.error(f"Failed to set monitor: {e}")
    
    @staticmethod
    async def set_report(guild: disnake.Guild, emote_id: int):
        """Set report emote."""
        try:
            storage = guild._state._get_client().storage if hasattr(guild._state, '_get_client') else None
            if storage:
                info = await storage.get("observer", str(guild.id))
                if not info:
                    info = {"guild_id": str(guild.id)}
                info["report_emote"] = str(emote_id)
                await storage.set("observer", str(guild.id), info)
        except Exception as e:
            logger.error(f"Failed to set report: {e}")
    
    @staticmethod
    async def observer_handler(message: disnake.Message):
        """Handle message deletion."""
        try:
            if not message.guild:
                return
            
            info = await Observer.get_info(message.guild)
            if not info or not info.get("channel_id"):
                return
            
            channel = message.guild.get_channel(int(info["channel_id"]))
            if not channel or message.author.bot:
                return
            
            embed = Observer.embed_message(message)
            await channel.send(f"🗑 Message deleted - from {message.channel.mention}", embed=embed)
        except Exception as e:
            logger.warning(f"Error in observer_handler: {e}")
    
    @staticmethod
    def embed_message(message: disnake.Message, color: int = None) -> Embed:
        """Create embed from message."""
        embed = Embed(
            description=message.content[:2000] if message.content else "*No content*",
            timestamp=message.created_at,
            color=color or 0xff0000
        )
        embed.set_author(
            name=f"{message.author.name}#{message.author.discriminator}",
            icon_url=message.author.display_avatar.url
        )
        
        if message.attachments:
            att_text = "\n".join([f"{att.filename} ({att.size} bytes)" for att in message.attachments[:5]])
            embed.add_field(name="Attachments", value=att_text[:1024], inline=False)
        
        return embed
    
    @staticmethod
    async def join_handler(member: disnake.Member):
        """Handle member join."""
        try:
            info = await Observer.get_info(member.guild)
            if not info or not info.get("channel_id"):
                return
            
            channel = member.guild.get_channel(int(info["channel_id"]))
            if not channel:
                return
            
            embed = Embed(
                title="Member Joined",
                color=0x7bf43,
                timestamp=datetime.now()
            )
            embed.set_author(name=f"{member.name}#{member.discriminator}", icon_url=member.display_avatar.url)
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="Name", value=f"{member.mention} ({member.name}#{member.discriminator})", inline=True)
            embed.add_field(name="ID", value=str(member.id), inline=True)
            embed.add_field(name="Joined Discord", value=member.created_at.strftime("%Y-%m-%d"), inline=True)
            embed.add_field(name="Member #", value=str(member.guild.member_count), inline=True)
            
            await channel.send("👋 Member joined", embed=embed)
        except Exception as e:
            logger.warning(f"Error in join_handler: {e}")
    
    @staticmethod
    async def leave_handler(member: disnake.Member):
        """Handle member leave."""
        try:
            info = await Observer.get_info(member.guild)
            if not info or not info.get("channel_id"):
                return
            
            channel = member.guild.get_channel(int(info["channel_id"]))
            if not channel:
                return
            
            embed = Embed(
                title="Member Left",
                color=0xbf2222,
                timestamp=datetime.now()
            )
            embed.set_author(name=f"{member.name}#{member.discriminator}", icon_url=member.display_avatar.url)
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.add_field(name="Name", value=f"{member.mention} ({member.name}#{member.discriminator})", inline=True)
            embed.add_field(name="ID", value=str(member.id), inline=True)
            
            roles = [role.mention for role in member.roles if role.name != "@everyone"]
            if roles:
                roles_text = ", ".join(roles[:20])
                if len(roles_text) > 1024:
                    roles_text = roles_text[:1021] + "..."
                embed.add_field(name="Roles", value=roles_text or "<no roles>", inline=False)
            
            await channel.send("💨 Member left (or was banned)", embed=embed)
        except Exception as e:
            logger.warning(f"Error in leave_handler: {e}")
    
    @staticmethod
    async def invite_handler(invite: disnake.Invite):
        """Handle invite creation."""
        try:
            info = await Observer.get_info(invite.guild)
            if not info or not info.get("channel_id"):
                return
            
            channel = invite.guild.get_channel(int(info["channel_id"]))
            if not channel:
                return
            
            embed = Embed(
                title="Invite Created",
                color=0x55aace,
                timestamp=datetime.now()
            )
            embed.set_author(name=f"{invite.inviter.name}#{invite.inviter.discriminator}", icon_url=invite.inviter.display_avatar.url)
            embed.set_thumbnail(url=invite.inviter.display_avatar.url)
            embed.add_field(name="Code", value=f"[{invite.code}]({invite.url})", inline=True)
            embed.add_field(name="Creator", value=f"{invite.inviter.mention} ({invite.inviter.name}#{invite.inviter.discriminator})", inline=True)
            embed.add_field(name="Channel", value=invite.channel.mention if invite.channel else "Unknown", inline=True)
            embed.add_field(name="Max Uses", value=str(invite.max_uses) if invite.max_uses else "Unlimited", inline=True)
            
            await channel.send("📨 Invite created", embed=embed)
        except Exception as e:
            logger.warning(f"Error in invite_handler: {e}")
    
    @staticmethod
    async def report_handler(bot, payload: disnake.RawReactionActionEvent):
        """Handle report reaction."""
        if payload.event_type != "REACTION_ADD":
            return
            
        if payload.user_id == bot.user.id:
            return
        
        guild = bot.get_guild(payload.guild_id)
        if not guild:
            return
        
        info = await Observer.get_info(guild, bot)
        if not info or not info.get("channel_id"):
            logger.debug(f"No observer channel configured for guild {guild.id}")
            return
        
        channel = guild.get_channel(int(info["channel_id"]))
        if not channel:
            logger.warning(f"Observer channel {info['channel_id']} not found in guild {guild.id}")
            return
        
        if not info.get("report_emote"):
            embed = Embed(
                title="Warning: No report emote set",
                color=0xbf2222,
                timestamp=datetime.now()
            )
            await channel.send(embed=embed)
            return

        emoji_id = str(payload.emoji.id) if payload.emoji.id else str(payload.emoji)
        report_emote_id = str(info["report_emote"])
        
        if emoji_id != report_emote_id:
            return
        
        message_channel = guild.get_channel(payload.channel_id)
        if not message_channel:
            return
        
        try:
            message = await message_channel.fetch_message(payload.message_id)
        except Exception as e:
            logger.warning(f"Failed to fetch message {payload.message_id}: {e}")
            return
        
        try:
            await message.remove_reaction(payload.emoji, payload.member or await guild.fetch_member(payload.user_id))
        except Exception as e:
            logger.warning(f"Failed to remove reaction: {e}")

        reporter = payload.member or await guild.fetch_member(payload.user_id)
        if not reporter:
            reporter = await bot.fetch_user(payload.user_id)
        
        embed = Embed(
            title="Message Reported",
            color=0xbf2222,
            timestamp=datetime.now()
        )
        embed.set_author(name=f"{reporter.name}#{getattr(reporter, 'discriminator', '')}", icon_url=reporter.display_avatar.url)
        embed.add_field(name="Reported by", value=f"{reporter.mention} ({reporter.name})", inline=True)
        embed.add_field(name="Reported User", value=f"{message.author.mention} ({message.author.name})", inline=True)
        embed.add_field(name="Channel", value=message_channel.mention, inline=True)
        embed.add_field(name="Reported Message", value=message.content[:2000] if message.content else "*No content*", inline=False)
        embed.add_field(name="Message Link", value=f"[Jump to Message]({message.jump_url})", inline=False)

        await channel.send(embed=embed)