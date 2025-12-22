"""
State Plugin - Rules-read verification and mod statements
"""

import logging
import disnake
from disnake import Embed
import re

from artemis.plugin.base import PluginInterface, PluginHelper
from artemis.events.listener import EventListener
from artemis.permissions.resolver import Permission

logger = logging.getLogger("artemis.plugin.state")


class State(PluginInterface, PluginHelper):
    """State plugin for moderation statements."""
    
    @staticmethod
    def register(bot):
        """Register the plugin."""
        if State.is_testing_client(bot):
            bot.log.info("Not adding state commands on testing.")
            return
        
        bot.eventManager.addEventListener(
            EventListener.new()
            .add_command("state")
            .set_callback(State.process)
        )
    
    @staticmethod
    async def process(data):
        """Handle state command."""
        try:
            p = Permission("p.moderation.state", data.artemis, False)
            p.add_message_context(data.message)
            if not await p.resolve():
                await p.send_unauthorized_message(data.message.channel)
                return
            
            ctxt = State.arg_substr(data.message.content, 1, 1)
            if not ctxt:
                await data.message.reply("Usage: `!state [channel] then the rest of your message`")
                return
            
            # Check if first argument is a channel mention
            channel = State.channel_mention(ctxt, data.message.guild)
            if channel:
                state_text = State.arg_substr(data.message.content, 2)
                pic = data.message.guild.icon.url if data.message.guild.icon else None
            else:
                channel = data.message.channel
                state_text = State.arg_substr(data.message.content, 1)
                pic = data.message.author.display_avatar.url
            
            if not state_text:
                await data.message.reply("Usage: `!state [channel] then the rest of your message`")
                return
            
            # Generate ID (simplified - in PHP uses Snowflake)
            import time
            state_id = f"{int(time.time())}"
            
            embed = Embed(
                title="MOD STATEMENT",
                description=state_text,
                color=0xd10000,
                timestamp=disnake.utils.utcnow()
            )
            embed.set_footer(text=f"Mod Statement {state_id}", icon_url=pic)
            
            # Extract mentions
            mentions = " ".join([str(user) for user in data.message.mentions])
            if mentions:
                mentions = mentions + " - "
            
            notice = mentions + "Please acknowledge (if appropriate to do so)."
            
            sent_msg = await channel.send(notice, embed=embed)
            if channel.id != data.message.channel.id:
                await data.message.reply(f"Anonymous statement made in {sent_msg.channel.mention}!")
        except Exception as e:
            await State.exception_handler(data.message, e, True)
