"""
Copyright 2025, Vijay Challa - Use of this source code follows the MIT license found in the LICENSE file.

AuditLog Plugin - Tracks and logs Discord audit log events

This plugin monitors Discord's audit log for all guilds the bot is in using the
on_audit_log_entry_create gateway event. It posts event summaries to a configured
logging channel, allowing real-time monitoring of moderation actions, role changes,
channel modifications, and other server events.

Commands:
    !auditlog <channel_id> - Set the logging channel for audit log events

Features:
    - Real-time tracking of audit log entries via gateway events
    - Posts event summaries to a configured channel
    - Tracks all audit log action types (bans, role changes, channel edits, etc.)
    - Detailed embed formatting for all audit log events
    - Per-guild configuration for logging channels
    - No rate limiting needed (uses gateway events instead of API polling)
"""

import logging
import disnake
from disnake import Embed
from datetime import datetime
from typing import Optional, Dict, Any

from artemis.plugin.base import PluginInterface, PluginHelper
from artemis.events.listener import EventListener
from artemis.utils.helpers import emoji_hash

logger = logging.getLogger("artemis.plugin.auditlog")


class AuditLog(PluginInterface, PluginHelper):
    """Audit log monitoring plugin."""
    
    @staticmethod
    def register(bot):
        """Register the plugin."""
        if AuditLog.is_testing_client(bot):
            bot.log.info("Not adding audit log monitoring on testing.")
            return
        
        bot.eventManager.add_listener(
            EventListener.new()
            .add_command("auditlog")
            .set_callback(AuditLog.config)
            .set_help("**Usage**: `!auditlog <channel_id>`\n\nConfigure the audit log logging channel. This command is admin only. The audit log plugin automatically logs moderation actions, role changes, channel modifications, and other server events to the configured channel. Each event is numbered sequentially and includes an emoji-based hash for verification.")
        )
        
        @bot.event
        async def on_audit_log_entry_create(entry: disnake.AuditLogEntry):
            await AuditLog.handle_audit_log_entry(bot, entry)
    
    @staticmethod
    async def get_info(guild: disnake.Guild, bot=None) -> Optional[Dict[str, Any]]:
        """Get audit log configuration for guild."""
        try:
            if bot and hasattr(bot, 'storage'):
                storage = bot.storage
            else:
                # Fall back to getting storage from guild state
                storage = guild._state._get_client().storage if hasattr(guild._state, '_get_client') else None
            
            if not storage:
                return None
            
            info = await storage.get("auditlog", str(guild.id))
            return info if isinstance(info, dict) else None
        except Exception as e:
            logger.warning(f"Failed to get audit log info for guild {guild.id}: {e}")
            return None
    
    @staticmethod
    async def config(data):
        """Handle auditlog config command."""
        try:
            admin_ids = getattr(data.artemis.config, 'ADMIN_USER_IDS', [])
            if str(data.message.author.id) not in admin_ids:
                await AuditLog.unauthorized(data.message)
                return
            
            if not data.guild:
                await data.message.channel.send("This command can only be used in a server, not in DMs.")
                return
            
            args = AuditLog.split_command(data.message.content)
            if len(args) != 2:
                await data.message.channel.send("Malformed command. Usage: `!auditlog <channel_id>`")
                return
            
            try:
                channel_id = int(args[1])
                channel = data.message.guild.get_channel(channel_id)
                if channel:
                    await AuditLog.set_logging_channel(data.message.guild, channel)
                    await data.message.channel.send(f"{channel.mention} set as audit log channel for guild `{data.message.guild.name}`")
                else:
                    await data.message.channel.send("Invalid channel ID. Please provide a valid channel ID.")
            except ValueError:
                await data.message.channel.send("Invalid channel ID. Please provide a valid channel ID.")
        except Exception as e:
            await AuditLog.exception_handler(data.message, e)
    
    @staticmethod
    async def set_logging_channel(guild: disnake.Guild, channel: disnake.TextChannel):
        """Set logging channel for audit log events."""
        try:
            storage = guild._state._get_client().storage if hasattr(guild._state, '_get_client') else None
            if storage:
                info = await storage.get("auditlog", str(guild.id))
                event_counter = info.get("event_counter", 0) if isinstance(info, dict) else 0
                
                await storage.set("auditlog", str(guild.id), {
                    "guild_id": str(guild.id),
                    "channel_id": str(channel.id),
                    "event_counter": event_counter
                })
        except Exception as e:
            logger.error(f"Failed to set audit log channel: {e}")
    
    @staticmethod
    async def get_and_increment_event_counter(guild: disnake.Guild, bot) -> int:
        """Get the current event counter and increment it for the next event."""
        try:
            storage = bot.storage if bot and hasattr(bot, 'storage') else None
            if not storage:
                storage = guild._state._get_client().storage if hasattr(guild._state, '_get_client') else None
            
            if not storage:
                return 1
            
            info = await storage.get("auditlog", str(guild.id))
            if not info or not isinstance(info, dict):
                event_counter = 1
                info = {"guild_id": str(guild.id), "event_counter": event_counter}
            else:
                event_counter = info.get("event_counter", 0) + 1
                info["event_counter"] = event_counter
            
            await storage.set("auditlog", str(guild.id), info)
            return event_counter
        except Exception as e:
            logger.error(f"Failed to get/increment event counter for guild {guild.id}: {e}")
            return 1
    
    @staticmethod
    async def handle_audit_log_entry(bot, entry: disnake.AuditLogEntry):
        """Handle a new audit log entry from the gateway event."""
        try:
            if not entry.guild:
                return
            
            action_name = entry.action.name.lower()
            if 'invite' in action_name and 'create' in action_name:
                return
            
            if entry.user and entry.user.id == bot.user.id:
                if 'channel' in action_name and ('update' in action_name or 'change' in action_name):
                    if entry.target and isinstance(entry.target, disnake.VoiceChannel):
                        if entry.after:
                            for key, value in entry.after:
                                if key == 'name':
                                    return  # Skip voice channel name changes by Artemis
            
            info = await AuditLog.get_info(entry.guild, bot)
            if not info or not info.get("channel_id"):
                return
            
            channel = entry.guild.get_channel(int(info["channel_id"]))
            if not channel:
                return
            
            event_number = await AuditLog.get_and_increment_event_counter(entry.guild, bot)
            
            event_time = entry.created_at if entry.created_at else datetime.now()
            event_time_str = event_time.isoformat()
            hash_input = f"{event_number}:{event_time_str}"
            event_hash = emoji_hash(hash_input)
            
            embed = AuditLog.create_audit_log_embed(entry, event_number, event_hash)
            await channel.send(embed=embed)
            
            logger.debug(f"Logged audit log entry {entry.id} (#{event_number}) for guild {entry.guild.name}")
        except Exception as e:
            logger.error(f"Error handling audit log entry: {e}", exc_info=True)
    
    @staticmethod
    def create_audit_log_embed(entry: disnake.AuditLogEntry, event_number: int, event_hash: str) -> Embed:
        """Create an embed from an audit log entry."""
        color = 0x3498db
        
        action_name = entry.action.name.lower()
        if 'ban' in action_name or 'kick' in action_name or 'prune' in action_name:
            color = 0xe74c3c  # Red for bans/kicks
        elif 'unban' in action_name or 'welcome' in action_name:
            color = 0x2ecc71  # Green for unbans/welcomes
        elif 'role' in action_name or 'permission' in action_name:
            color = 0xf39c12  # Orange for role/permission changes
        elif 'channel' in action_name or 'overwrite' in action_name:
            color = 0x9b59b6  # Purple for channel changes
        elif 'update' in action_name or 'change' in action_name:
            color = 0x3498db  # Blue for updates
        elif 'delete' in action_name:
            color = 0xe67e22  # Dark orange for deletions
        elif 'create' in action_name:
            color = 0x1abc9c  # Teal for creations
        
        embed = Embed(
            title=f"Audit Log: {entry.action.name.replace('_', ' ').title()}",
            color=color,
            timestamp=entry.created_at if entry.created_at else datetime.now()
        )
        
        # Event number and hash
        embed.add_field(name="Event #", value=str(event_number), inline=True)
        embed.add_field(name="Hash", value=event_hash, inline=True)
        
        # User who performed the action
        if entry.user:
            embed.set_author(
                name=f"{entry.user.name}#{getattr(entry.user, 'discriminator', '')}",
                icon_url=entry.user.display_avatar.url
            )
        
        # Target of the action
        if entry.target:
            target_name = "Unknown"
            if isinstance(entry.target, disnake.Member):
                target_name = f"{entry.target.name}#{getattr(entry.target, 'discriminator', '')}"
            elif isinstance(entry.target, disnake.User):
                target_name = f"{entry.target.name}#{getattr(entry.target, 'discriminator', '')}"
            elif isinstance(entry.target, disnake.Role):
                target_name = f"@{entry.target.name}"
            elif isinstance(entry.target, disnake.abc.GuildChannel):
                target_name = f"#{entry.target.name}"
            elif hasattr(entry.target, 'name'):
                target_name = str(entry.target.name)
            else:
                target_name = f"ID: {entry.target.id}"
            
            embed.add_field(name="Target", value=target_name, inline=True)
            embed.add_field(name="Target ID", value=str(entry.target.id), inline=True)
        
        # Reason
        if entry.reason:
            embed.add_field(name="Reason", value=entry.reason[:1024], inline=False)
        
        # Changes
        changes = AuditLog._format_changes(entry)
        if changes:
            embed.add_field(name="Changes", value=changes[:1024], inline=False)
        
        footer_parts = [f"Event #{event_number}"]
        if entry.id:
            footer_parts.append(f"Entry ID: {entry.id}")
        footer_parts.append(f"Action Type: {entry.action.value}")
        embed.set_footer(text=" | ".join(footer_parts))
        
        return embed
    
    @staticmethod
    def _format_changes(entry: disnake.AuditLogEntry) -> str:
        """Format audit log changes as a readable string."""
        if not entry.before and not entry.after:
            return ""
        
        changes_lines = []
        
        try:
            before_dict = {}
            after_dict = {}
            
            if entry.before:
                for key, value in entry.before:
                    before_dict[key] = value
            
            if entry.after:
                for key, value in entry.after:
                    after_dict[key] = value
            
            all_keys = set(before_dict.keys()) | set(after_dict.keys())
            
            for key in all_keys:
                old_value = before_dict.get(key)
                new_value = after_dict.get(key)
                
                old_str = AuditLog._format_change_value(old_value)
                new_str = AuditLog._format_change_value(new_value)
                
                changes_lines.append(f"**{key.replace('_', ' ').title()}**: `{old_str}` → `{new_str}`")
        
        except Exception as e:
            logger.debug(f"Error formatting changes from audit log entry {entry.id}: {e}")
            return ""
        
        return "\n".join(changes_lines) if changes_lines else ""
    
    @staticmethod
    def _format_change_value(value: Any) -> str:
        """Format a change value for display."""
        if value is None:
            return "None"
        
        if isinstance(value, bool):
            return "True" if value else "False"
        
        if isinstance(value, (list, tuple)):
            if len(value) == 0:
                return "[]"
            formatted_items = []
            for item in value[:5]:
                formatted_items.append(str(item))
            result = ", ".join(formatted_items)
            if len(value) > 5:
                result += f" (+{len(value) - 5} more)"
            return f"[{result}]"
        
        if isinstance(value, dict):
            return str(value)[:100]  # Limit dict representation
        
        value_str = str(value)
        if len(value_str) > 50:
            return value_str[:47] + "..."
        
        return value_str