"""
ServerActivityMonitor - Tracks message statistics per guild
"""

import os
import subprocess
import logging
from pathlib import Path
from typing import Dict

import disnake

logger = logging.getLogger("artemis.plugin.serveractivity")


class ServerActivityMonitor:
    """Monitors server activity and stores statistics using RRDtool."""
    
    def __init__(self, guild: disnake.Guild):
        """
        Initialize monitor for a guild.
        
        Args:
            guild: Discord guild to monitor
        """
        self.guild = guild
        self.messages = 0
        self.bot_messages = 0
        
        self.create_data_store()
    
    def create_data_store(self, force: bool = False) -> None:
        """Create RRD database file if it doesn't exist."""
        exe = "wsl rrdtool" if os.name == 'nt' else "rrdtool"
        filename = f"temp/serveractivity/{self.guild.id}_messages.rrd"
        
        # Ensure directory exists
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        
        if os.path.exists(filename) and not force:
            return
        
        # RRD create command
        command = [
            exe.split()[0] if os.name == 'nt' else exe,
            "create", filename,
            "--step", "60",
            "DS:messages:ABSOLUTE:120:0:U",
            "DS:botmessages:ABSOLUTE:120:0:U",
            "DS:users:GAUGE:120:0:U",
            "RRA:AVERAGE:0.5:1:1440",  # 1 day @ 1 minute resolution
            "RRA:AVERAGE:0.5:15:672",  # 1 week @ 15 minute resolution
            "RRA:AVERAGE:0.5:60:720",  # 30 days @ 1 hour resolution
            "RRA:AVERAGE:0.5:1440:365",  # 365 days @ 1 day resolution
            "RRA:LAST:0.5:1:1440",
            "RRA:LAST:0.5:15:672",
            "RRA:LAST:0.5:60:720",
            "RRA:LAST:0.5:1440:365",
            "RRA:MAX:0.5:1:1440",
            "RRA:MAX:0.5:15:672",
            "RRA:MAX:0.5:60:720",
            "RRA:MAX:0.5:1440:365",
        ]
        
        if os.name == 'nt':
            # On Windows, use wsl
            command = ["wsl"] + command[1:]
        
        try:
            logger.info(f"Creating server activity logger file {filename}...")
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode != 0:
                logger.warning(f"RRDtool create failed: {result.stderr}")
        except Exception as e:
            logger.error(f"Error creating RRD file: {e}")
    
    def get_graphs(self, sizes: Dict[str, str]) -> Dict[str, bytes]:
        """
        Generate graphs for different time periods.
        
        Args:
            sizes: Dictionary mapping period names to RRDtool time specs
            
        Returns:
            Dictionary mapping period names to PNG image data
        """
        files = {}
        exe = "wsl rrdtool" if os.name == 'nt' else "rrdtool"
        filename = f"temp/serveractivity/{self.guild.id}_messages.rrd"
        safe_name = self.guild.name.replace('"', '\\"')
        
        for period, time_spec in sizes.items():
            command = [
                exe.split()[0] if os.name == 'nt' else exe,
                "graph", "-",
                "--start", f"end-{time_spec}",
                "--imgformat", "PNG",
                "--title", f"{safe_name} message rates",
                "--vertical-label", "messages per second",
                "--width", "480",
                "--height", "160",
                "--watermark", "Timezone: UTC",
                "--use-nan-for-all-missing-data",
                "--lower-limit", "0",
                f"DEF:avgrate={filename}:messages:AVERAGE",
                f"DEF:avgbotrate={filename}:botmessages:AVERAGE",
                f"DEF:maxrate={filename}:messages:MAX",
                f"DEF:maxbotrate={filename}:botmessages:MAX",
                "LINE1:avgrate#FF0000FF:all (avg)",
                "LINE1:avgbotrate#0000FFFF:bots (avg)",
                "LINE1:maxrate#FF000040:all (peak)",
                "LINE1:maxbotrate#0000FF40:bots (peak)",
            ]
            
            if os.name == 'nt':
                command = ["wsl"] + command[1:]
            
            try:
                result = subprocess.run(command, capture_output=True)
                if result.returncode == 0:
                    files[period] = result.stdout
                else:
                    logger.error(f"RRDtool graph failed for {period}: {result.stderr.decode()}")
            except Exception as e:
                logger.error(f"Error generating graph for {period}: {e}")
        
        return files
    
    def add_message(self, message: disnake.Message) -> None:
        """Add a message to the counter."""
        self.messages += 1
        
        if message.author.bot or getattr(message.author, 'webhook', None) or message.system:
            self.bot_messages += 1
    
    def commit(self) -> None:
        """Commit data to RRD and reset counters."""
        self.add_data()
        self.wipe()
    
    def add_data(self) -> None:
        """Add current data to RRD file."""
        exe = "wsl rrdtool" if os.name == 'nt' else "rrdtool"
        filename = f"temp/serveractivity/{self.guild.id}_messages.rrd"
        
        messages = self.messages
        bot_messages = self.bot_messages
        users = self.guild.member_count or 0
        
        command = [
            exe.split()[0] if os.name == 'nt' else exe,
            "update", filename,
            f"N:{messages}:{bot_messages}:{users}"
        ]
        
        if os.name == 'nt':
            command = ["wsl"] + command[1:]
        
        try:
            logger.debug(f"Updating server activity {filename}...")
            result = subprocess.run(command, capture_output=True, text=True)
            if result.returncode != 0:
                logger.warning(f"RRDtool update failed: {result.stderr}")
        except Exception as e:
            logger.error(f"Error updating RRD file: {e}")
    
    def wipe(self) -> None:
        """Reset counters."""
        self.messages = 0
        self.bot_messages = 0
