"""
ServerActivity Plugin - Track server message statistics
"""

import logging
from typing import Dict

import disnake

from artemis.plugin.base import PluginInterface, PluginHelper
from artemis.events.listener import EventListener
from artemis.permissions.resolver import Permission
from plugins.server_activity.monitor import ServerActivityMonitor

logger = logging.getLogger("artemis.plugin.serveractivity")


class ServerActivity(PluginInterface, PluginHelper):
    """Server activity tracking plugin."""
    
    _monitors: Dict[int, ServerActivityMonitor] = {}
    _counter = 0
    
    @staticmethod
    def register(bot):
        """Register the plugin."""
        if ServerActivity.is_testing_client(bot):
            bot.log.info("Not adding serveractivity on testing.")
            return
        
        # Message event
        bot.eventManager.addEventListener(
            EventListener.new()
            .add_event("message")
            .set_callback(ServerActivity.message_rx)
        )
        
        # Guild create event
        bot.eventManager.addEventListener(
            EventListener.new()
            .add_event("guildCreate")
            .set_callback(ServerActivity.guild_create)
        )
        
        # Periodic update (every 6 seconds)
        bot.eventManager.addEventListener(
            EventListener.new()
            .set_periodic(6)
            .set_callback(ServerActivity.update_rrd)
        )
        
        # Stats command
        bot.eventManager.addEventListener(
            EventListener.new()
            .add_command("messagestats")
            .set_callback(ServerActivity.stats_handler)
        )
    
    @staticmethod
    async def update_rrd(bot):
        """Periodically update RRD data."""
        ServerActivity._counter += 1
        
        for guild in bot.guilds:
            # Load balance: only process guilds matching counter mod 10
            if guild.id % 10 != ServerActivity._counter % 10:
                continue
            
            sam = ServerActivity.get_sam(guild)
            sam.commit()
    
    @staticmethod
    def get_sam(guild: disnake.Guild) -> ServerActivityMonitor:
        """Get or create ServerActivityMonitor for a guild."""
        if guild.id not in ServerActivity._monitors:
            ServerActivity._monitors[guild.id] = ServerActivityMonitor(guild)
        return ServerActivity._monitors[guild.id]
    
    @staticmethod
    async def message_rx(data):
        """Handle message event."""
        if data.guild:
            sam = ServerActivity.get_sam(data.guild)
            sam.add_message(data.message)
    
    @staticmethod
    async def guild_create(data):
        """Handle guild create event."""
        p = Permission("p.serveractivity.track", data.artemis, True)
        if data.message:
            p.add_message_context(data.message)
        
        # For now, allow by default (permission system can be extended)
        # if not await p.resolve():
        #     return
        
        ServerActivity.get_sam(data.guild)
    
    @staticmethod
    async def stats_handler(data):
        """Handle messagestats command."""
        try:
            p = Permission("p.serveractivity.view", data.artemis, True)
            p.add_message_context(data.message)
            if not await p.resolve():
                await p.send_unauthorized_message(data.message.channel)
                return
            
            sizes = {
                'day': '1d',
                'week': '1w'
            }
            
            # Check for "all" argument
            arg = ServerActivity.arg_substr(data.message.content, 1, 1)
            if arg == "all":
                sizes['month'] = '1m'
                sizes['year'] = '1y'
            
            sam = ServerActivity.get_sam(data.guild)
            
            graphs = sam.get_graphs(sizes)
            files = []
            for period, image_data in graphs.items():
                import io
                files.append(disnake.File(
                    fp=io.BytesIO(image_data),
                    filename=f"{data.guild.id}_messageactivity_{period}.png"
                ))
            
            if files:
                await data.message.reply(files=files)
            else:
                await data.message.reply("No statistics available yet.")
        except Exception as e:
            await ServerActivity.exception_handler(data.message, e, True)
