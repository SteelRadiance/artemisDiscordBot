"""
Ironreach Plugin - Ironreach server-specific features
"""

import logging
import disnake
import random
from pathlib import Path

from artemis.plugin.base import PluginInterface, PluginHelper
from artemis.events.listener import EventListener
from artemis.permissions.resolver import Permission

logger = logging.getLogger("artemis.plugin.ironreach")


class Ironreach(PluginInterface, PluginHelper):
    """Ironreach plugin for server-specific features."""
    
    COMREP_ROLE = 766785052163571734
    JURY_CHANNEL = 769771967606947840
    JURY_ROLE = 769772066371010590
    IRONREACH_GUILD_ID = 673383165943087115
    
    @staticmethod
    def register(bot):
        """Register the plugin."""
        if Ironreach.is_testing_client(bot):
            bot.log.info("Not adding ironreach commands on testing.")
            return
        
        # Only register for specific guild
        bot.eventManager.addEventListener(
            EventListener.new()
            .add_command("jury")
            .add_guild(Ironreach.IRONREACH_GUILD_ID)
            .set_callback(Ironreach.jury)
        )
        
        bot.eventManager.addEventListener(
            EventListener.new()
            .add_command("talkingstick")
            .add_guild(Ironreach.IRONREACH_GUILD_ID)
            .set_callback(Ironreach.talkingstick)
        )
        
        bot.eventManager.addEventListener(
            EventListener.new()
            .add_command("vc")
            .add_guild(Ironreach.IRONREACH_GUILD_ID)
            .set_callback(Ironreach.voice_chat)
        )
        
        # Periodic voice chat update
        bot.eventManager.addEventListener(
            EventListener.new()
            .set_periodic(60 * 60)
            .set_callback(Ironreach.voice_chat_change)
        )
        
        # Register agenda config event
        bot.eventManager.addEventListener(
            EventListener.new()
            .add_event("agendaPluginConf")
            .set_callback(Ironreach.handle_agenda_config)
        )
    
    @staticmethod
    async def handle_agenda_config(bot, configs: dict):
        """Handle agenda configuration event."""
        if not isinstance(configs, dict):
            return
        
        configs[str(Ironreach.IRONREACH_GUILD_ID)] = {
            'staffRole': 741883050278912050,
            'tiebreakerRole': Ironreach.COMREP_ROLE,
            'quorum': 2/3,
            'voteTypes': {
                "For": 747168156866314282,
                "Against": 747168184246861914,
                "Abstain": "👀",
                "Absent": None,
            },
        }
    
    @staticmethod
    async def voice_chat(data):
        """Handle voice chat command."""
        try:
            p = Permission("p.ironreach.changevc", data.artemis, False)
            p.add_message_context(data.message)
            if not await p.resolve():
                await p.send_unauthorized_message(data.message.channel)
                return
            
            await Ironreach.voice_chat_change(data.artemis)
            await data.message.add_reaction("😤")
        except Exception as e:
            await Ironreach.exception_handler(data.message, e)
    
    @staticmethod
    async def voice_chat_change(bot):
        """Change voice channel names."""
        try:
            guild = bot.get_guild(Ironreach.IRONREACH_GUILD_ID)
            if not guild:
                return
            
            # Find empty voice channels in specific category
            category_id = 673383165943087117
            empty_channels = [
                ch for ch in guild.voice_channels
                if ch.category_id == category_id and len(ch.members) == 0
            ]
            
            if not empty_channels:
                return
            
            # Load track names from file
            try:
                tracks_file = Path("data/ironreach.txt")
                if tracks_file.exists():
                    with open(tracks_file, 'r', encoding='utf-8') as f:
                        tracks = [line.strip() for line in f if line.strip()]
                else:
                    tracks = ["Track 1", "Track 2", "Track 3"]  # Fallback
            except:
                tracks = ["Track 1", "Track 2", "Track 3"]
            
            # Assign random track names
            selected_tracks = random.sample(tracks, min(len(empty_channels), len(tracks)))
            
            for channel, track_name in zip(empty_channels, selected_tracks):
                try:
                    await channel.edit(name=track_name)
                except Exception as e:
                    logger.warning(f"Failed to rename channel {channel.name}: {e}")
            
            # Update voice-text channel name
            vtc_id = 747227035495170218
            vtc = guild.get_channel(vtc_id)
            if vtc:
                words = ['voice', 'text', 'chat']
                new_name = f"{random.choice(words)}-{random.choice(words)}-{random.choice(words)}"
                try:
                    await vtc.edit(name=new_name)
                except Exception as e:
                    logger.warning(f"Failed to rename VTC channel: {e}")
        except Exception as e:
            logger.error(f"Error in voice_chat_change: {e}")
    
    @staticmethod
    async def talkingstick(data):
        """Handle talking stick command."""
        try:
            staff_channel_id = 747153810392350740
            
            staff_channel = data.guild.get_channel(staff_channel_id)
            if staff_channel:
                await staff_channel.send(
                    f"<@&741883050278912050>: {data.message.member.mention} has asked for the talking stick!"
                )
            
            await data.message.channel.send("Your request to get the Talking Stick has been relayed to staff.")
            await data.message.delete()
        except Exception as e:
            await Ironreach.exception_handler(data.message, e)
    
    @staticmethod
    async def jury(data):
        """Handle jury command."""
        try:
            args = Ironreach.split_command(data.message.content)
            if len(args) < 2:
                await data.message.reply("Usage: `!jury <user>`")
                return
            
            user_text = " ".join(args[1:])
            member = Ironreach.parse_guild_user(data.guild, user_text)
            
            if not member:
                await data.message.reply("Could not find that user.")
                return
            
            jury_channel = data.guild.get_channel(Ironreach.JURY_CHANNEL)
            jury_role = data.guild.get_role(Ironreach.JURY_ROLE)
            
            if not jury_channel or not jury_role:
                await data.message.reply("Jury system not configured.")
                return
            
            # Add jury role
            try:
                await member.add_roles(jury_role, reason="Added via jury command")
                await jury_channel.send(f"{member.mention} has been added to the jury.")
                await data.message.reply(f"{member.display_name} has been added to the jury.")
            except Exception as e:
                await data.message.reply(f"Failed to add {member.display_name} to jury: {e}")
        except Exception as e:
            await Ironreach.exception_handler(data.message, e)
