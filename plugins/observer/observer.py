"""
Observer Plugin - Moderation logging and user reporting
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
        
        bot.eventManager.addEventListener(
            EventListener.new()
            .add_command("observer")
            .set_callback(Observer.config)
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
        async def on_reaction_add(reaction, user):
            await Observer.report_handler(reaction, user)
    
    @staticmethod
    async def get_info(guild: disnake.Guild) -> dict:
        """Get observer configuration for guild."""
        try:
            storage = guild._state._get_client().storage if hasattr(guild._state, '_get_client') else None
            if not storage:
                return None
            
            info = await storage.get("observer", str(guild.id))
            return info if isinstance(info, dict) else None
        except:
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
            
            # Try channel ID first
            try:
                channel_id = int(args[1])
                channel = data.message.guild.get_channel(channel_id)
                if channel:
                    await Observer.set_monitor(data.message.guild, channel)
                    await data.message.channel.send(f"{channel.mention} set as reporting channel for guild `{data.message.guild.name}`")
                    return
            except ValueError:
                pass
            
            # Try emote ID
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
    async def report_handler(reaction: disnake.Reaction, user: disnake.User):
        """Handle report reaction."""
        try:
            if not reaction.message.guild:
                return
            
            info = await Observer.get_info(reaction.message.guild)
            if not info or not info.get("channel_id") or not info.get("report_emote"):
                return
            
            if user.bot or reaction.message.author.id == user.id:
                return
            
            emote_id = str(reaction.emoji.id) if reaction.emoji.id else str(reaction.emoji)
            if emote_id != str(info["report_emote"]):
                return
            
            channel = reaction.message.guild.get_channel(int(info["channel_id"]))
            if not channel:
                return
            
            embed = Observer.embed_message(reaction.message, 0xcc0000)
            member = reaction.message.guild.get_member(user.id)
            
            await channel.send(
                f"**⚠ Reported message** - reported by {member.display_name if member else user.name} in {reaction.message.channel.mention} - {reaction.message.jump_url}",
                embed=embed
            )
            
            # Remove reaction
            await reaction.remove(user)
        except Exception as e:
            logger.warning(f"Error in report_handler: {e}")
