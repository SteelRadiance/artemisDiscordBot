"""
Copyright 2025, Vijay Challa - Use of this source code follows the MIT license found in the LICENSE file.

State Plugin - Rules-read verification and mod statements

This plugin allows moderators to post official moderation statements to channels.
These statements can be posted anonymously (using server icon) or with the moderator's
avatar, and can be targeted to specific channels. Useful for posting rules, warnings,
or other official server communications.

Commands:
    !state [channel] <message> - Post a moderation statement

Features:
    - Anonymous or attributed moderation statements
    - Channel targeting (can post to different channels)
    - Automatic mention extraction and acknowledgment requests
    - Distinctive formatting with "MOD STATEMENT" title
    - Timestamped statements with unique IDs
    - Permission-based access control
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
        
        bot.eventManager.add_listener(
            EventListener.new()
            .add_command("state")
            .set_callback(State.process)
            .set_help("**Usage**: `!state [channel] <message>`\n\nPost a moderation statement. If a channel is specified, posts to that channel; otherwise posts to the current channel. Requires permission `p.moderation.state`.")
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
            
            import time
            state_id = f"{int(time.time())}"
            
            embed = Embed(
                title="MOD STATEMENT",
                description=state_text,
                color=0xd10000,
                timestamp=disnake.utils.utcnow()
            )
            embed.set_footer(text=f"Mod Statement {state_id}", icon_url=pic)
            
            mentions = " ".join([str(user) for user in data.message.mentions])
            if mentions:
                mentions = mentions + " - "
            
            notice = mentions + "Please acknowledge (if appropriate to do so)."
            
            sent_msg = await channel.send(notice, embed=embed)
            if channel.id != data.message.channel.id:
                await data.message.reply(f"Anonymous statement made in {sent_msg.channel.mention}!")
        except Exception as e:
            await State.exception_handler(data.message, e, True)
