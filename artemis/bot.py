"""
Copyright 2025, Vijay Challa - Use of this source code follows the MIT license found in the LICENSE file.

Core Artemis Bot class
"""

import disnake
from disnake.ext import commands
from typing import Optional
import logging
from dataclasses import dataclass

from artemis.storage.json_store import JSONStore
from artemis.events.manager import EventManager
from artemis.plugin.loader import PluginLoader
from artemis.commands.parser import CommandParser

logger = logging.getLogger("artemis.bot")


@dataclass
class EventData:
    """Data container for event callbacks."""
    message: Optional[disnake.Message] = None
    guild: Optional[disnake.Guild] = None
    channel: Optional[disnake.TextChannel] = None
    artemis: Optional["ArtemisBot"] = None


class ArtemisBot(commands.Bot):
    """
    Main bot class extending disnake Bot.
    """
    
    def __init__(self, config):
        """
        Initialize the bot.
        
        Args:
            config: Configuration object
        """
        # Bot configuration
        self.config = config
        
        # Initialize disnake Bot
        intents = disnake.Intents.default()
        intents.message_content = True
        super().__init__(
            command_prefix=config.COMMAND_PREFIX,
            intents=intents,
            help_command=None  # We'll implement custom help
        )
        
        # Initialize storage
        storage_dir = getattr(config, 'STORAGE_DIR', 'storage')
        self.storage = JSONStore(storage_dir)
        
        # Initialize event manager
        self.eventManager = EventManager(self)
        
        # Initialize plugin loader
        self.plugin_loader = PluginLoader("plugins")
        
        # Initialize command parser
        self.command_parser = CommandParser(config.COMMAND_PREFIX)
        
        # Expose logger as bot.log for plugin compatibility
        self.log = logger
        
        # Startup time
        import time
        self.startup_time = time.time()
        
        logger.info("Artemis bot initialized")
    
    async def setup_hook(self):
        """Called when the bot is about to connect to Discord."""
        # Set status to busy (dnd) during startup
        await self.change_presence(status=disnake.Status.dnd, activity=None)
        logger.info("Bot connecting - status set to busy")
    
    async def on_ready(self):
        """Called when bot is ready."""
        logger.info(f"Bot is ready! Logged in as {self.user}")
        logger.info(f"Connected to {len(self.guilds)} guilds")
        
        # Set bot status to online and apply configured activity
        await self._set_status()
        
        # Start periodic tasks
        self.eventManager.start_periodic_tasks()
        
        # Dispatch ready event
        await self.eventManager.dispatch_event("ready", self)
    
    async def _set_status(self):
        """Set the bot's presence status to online with configured activity."""
        # Always set status to online when ready
        activity_type = getattr(self.config, 'BOT_ACTIVITY_TYPE', None)
        activity_text = getattr(self.config, 'BOT_ACTIVITY_TEXT', None)
        
        # Create activity if configured
        activity = None
        if activity_type and activity_text:
            activity_type_map = {
                'playing': disnake.ActivityType.playing,
                'watching': disnake.ActivityType.watching,
                'listening': disnake.ActivityType.listening,
                'streaming': disnake.ActivityType.streaming,
                'competing': disnake.ActivityType.competing
            }
            
            activity_type_enum = activity_type_map.get(activity_type.lower(), disnake.ActivityType.playing)
            
            # For streaming, we need a URL
            if activity_type_enum == disnake.ActivityType.streaming:
                stream_url = getattr(self.config, 'BOT_STREAM_URL', 'https://twitch.tv')
                activity = disnake.Streaming(name=activity_text, url=stream_url)
            else:
                activity = disnake.Activity(type=activity_type_enum, name=activity_text)
        
        # Set the presence to online
        await self.change_presence(status=disnake.Status.online, activity=activity)
        
        if activity:
            activity_str = f"{activity_type}: {activity_text}"
            logger.info(f"Set bot presence - Status: online, {activity_str}")
        else:
            logger.info("Set bot presence - Status: online")
    
    async def on_message(self, message: disnake.Message):
        """Handle incoming messages."""
        # Ignore bot messages
        if message.author.bot:
            return
        
        # Parse for prefix commands (using custom command system)
        parsed = self.command_parser.parse(message.content)
        if parsed:
            logger.info(f"Parsed command: '{parsed.command}' from message: '{message.content}'")
            # Create event data
            event_data = EventData(
                message=message,
                guild=message.guild,
                channel=message.channel,
                artemis=self
            )
            
            # Dispatch command event
            await self.eventManager.dispatch_command(parsed.command, event_data)
        else:
            logger.debug(f"Message did not parse as command: {message.content}")
        
        # Dispatch message event
        await self.eventManager.dispatch_event("message", EventData(
            message=message,
            guild=message.guild,
            channel=message.channel,
            artemis=self
        ))
    
    async def on_guild_join(self, guild: disnake.Guild):
        """Handle guild join."""
        logger.info(f"Joined guild: {guild.name} ({guild.id})")
        await self.eventManager.dispatch_event("guildCreate", EventData(
            guild=guild,
            artemis=self
        ))
    
    def load_plugins(self) -> None:
        """Load all plugins."""
        logger.info("Loading plugins...")
        self.plugin_loader.load_plugins(self)
        logger.info(f"Loaded {len(self.plugin_loader.loaded_plugins)} plugins")
        logger.info(f"Registered commands: {sorted(self.eventManager.command_listeners.keys())}")
    
    def run(self) -> None:
        """Run the bot."""
        # Load plugins before starting
        self.load_plugins()
        
        # Start bot
        token = self.config.BOT_TOKEN
        if not token or token == "your-bot-token-here":
            logger.error("Bot token not configured! Please set BOT_TOKEN in config/config.py")
            return
        
        super().run(token)
    
    async def close(self):
        """Cleanup on shutdown."""
        logger.info("Shutting down...")
        
        # Set status to offline before shutting down
        try:
            await self.change_presence(status=disnake.Status.invisible, activity=None)
            logger.info("Set bot status to offline")
        except Exception as e:
            logger.warning(f"Failed to set offline status: {e}")
        
        # Stop periodic tasks
        self.eventManager.stop_periodic_tasks()
        
        # Close disnake connection
        await super().close()
        
        logger.info("Bot shutdown complete")
