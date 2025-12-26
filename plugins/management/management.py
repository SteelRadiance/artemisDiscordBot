"""
Copyright 2025, Vijay Challa - Use of this source code follows the MIT license found in the LICENSE file.

Management Plugin - Bot management commands

This plugin provides core bot administration commands including ping testing,
bot information display, and invite link
generation. It shows system statistics, loaded plugins, dependencies, and
bot status information.

Commands:
    !ping - Test bot latency
    !artemis - Display bot information and statistics
    !help - List all commands available to the user
    # !restart - Restart the bot (admin only) - DISABLED
    # !update - Pull latest code from git (admin only) - DISABLED
    !invite - Generate bot invite URL
    !talkingstick - Request the talking stick (notifies staff)
    !talkingstick role <role_id> - Set staff role for talking stick (admin only)
    !vc - Manually trigger voice channel name changes

Features:
    - Ping measurement using Discord snowflake timestamps
    - Comprehensive bot info: memory, Python version, uptime, guild/channel counts
    - Plugin listing with emoji-based version hashes
    - Dependency version display
    - OAuth invite URL generation with proper permissions
    - Talking stick: Relays requests to staff using observer channel and configurable staff role
    - Voice channel naming: Automatically renames empty voice channels with names from data files
"""

import time
import os
import sys
import subprocess
import asyncio
import importlib.metadata
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path
import random
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
        
        Management.startup_time = time.time()
        
        bot.eventManager.add_listener(
            EventListener.new()
            .add_command("ping")
            .set_callback(Management.ping)
            .set_help("**Usage**: `!ping`\n\nTests bot latency by measuring response time.")
        )
        
        bot.eventManager.add_listener(
            EventListener.new()
            .add_command("artemis")
            .set_callback(Management.info)
            .set_help("**Usage**: `!artemis`\n\nDisplays bot information including memory usage, Python version, uptime, guild/channel counts, loaded plugins, and dependencies.")
        )
        
        # bot.eventManager.add_listener(
        #     EventListener.new()
        #     .add_command("restart")
        #     .set_callback(Management.restart)
        #     .set_help("**Usage**: `!restart`\n\nRestarts the bot. (Admin only)")
        # )
        
        # bot.eventManager.add_listener(
        #     EventListener.new()
        #     .add_command("update")
        #     .set_callback(Management.update)
        #     .set_help("**Usage**: `!update`\n\nPulls the latest code from git. (Admin only)")
        # )
        
        bot.eventManager.add_listener(
            EventListener.new()
            .add_command("invite")
            .set_callback(Management.invite)
            .set_help("**Usage**: `!invite`\n\nGenerates a bot invite URL with the required permissions.")
        )
        
        bot.eventManager.add_listener(
            EventListener.new()
            .add_command("help")
            .set_callback(Management.help)
            .set_help("**Usage**: `!help`\n\nLists all commands available to you, organized by category with descriptions.")
        )
        
        bot.eventManager.add_listener(
            EventListener.new()
            .add_command("talkingstick")
            .set_callback(Management.talkingstick)
            .set_help("**Usage**: `!talkingstick` or `!talkingstick role <role_id>`\n\nRequest the talking stick (notifies staff). Admins can use `!talkingstick role <role_id>` to set the staff role to ping.")
        )
        
        bot.eventManager.add_listener(
            EventListener.new()
            .add_command("vc")
            .set_callback(Management.voice_chat)
            .set_help("**Usage**: `!vc`\n\nManually trigger voice channel name changes. Requires permission `p.management.changevc`.")
        )
        
        bot.eventManager.add_listener(
            EventListener.new()
            .set_periodic(60 * 60)
            .set_callback(Management.voice_chat_change)
        )
        
        bot.eventManager.add_listener(
            EventListener.new()
            .add_event("ready")
            .set_callback(lambda bot: setattr(Management, 'startup_time', time.time()))
        )
    
    @staticmethod
    async def ping(data):
        """Handle ping command."""
        try:
            message_tx = time.time() * 1000
            
            message_id = data.message.id
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
            args = Management.split_command(data.message.content)
            show_dependencies = "-dependencies" in args
            
            embed = Embed(title="Artemis Bot Information")
            
            import psutil
            process = psutil.Process(os.getpid())
            memory_mb = process.memory_info().rss / 1024 / 1024
            embed.add_field(name="Memory usage", value=f"{memory_mb:.2f} MiB", inline=True)
            
            embed.add_field(name="Python", value=sys.version.split()[0], inline=True)
            
            embed.add_field(name="PID / User", value=f"{os.getpid()} / {os.getenv('USER', 'unknown')}", inline=True)
            
            guild_count = len(data.artemis.guilds)
            channel_count = sum(len(guild.channels) for guild in data.artemis.guilds)
            user_count = len(data.artemis.users)
            embed.add_field(
                name="Guilds / Channels / (loaded) Users",
                value=f"{guild_count} / {channel_count} / {user_count}",
                inline=False
            )
            
            version = Management.git_version()
            version_hash = emoji_hash(f"artemis-{__version__}-{version}")
            embed.add_field(name="Artemis", value=f"{version} {version_hash}", inline=False)
            
            import platform
            embed.add_field(name="System", value=platform.platform(), inline=False)
            
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
            
            plugins = Management.get_plugins(data.artemis)
            if plugins:
                plugins_with_hashes = []
                for plugin_name in plugins:
                    plugin_hash = emoji_hash(f"plugin-{plugin_name}")
                    plugins_with_hashes.append(f"{plugin_name} {plugin_hash}")
                
                plugins_text = "\n".join(plugins_with_hashes)
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
            
            if show_dependencies:
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
    
    # @staticmethod
    # async def restart(data):
    #     """Handle restart command."""
    #     admin_ids = getattr(data.artemis.config, 'ADMIN_USER_IDS', [])
    #     if str(data.message.author.id) not in admin_ids:
    #         await Management.unauthorized(data.message)
    #         return
    #     
    #     await data.message.channel.send("🃏🔫")
    #     
    #     # Get the path to main.py (project root)
    #     project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    #     main_script = os.path.join(project_root, "main.py")
    #     
    #     # Get Python executable
    #     python_exe = sys.executable
    #     
    #     try:
    #         # Set environment variable to indicate this is a restart
    #         env = os.environ.copy()
    #         env['ARTEMIS_RESTART'] = '1'
    #         
    #         # Spawn a new process to restart the bot
    #         if os.name == 'nt':  # Windows
    #             # On Windows, use CREATE_NEW_CONSOLE to spawn in a new console window
    #             subprocess.Popen(
    #                 [python_exe, main_script],
    #                 cwd=project_root,
    #                 env=env,
    #                 creationflags=subprocess.CREATE_NEW_CONSOLE,
    #                 stdout=subprocess.DEVNULL,
    #                 stderr=subprocess.DEVNULL
    #             )
    #         else:  # Unix-like systems
    #             # On Unix, detach the process so it continues after parent exits
    #             subprocess.Popen(
    #                 [python_exe, main_script],
    #                 cwd=project_root,
    #                 env=env,
    #                 start_new_session=True,
    #                 stdout=subprocess.DEVNULL,
    #                 stderr=subprocess.DEVNULL
    #             )
    #     except Exception as e:
    #         logger.error(f"Failed to restart bot: {e}")
    #         await data.message.channel.send(f"❌ Failed to restart: {str(e)}")
    #         return
    #     
    #     # Give the new process a moment to start
    #     await asyncio.sleep(0.5)
    #     
    #     # Properly close the bot connection before exiting
    #     # Create a task to close and exit, so we don't block the current handler
    #     async def shutdown_and_exit():
    #         try:
    #             await data.artemis.close()
    #         except Exception as e:
    #             logger.error(f"Error during bot shutdown: {e}")
    #         finally:
    #             # Use os._exit instead of sys.exit to avoid the task exception issue
    #             os._exit(0)
    #     
    #     # Schedule the shutdown task
    #     asyncio.create_task(shutdown_and_exit())
    
    # @staticmethod
    # async def update(data):
    #     """Handle update command."""
    #     admin_ids = getattr(data.artemis.config, 'ADMIN_USER_IDS', [])
    #     if str(data.message.author.id) not in admin_ids:
    #         await Management.unauthorized(data.message)
    #         return
    #     
    #     try:
    #         result = Management.git_pull()
    #         await data.message.channel.send(f"```\n{result}\n```")
    #     except Exception as e:
    #         await Management.exception_handler(data.message, e, True)
    
    @staticmethod
    async def invite(data):
        """Handle invite command."""
        try:
            admin_ids = getattr(data.artemis.config, 'ADMIN_USER_IDS', [])
            if str(data.message.author.id) not in admin_ids:
                await Management.unauthorized(data.message)
                return
            
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
    async def help(data):
        """Handle help command - list all available commands for the user."""
        try:
            command_info = {
                "ping": (None, True, "Test bot latency", "Management"),
                "artemis": (None, True, "Display bot information and statistics", "Management"),
                "help": (None, True, "List all available commands", "Management"),
                "invite": (None, False, "Generate bot invite URL (admin only)", "Management"),
                # "restart": (None, False, "Restart the bot (admin only)", "Management"),
                # "update": (None, False, "Pull latest code from git (admin only)", "Management"),
                
                "user": (None, True, "Get user information", "User"),
                "roster": ("p.userutils.roster", True, "List members with a role", "User"),
                "av": (None, True, "Get user avatar URL", "User"),
                
                "role": ("p.roles.toggle", True, "Toggle a role or list available roles", "Role"),
                "roles": ("p.roles.list", True, "List all self-assignable roles", "Role"),
                "bindrole": ("p.roles.bind", False, "Make a role self-assignable (admin)", "Role"),
                
                "remind": (None, True, "Set a reminder (use !remind delete <id> to remove)", "Remind"),
                "rem": (None, True, "Set a reminder (short)", "Remind"),
                "remindme": (None, True, "Set a reminder", "Remind"),
                "reminder": (None, True, "Set a reminder", "Remind"),
                
                "agenda": (None, True, "Tally votes on a staff motion", "Agenda"),
                
                "state": ("p.moderation.state", False, "Post moderation statement", "State"),
                
                "archive": (None, False, "Archive a channel (admin only)", "Archive"),
                
                "gamesbot": (None, True, "Game tagging system (add/remove/list/ping)", "GamesBot"),
                "gamebot": (None, True, "Game tagging system (short)", "GamesBot"),
                "gb": (None, True, "Game tagging system (short)", "GamesBot"),
                
                "match": (None, True, "Create or manage matches (some subcommands require manage_roles or admin)", "MatchVoting"),
                "tally": (None, True, "View match voting results", "MatchVoting"),
                
                "observer": (None, False, "Configure moderation logging (admin)", "Observer"),
                
                "timezone": (None, True, "Set or view your timezone", "Localization"),
                "time": (None, True, "Convert time to all timezones", "Localization"),
                
                "auditlog": (None, True, "View audit log entries (sent via DM)", "AuditLog"),
                
                "permission": (None, True, "Check or manage permissions", "Permission"),
                "perm": (None, True, "Check or manage permissions (short)", "Permission"),
                "hpm": (None, True, "Check or manage permissions (short)", "Permission"),
                
                "talkingstick": (None, True, "Request talking stick", "Management"),
                "vc": ("p.management.changevc", False, "Change voice channel name", "Management"),
            }
            
            all_commands = set(data.artemis.eventManager.command_listeners.keys())
            
            available_commands = {}
            admin_ids = getattr(data.artemis.config, 'ADMIN_USER_IDS', [])
            is_admin = str(data.message.author.id) in admin_ids
            
            for cmd in sorted(all_commands):
                if cmd not in command_info:
                    available_commands.setdefault("Other", []).append(f"`!{cmd}`")
                    continue
                
                perm_str, default_allowed, description, category = command_info[cmd]
                
                has_permission = False
                if is_admin:
                    has_permission = True
                elif perm_str is None:
                    has_permission = default_allowed
                else:
                    p = Permission(perm_str, data.artemis, default_allowed)
                    p.add_message_context(data.message)
                    has_permission = await p.resolve()
                
                if has_permission:
                    available_commands.setdefault(category, []).append(f"`!{cmd}` - {description}")
            
            embed = Embed(
                title="Available Commands",
                description=f"Commands available to {data.message.author.display_name}",
                color=data.message.author.color if data.message.author.color else 0x00ff00
            )
            
            if available_commands:
                for category in sorted(available_commands.keys()):
                    commands_list = available_commands[category]
                    if len("\n".join(commands_list)) > 1024:
                        chunks = []
                        current_chunk = []
                        current_length = 0
                        for cmd in commands_list:
                            if current_length + len(cmd) + 1 > 1024:
                                chunks.append("\n".join(current_chunk))
                                current_chunk = [cmd]
                                current_length = len(cmd)
                            else:
                                current_chunk.append(cmd)
                                current_length += len(cmd) + 1
                        if current_chunk:
                            chunks.append("\n".join(current_chunk))
                        
                        for i, chunk in enumerate(chunks):
                            embed.add_field(
                                name=category if i == 0 else f"{category} (cont.)",
                                value=chunk,
                                inline=False
                            )
                    else:
                        embed.add_field(
                            name=category,
                            value="\n".join(commands_list),
                            inline=False
                        )
            else:
                embed.description = "No commands available."
            
            embed.set_footer(text=f"Use !help to see this list again. Prefix: {data.artemis.config.COMMAND_PREFIX}")
            
            try:
                dm_channel = await data.message.author.create_dm()
                await dm_channel.send(embed=embed)
                await data.message.reply("📬 I've sent the command list to your DMs!")
            except:
                await data.message.reply(embed=embed)
        except Exception as e:
            await Management.exception_handler(data.message, e, True)
    
    # @staticmethod
    # def git_pull() -> str:
    #     """Execute git pull and return output."""
    #     try:
    #         if os.name == 'nt':  # Windows
    #             result = subprocess.run(
    #                 ['git', 'pull'],
    #                 capture_output=True,
    #                 text=True,
    #                 cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    #             )
    #         else:  # Unix-like
    #             result = subprocess.run(
    #                 ['./update'],
    #                 capture_output=True,
    #                 text=True,
    #                 cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    #             )
    #         
    #         return result.stdout + result.stderr
    #     except Exception as e:
    #         return f"Error: {str(e)}"
    
    @staticmethod
    def git_version() -> str:
        """Get git version/commit."""
        try:
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                capture_output=True,
                text=True,
                cwd=project_root
            )
            commit = result.stdout.strip()
            
            remote_result = subprocess.run(
                ['git', 'remote', 'get-url', 'origin'],
                capture_output=True,
                text=True,
                cwd=project_root
            )
            remote_url = remote_result.stdout.strip()
            
            if remote_url.startswith('git@github.com:'):
                repo = remote_url.replace('git@github.com:', '').replace('.git', '')
            elif remote_url.startswith('https://github.com/'):
                repo = remote_url.replace('https://github.com/', '').replace('.git', '')
            else:
                repo = 'SteelRadiance/artemisDiscordBot'
            
            return f"[{commit[:7]}](https://github.com/{repo}/commit/{commit})"
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
            dists = importlib.metadata.distributions()
            for dist in dists:
                deps[dist.metadata['Name']] = dist.version
            return deps
        except:
            return {}
    
    @staticmethod
    async def get_staff_role_id(guild: disnake.Guild) -> Optional[int]:
        """Get the configured staff role ID for talking stick."""
        try:
            storage = guild._state._get_client().storage if hasattr(guild._state, '_get_client') else None
            if not storage:
                return None
            
            info = await storage.get("talkingstick", str(guild.id))
            if info and isinstance(info, dict) and info.get("staff_role_id"):
                return int(info["staff_role_id"])
            return None
        except:
            return None
    
    @staticmethod
    async def set_staff_role(guild: disnake.Guild, role_id: int):
        """Set the staff role ID for talking stick."""
        try:
            storage = guild._state._get_client().storage if hasattr(guild._state, '_get_client') else None
            if not storage:
                return False
            
            await storage.set("talkingstick", str(guild.id), {
                "guild_id": str(guild.id),
                "staff_role_id": str(role_id)
            })
            return True
        except Exception as e:
            logger.error(f"Failed to set staff role: {e}")
            return False
    
    @staticmethod
    async def get_observer_channel(guild: disnake.Guild) -> Optional[disnake.TextChannel]:
        """Get the observer channel for this guild."""
        try:
            from plugins.observer.observer import Observer
            info = await Observer.get_info(guild)
            if info and info.get("channel_id"):
                channel = guild.get_channel(int(info["channel_id"]))
                return channel
            return None
        except Exception as e:
            logger.error(f"Failed to get observer channel: {e}")
            return None
    
    @staticmethod
    async def talkingstick(data):
        """Handle talking stick command."""
        try:
            if not data.guild:
                await data.message.reply("This command can only be used in a server.")
                return
            
            args = Management.split_command(data.message.content)
            
            # Check if this is a config command (role flag)
            if len(args) > 1 and args[1].lower() == "role":
                # Admin-only configuration
                admin_ids = getattr(data.artemis.config, 'ADMIN_USER_IDS', [])
                if str(data.message.author.id) not in admin_ids:
                    await Management.unauthorized(data.message)
                    return
                
                if len(args) < 3:
                    await data.message.reply("Usage: `!talkingstick role <role_id>` or `!talkingstick role @Role`")
                    return
                
                # Parse role
                role_id = None
                try:
                    role_id = int(args[2])
                except ValueError:
                    # Try to parse as role mention or name
                    role = Management.parse_role(data.guild, args[2])
                    if not role:
                        await data.message.reply("Role not found. Use a role ID, mention (@Role), or role name.")
                        return
                    role_id = role.id
                
                # Verify role exists
                role = data.guild.get_role(role_id)
                if not role:
                    await data.message.reply("Role not found.")
                    return
                
                # Save the role
                if await Management.set_staff_role(data.guild, role_id):
                    await data.message.reply(f"✅ Staff role set to {role.mention} for talking stick notifications.")
                else:
                    await data.message.reply("❌ Failed to save staff role configuration.")
                return
            
            # Get observer channel (same channel observer uses)
            observer_channel = await Management.get_observer_channel(data.guild)
            if not observer_channel:
                await data.message.reply("⚠️ Talking stick is not configured. An admin needs to set up the observer channel first using `!observer <channel_id>`.")
                return
            
            # Get staff role
            staff_role_id = await Management.get_staff_role_id(data.guild)
            if not staff_role_id:
                await data.message.reply("⚠️ No staff role configured. An admin needs to set one using `!talkingstick role <role_id>`.")
                return
            
            staff_role = data.guild.get_role(staff_role_id)
            if not staff_role:
                await data.message.reply("⚠️ Configured staff role no longer exists. An admin needs to reconfigure it.")
                return
            
            # Send notification to observer channel
            member = data.guild.get_member(data.message.author.id) if data.guild else None
            member_mention = member.mention if member else data.message.author.mention
            
            await observer_channel.send(
                f"{staff_role.mention}: {member_mention} has asked for the talking stick!"
            )
            
            try:
                dm_channel = await data.message.author.create_dm()
                await dm_channel.send("Your request to get the Talking Stick has been relayed to staff.")
            except:
                await data.message.channel.send("Your request to get the Talking Stick has been relayed to staff.")
            
            await data.message.delete()
        except Exception as e:
            await Management.exception_handler(data.message, e)
    
    @staticmethod
    async def voice_chat(data):
        """Handle voice chat command."""
        try:
            p = Permission("p.management.changevc", data.artemis, False)
            p.add_message_context(data.message)
            if not await p.resolve():
                await p.send_unauthorized_message(data.message.channel)
                return
            
            await Management.voice_chat_change(data.artemis)
            await data.message.add_reaction("😤")
        except Exception as e:
            await Management.exception_handler(data.message, e)
    
    @staticmethod
    async def voice_chat_change(bot):
        """Change voice channel names."""
        try:
            # This is a generic implementation - can be customized per guild if needed
            for guild in bot.guilds:
                # Skip if no voice channels
                if not guild.voice_channels:
                    continue
                
                # Find empty voice channels (can be customized per guild)
                empty_channels = [
                    ch for ch in guild.voice_channels
                    if len(ch.members) == 0
                ]
                
                if not empty_channels:
                    continue
                
                # Try to load track names from data file (guild-specific or generic)
                tracks = []
                tracks_file = Path(f"data/{guild.id}.txt")
                if not tracks_file.exists():
                    tracks_file = Path("data/voice_channels.txt")
                if not tracks_file.exists():
                    tracks_file = Path("data/ironreach.txt")  # Fallback to ironreach
                
                try:
                    if tracks_file.exists():
                        with open(tracks_file, 'r', encoding='utf-8') as f:
                            tracks = [line.strip() for line in f if line.strip()]
                except:
                    pass
                
                if not tracks:
                    # Skip if no track names available
                    continue
                
                selected_tracks = random.sample(tracks, min(len(empty_channels), len(tracks)))
                
                for channel, track_name in zip(empty_channels, selected_tracks):
                    try:
                        await channel.edit(name=track_name)
                    except Exception as e:
                        logger.warning(f"Failed to rename channel {channel.name} in {guild.name}: {e}")
        except Exception as e:
            logger.error(f"Error in voice_chat_change: {e}")
