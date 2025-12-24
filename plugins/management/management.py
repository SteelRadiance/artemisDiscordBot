"""
Management Plugin - Bot management commands

This plugin provides core bot administration commands including ping testing,
bot information display, restart functionality, git updates, and invite link
generation. It shows system statistics, loaded plugins, dependencies, and
bot status information.

Commands:
    !ping - Test bot latency
    !artemis - Display bot information and statistics
    !restart - Restart the bot (admin only)
    !update - Pull latest code from git (admin only)
    !invite - Generate bot invite URL

Features:
    - Ping measurement using Discord snowflake timestamps
    - Comprehensive bot info: memory, Python version, uptime, guild/channel counts
    - Plugin listing with emoji-based version hashes
    - Dependency version display
    - Git integration for updates
    - OAuth invite URL generation with proper permissions
"""

import time
import os
import sys
import subprocess
import importlib.metadata
from datetime import datetime, timedelta
import logging

import disnake
from disnake import Embed

from artemis.plugin.base import PluginInterface, PluginHelper
from artemis.events.listener import EventListener
from artemis.permissions.resolver import Permission
from artemis.utils.helpers import format_bytes, emoji_hash
from artemis import __version__

logger = logging.getLogger("artemis.plugin.management")


class Management(PluginInterface, PluginHelper):
    """Management plugin for bot administration."""
    
    startup_time: float = None
    
    @staticmethod
    def register(bot):
        """Register the plugin."""
        if Management.is_testing_client(bot):
            bot.log.info("Not adding management commands on testing.")
            return
        
        # Set startup time
        Management.startup_time = time.time()
        
        # Register commands
        bot.eventManager.addEventListener(
            EventListener.new()
            .add_command("ping")
            .set_callback(Management.ping)
        )
        
        bot.eventManager.addEventListener(
            EventListener.new()
            .add_command("artemis")
            .set_callback(Management.info)
        )
        
        bot.eventManager.addEventListener(
            EventListener.new()
            .add_command("restart")
            .set_callback(Management.restart)
        )
        
        bot.eventManager.addEventListener(
            EventListener.new()
            .add_command("update")
            .set_callback(Management.update)
        )
        
        bot.eventManager.addEventListener(
            EventListener.new()
            .add_command("invite")
            .set_callback(Management.invite)
        )
        
        # Register ready event
        bot.eventManager.addEventListener(
            EventListener.new()
            .add_event("ready")
            .set_callback(lambda bot: setattr(Management, 'startup_time', time.time()))
        )
    
    @staticmethod
    async def ping(data):
        """Handle ping command."""
        try:
            message_tx = time.time() * 1000
            
            # Get message timestamp from Discord snowflake
            message_id = data.message.id
            # Discord snowflake timestamp calculation
            discord_epoch = 1420070400000
            snowflake_timestamp = ((message_id >> 22) + discord_epoch) / 1000
            dstamp_tx = snowflake_timestamp * 1000
            
            reply = await data.message.reply("Pong!")
            
            message_rx = time.time() * 1000
            dstamp_rx = ((reply.id >> 22) + discord_epoch) / 1000 * 1000
            
            artemis_ping = f"{(message_rx - message_tx):.0f}"
            discord_ping = f"{(dstamp_rx - dstamp_tx):.0f}"
            
            await reply.edit(f"Pong!\n{artemis_ping}ms ping (artemis-rx)\n{discord_ping}ms ping (msg-snowflake)")
        except Exception as e:
            await Management.exception_handler(data.message, e)
    
    @staticmethod
    async def info(data):
        """Handle info command."""
        try:
            embed = Embed(title="Artemis Bot Information")
            
            # Memory usage
            import psutil
            process = psutil.Process(os.getpid())
            memory_mb = process.memory_info().rss / 1024 / 1024
            embed.add_field(name="Memory usage", value=f"{memory_mb:.2f} MiB", inline=True)
            
            # Python version
            embed.add_field(name="Python", value=sys.version.split()[0], inline=True)
            
            # PID / User
            embed.add_field(name="PID / User", value=f"{os.getpid()} / {os.getenv('USER', 'unknown')}", inline=True)
            
            # Guilds / Channels / Users
            guild_count = len(data.artemis.guilds)
            channel_count = sum(len(guild.channels) for guild in data.artemis.guilds)
            user_count = len(data.artemis.users)
            embed.add_field(
                name="Guilds / Channels / (loaded) Users",
                value=f"{guild_count} / {channel_count} / {user_count}",
                inline=False
            )
            
            # Version (git commit if available) with emoji hash
            version = Management.git_version()
            version_hash = emoji_hash(f"artemis-{__version__}-{version}")
            embed.add_field(name="Artemis", value=f"{version} {version_hash}", inline=False)
            
            # System
            import platform
            embed.add_field(name="System", value=platform.platform(), inline=False)
            
            # Uptime
            if Management.startup_time:
                uptime_seconds = time.time() - Management.startup_time
                uptime_delta = timedelta(seconds=int(uptime_seconds))
                uptime_str = str(uptime_delta)
                connected_time = datetime.fromtimestamp(Management.startup_time).isoformat()
                embed.add_field(
                    name="Uptime",
                    value=f"{uptime_str} - *(connected {connected_time})*",
                    inline=False
                )
            
            # Loaded plugins with emoji hashes
            plugins = Management.get_plugins(data.artemis)
            if plugins:
                plugins_with_hashes = []
                for plugin_name in plugins:
                    plugin_hash = emoji_hash(f"plugin-{plugin_name}")
                    plugins_with_hashes.append(f"{plugin_name} {plugin_hash}")
                
                plugins_text = "\n".join(plugins_with_hashes)
                # Split if too long
                if len(plugins_text) > 1024:
                    chunks = [plugins_text[i:i+1024] for i in range(0, len(plugins_text), 1024)]
                    for i, chunk in enumerate(chunks):
                        embed.add_field(
                            name="Loaded Plugins" if i == 0 else "Loaded Plugins (cont.)",
                            value=chunk,
                            inline=False
                        )
                else:
                    embed.add_field(name="Loaded Plugins", value=plugins_text, inline=False)
            
            # Dependencies
            deps = Management.get_dependencies()
            if deps:
                deps_text = "\n".join([f"{name} ({version})" for name, version in deps.items()])
                if len(deps_text) > 1024:
                    chunks = [deps_text[i:i+1024] for i in range(0, len(deps_text), 1024)]
                    for i, chunk in enumerate(chunks):
                        embed.add_field(
                            name="Dependencies" if i == 0 else "Dependencies (cont.)",
                            value=chunk,
                            inline=False
                        )
                else:
                    embed.add_field(name="Dependencies", value=deps_text, inline=False)
            
            await data.message.channel.send(embed=embed)
        except Exception as e:
            await Management.exception_handler(data.message, e, True)
    
    @staticmethod
    async def restart(data):
        """Handle restart command."""
        admin_ids = getattr(data.artemis.config, 'ADMIN_USER_IDS', [])
        if str(data.message.author.id) not in admin_ids:
            await Management.unauthorized(data.message)
            return
        
        await data.message.channel.send("🃏🔫")
        # Exit with code 1 to trigger restart (if using a process manager)
        sys.exit(1)
    
    @staticmethod
    async def update(data):
        """Handle update command."""
        admin_ids = getattr(data.artemis.config, 'ADMIN_USER_IDS', [])
        if str(data.message.author.id) not in admin_ids:
            await Management.unauthorized(data.message)
            return
        
        try:
            # Try to run git pull
            result = Management.git_pull()
            await data.message.channel.send(f"```\n{result}\n```")
        except Exception as e:
            await Management.exception_handler(data.message, e, True)
    
    @staticmethod
    async def invite(data):
        """Handle invite command."""
        try:
            # Generate OAuth invite URL
            oauth_url = disnake.utils.oauth_url(
                client_id=data.artemis.user.id,
                permissions=disnake.Permissions(administrator=True),
                scopes=["bot", "applications.commands"]
            )
            await data.message.channel.send(
                f"Use the following URL to add this Artemis instance to your server!\n<{oauth_url}>"
            )
        except Exception as e:
            await Management.exception_handler(data.message, e)
    
    @staticmethod
    def git_pull() -> str:
        """Execute git pull and return output."""
        try:
            if os.name == 'nt':  # Windows
                result = subprocess.run(
                    ['git', 'pull'],
                    capture_output=True,
                    text=True,
                    cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                )
            else:  # Unix-like
                result = subprocess.run(
                    ['./update'],
                    capture_output=True,
                    text=True,
                    cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
                )
            
            return result.stdout + result.stderr
        except Exception as e:
            return f"Error: {str(e)}"
    
    @staticmethod
    def git_version() -> str:
        """Get git version/commit."""
        try:
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                capture_output=True,
                text=True,
                cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            )
            commit = result.stdout.strip()
            return f"[{commit[:7]}](https://github.com/artemis/commit/{commit})"
        except:
            return "unknown"
    
    @staticmethod
    def get_plugins(bot) -> list:
        """Get list of loaded plugins."""
        plugins = []
        for plugin_class in bot.plugin_loader.loaded_plugins:
            plugins.append(plugin_class.__name__)
        return plugins
    
    @staticmethod
    def get_dependencies() -> dict:
        """Get Python package dependencies."""
        try:
            deps = {}
            # Get packages from requirements.txt or installed packages
            dists = importlib.metadata.distributions()
            for dist in dists:
                deps[dist.metadata['Name']] = dist.version
            return deps
        except:
            return {}
