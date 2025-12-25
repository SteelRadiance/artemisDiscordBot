"""
Copyright 2025, Vijay Challa - Use of this source code follows the MIT license found in the LICENSE file.

EventManager for handling Discord events, commands, and periodic tasks
"""

import asyncio
from typing import Dict, List, Callable, Optional, Union
import logging

from artemis.events.listener import EventListener

logger = logging.getLogger("artemis.events")


class EventManager:
    """Manages event listeners, commands, and periodic tasks."""
    
    def __init__(self, bot):
        """
        Initialize event manager.
        
        Args:
            bot: Bot instance
        """
        self.bot = bot
        self.event_listeners: Dict[str, List[Callable]] = {}
        self.command_listeners: Dict[str, List[tuple]] = {}  # List of (callback, guild_id, help_text) tuples
        self.command_help: Dict[str, Union[str, Callable]] = {}  # Command name -> help text/callable
        self.periodic_tasks: List[tuple] = []  # List of (interval, callback) tuples
        self._periodic_task_handles: List[asyncio.Task] = []
    
    def add_listener(self, listener: EventListener) -> None:
        """
        Add an event listener.
        
        Args:
            listener: EventListener configuration
        """
        if listener.event_name:
            if listener.event_name not in self.event_listeners:
                self.event_listeners[listener.event_name] = []
            if listener.callback:
                self.event_listeners[listener.event_name].append(listener.callback)
                logger.debug(f"Registered event listener: {listener.event_name}")
        
        if listener.command:
            if listener.command not in self.command_listeners:
                self.command_listeners[listener.command] = []
            if listener.callback:
                # Store callback with guild_id filter (None if no filter) and help text
                self.command_listeners[listener.command].append((listener.callback, listener.guild_id, listener.help_text))
                # Store help text if provided (overwrites previous if multiple listeners for same command)
                if listener.help_text:
                    self.command_help[listener.command] = listener.help_text
                logger.info(f"Registered command listener: {listener.command}" + 
                           (f" (guild: {listener.guild_id})" if listener.guild_id else ""))
        
        if listener.periodic and listener.callback:
            self.periodic_tasks.append((listener.periodic, listener.callback))
            logger.debug(f"Registered periodic task: {listener.periodic}s interval")
    
    async def dispatch_event(self, event_name: str, *args, **kwargs) -> None:
        """
        Dispatch an event to all registered listeners.
        
        Args:
            event_name: Name of the event
            *args: Event arguments
            **kwargs: Event keyword arguments
        """
        if event_name in self.event_listeners:
            for callback in self.event_listeners[event_name]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(*args, **kwargs)
                    else:
                        callback(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Error in event listener for {event_name}: {e}", exc_info=True)
    
    async def dispatch_command(self, command: str, parsed_args: Optional[list] = None, *args, **kwargs) -> None:
        """
        Dispatch a command to all registered listeners.
        
        Args:
            command: Command name
            parsed_args: Parsed command arguments (for checking -help flag)
            *args: Command arguments (EventData)
            **kwargs: Command keyword arguments
        """
        logger.info(f"Dispatching command: '{command}', available commands: {sorted(self.command_listeners.keys())}")
        
        # Check for -help flag
        if parsed_args and "-help" in parsed_args:
            await self._handle_help(command, args[0] if args else None)
            return
        
        if command in self.command_listeners:
            # Extract guild from EventData if present
            guild_id = None
            if args and hasattr(args[0], 'guild') and args[0].guild:
                guild_id = args[0].guild.id
            
            for callback_tuple in self.command_listeners[command]:
                callback = callback_tuple[0]
                filter_guild_id = callback_tuple[1] if len(callback_tuple) > 1 else None
                
                # Skip if guild filter doesn't match
                if filter_guild_id is not None and guild_id != filter_guild_id:
                    logger.debug(f"Skipping command {command} due to guild filter: {filter_guild_id} != {guild_id}")
                    continue
                
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(*args, **kwargs)
                    else:
                        callback(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Error in command listener for {command}: {e}", exc_info=True)
        else:
            logger.warning(f"Command '{command}' not found in registered commands: {sorted(self.command_listeners.keys())}")
    
    async def _handle_help(self, command: str, event_data) -> None:
        """
        Handle help request for a command.
        
        Args:
            command: Command name
            event_data: EventData object with message
        """
        if not event_data or not hasattr(event_data, 'message'):
            return
        
        help_text = None
        
        # Get help text from registered help
        if command in self.command_help:
            help_source = self.command_help[command]
            if isinstance(help_source, str):
                help_text = help_source
            elif callable(help_source):
                try:
                    if asyncio.iscoroutinefunction(help_source):
                        help_text = await help_source()
                    else:
                        help_text = help_source()
                except Exception as e:
                    logger.error(f"Error calling help function for {command}: {e}")
        
        # Send help message
        if help_text:
            await event_data.message.reply(help_text)
        else:
            await event_data.message.reply(f"No help available for command `{command}`.")
    
    def start_periodic_tasks(self) -> None:
        """Start all registered periodic tasks."""
        for interval, callback in self.periodic_tasks:
            task = asyncio.create_task(self._run_periodic(interval, callback))
            self._periodic_task_handles.append(task)
            logger.info(f"Started periodic task: {interval}s interval")
    
    async def _run_periodic(self, interval: int, callback: Callable) -> None:
        """Run a periodic task."""
        while True:
            try:
                await asyncio.sleep(interval)
                if asyncio.iscoroutinefunction(callback):
                    await callback(self.bot)
                else:
                    callback(self.bot)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in periodic task: {e}", exc_info=True)
    
    def stop_periodic_tasks(self) -> None:
        """Stop all periodic tasks."""
        for task in self._periodic_task_handles:
            task.cancel()
        self._periodic_task_handles.clear()
