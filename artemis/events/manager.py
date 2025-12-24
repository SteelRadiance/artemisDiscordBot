"""
Copyright 2025, Vijay Challa - Use of this source code follows the MIT license found in the LICENSE file.

EventManager for handling Discord events, commands, and periodic tasks
"""

import asyncio
from typing import Dict, List, Callable, Optional
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
        self.command_listeners: Dict[str, List[Callable]] = {}
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
                self.command_listeners[listener.command].append(listener.callback)
                logger.debug(f"Registered command listener: {listener.command}")
        
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
    
    async def dispatch_command(self, command: str, *args, **kwargs) -> None:
        """
        Dispatch a command to all registered listeners.
        
        Args:
            command: Command name
            *args: Command arguments
            **kwargs: Command keyword arguments
        """
        if command in self.command_listeners:
            for callback in self.command_listeners[command]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(*args, **kwargs)
                    else:
                        callback(*args, **kwargs)
                except Exception as e:
                    logger.error(f"Error in command listener for {command}: {e}", exc_info=True)
    
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
