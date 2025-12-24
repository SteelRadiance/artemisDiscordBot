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
        
        # Startup time
        import time
        self.startup_time = time.time()
        
        logger.info("Artemis bot initialized")
    
    async def on_ready(self):
        """Called when bot is ready."""
        logger.info(f"Bot is ready! Logged in as {self.user}")
        logger.info(f"Connected to {len(self.guilds)} guilds")
        
        # Start periodic tasks
        self.eventManager.start_periodic_tasks()
        
        # Dispatch ready event
        await self.eventManager.dispatch_event("ready", self)
    
    async def on_message(self, message: disnake.Message):
        """Handle incoming messages."""
        # Ignore bot messages
        if message.author.bot:
            return
        
        # Process commands first (disnake's command system)
        await self.process_commands(message)
        
        # Parse for prefix commands
        parsed = self.command_parser.parse(message.content)
        if parsed:
            # Create event data
            event_data = EventData(
                message=message,
                guild=message.guild,
                channel=message.channel,
                artemis=self
            )
            
            # Dispatch command event
            await self.eventManager.dispatch_command(parsed.command, event_data)
        
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
        
        # Stop periodic tasks
        self.eventManager.stop_periodic_tasks()
        
        # Close disnake connection
        await super().close()
        
        logger.info("Bot shutdown complete")
