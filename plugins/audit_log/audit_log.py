"""
Copyright 2025, Vijay Challa - Use of this source code follows the MIT license found in the LICENSE file.

AuditLog Plugin - Tracks and stores Discord audit log events

This plugin monitors Discord's audit log for all guilds the bot is in using the
on_audit_log_entry_create gateway event. It stores entries persistently, allowing
retrieval of moderation actions, role changes, channel modifications, and other
server events even after they've expired from Discord's audit log.

Commands:
    !auditlog - Output all stored audit log events as JSON
    !auditlog -readable - Output a human-readable audit log

Features:
    - Real-time tracking of audit log entries via gateway events
    - Stores entries persistently in JSON storage
    - Tracks all audit log action types (bans, role changes, channel edits, etc.)
    - Provides programmatic access to historical audit data
    - No rate limiting needed (uses gateway events instead of API polling)
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any
from collections import defaultdict
from datetime import datetime

import disnake

from artemis.plugin.base import PluginInterface, PluginHelper
from artemis.events.listener import EventListener

logger = logging.getLogger("artemis.plugin.auditlog")


class AuditLog(PluginInterface, PluginHelper):
    """Audit log monitoring plugin."""
    
    # In-memory storage: {guild_id: {entry_id: entry_data}}
    _audit_log_storage: Dict[int, Dict[str, Any]] = defaultdict(dict)
    
    @staticmethod
    def register(bot):
        """Register the plugin."""
        if AuditLog.is_testing_client(bot):
            bot.log.info("Not adding audit log monitoring on testing.")
            return
        
        bot.eventManager.add_listener(
            EventListener.new()
            .add_event("ready")
            .set_callback(lambda bot_instance: asyncio.create_task(AuditLog.load_from_storage(bot_instance)))
        )
        
        @bot.event
        async def on_audit_log_entry_create(entry: disnake.AuditLogEntry):
            await AuditLog.handle_audit_log_entry(bot, entry)
        
        bot.eventManager.add_listener(
            EventListener.new()
            .add_command("auditlog")
            .set_callback(AuditLog.output_audit_logs)
        )
    
    @staticmethod
    async def load_from_storage(bot):
        """Load existing audit log entries from JSON storage."""
        try:
            await asyncio.sleep(2)
            
            all_stored = await bot.storage.get_all("audit_log")
            for key, entry_data in all_stored.items():
                parts = key.split('_', 1)
                if len(parts) == 2:
                    try:
                        guild_id = int(parts[0])
                        entry_id = parts[1]
                        
                        if guild_id not in AuditLog._audit_log_storage:
                            AuditLog._audit_log_storage[guild_id] = {}
                        
                        AuditLog._audit_log_storage[guild_id][entry_id] = entry_data
                    except ValueError:
                        continue
            
            total_entries = sum(len(entries) for entries in AuditLog._audit_log_storage.values())
            if total_entries > 0:
                logger.info(f"Loaded {total_entries} audit log entries from storage")
        except Exception as e:
            logger.error(f"Error loading audit logs from storage: {e}", exc_info=True)
    
    @staticmethod
    async def handle_audit_log_entry(bot, entry: disnake.AuditLogEntry):
        """Handle a new audit log entry from the gateway event."""
        try:
            if not entry.guild:
                return
            
            guild_id = entry.guild.id
            entry_id = str(entry.id)
            
            if entry_id in AuditLog._audit_log_storage[guild_id]:
                logger.debug(f"Audit log entry {entry_id} already stored, skipping")
                return
            
            entry_data = {
                'id': entry_id,
                'guild_id': str(guild_id),
                'user_id': str(entry.user.id) if entry.user else None,
                'target_id': str(entry.target.id) if entry.target else None,
                'action': entry.action.name if hasattr(entry.action, 'name') else str(entry.action),
                'action_type': entry.action.value if hasattr(entry.action, 'value') else None,
                'reason': entry.reason,
                'changes': AuditLog._extract_changes(entry),
                'created_at': entry.created_at.isoformat() if entry.created_at else None,
            }
            
            AuditLog._audit_log_storage[guild_id][entry_id] = entry_data
            
            try:
                await bot.storage.set("audit_log", f"{guild_id}_{entry_id}", entry_data)
            except Exception as e:
                logger.warning(f"Failed to persist audit log entry to storage: {e}")
            
            logger.debug(f"Stored new audit log entry {entry_id} for guild {entry.guild.name}")
        except Exception as e:
            logger.error(f"Error handling audit log entry: {e}", exc_info=True)
    
    @staticmethod
    def _extract_changes(entry: disnake.AuditLogEntry) -> List[Dict[str, Any]]:
        """Extract changes from an audit log entry."""
        changes = []
        
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
                
                changes.append({
                    'key': key,
                    'old_value': str(old_value) if old_value is not None else None,
                    'new_value': str(new_value) if new_value is not None else None,
                })
        
        except Exception as e:
            logger.debug(f"Error extracting changes from audit log entry {entry.id}: {e}")
            return []
        
        return changes
    
    @staticmethod
    async def output_audit_logs(data):
        """Output all stored audit log events as JSON or readable format via DM."""
        try:
            if not data.guild:
                await data.message.channel.send("This command can only be used in a server, not in DMs.")
                return
            
            args = AuditLog.split_command(data.message.content)
            readable = len(args) > 1 and args[1].lower() == '-readable'
            
            if readable:
                await AuditLog.output_readable_audit_logs(data)
            else:
                guild_id = data.guild.id
                output = {}
                
                if guild_id in AuditLog._audit_log_storage:
                    output[str(guild_id)] = list(AuditLog._audit_log_storage[guild_id].values())
                else:
                    output[str(guild_id)] = []
                
                import json
                json_output = json.dumps(output, indent=2, ensure_ascii=False)
                
                try:
                    dm_channel = await data.message.author.create_dm()
                    
                    if len(json_output) > 2000:
                        import io
                        file_obj = disnake.File(
                            fp=io.BytesIO(json_output.encode('utf-8')),
                            filename=f"audit_log_{guild_id}.json"
                        )
                        await dm_channel.send("Here is the audit log:", file=file_obj)
                    else:
                        await dm_channel.send(f"```json\n{json_output}\n```")
                    
                    await data.message.channel.send(f"{data.message.author.mention}, I've sent the audit log to your DMs!")
                
                except disnake.Forbidden:
                    await data.message.channel.send(
                        f"{data.message.author.mention}, I couldn't send you a DM. "
                        "Please enable DMs from server members to receive the audit log."
                    )
                except Exception as dm_error:
                    logger.error(f"Error sending audit log via DM: {dm_error}")
                    await data.message.channel.send(
                        f"{data.message.author.mention}, I encountered an error sending the audit log via DM. "
                        "Please check your privacy settings."
                    )
        
        except Exception as e:
            await AuditLog.exception_handler(data.message, e, True)
    
    @staticmethod
    def get_all_events(guild_id: Optional[int] = None) -> Dict[str, Any]:
        """Get all stored audit log events (for programmatic access)."""
        if guild_id and guild_id in AuditLog._audit_log_storage:
            return {str(guild_id): list(AuditLog._audit_log_storage[guild_id].values())}
        
        output = {}
        for gid, entries in AuditLog._audit_log_storage.items():
            output[str(gid)] = list(entries.values())
        
        return output
    
    @staticmethod
    async def output_readable_audit_logs(data):
        """Output a human-readable audit log via DM."""
        try:
            if not data.guild:
                await data.message.channel.send("This command can only be used in a server, not in DMs.")
                return
            
            guild_id = data.guild.id
            bot = data.artemis
            
            if guild_id not in AuditLog._audit_log_storage:
                await data.message.channel.send("No audit log entries found for this server.")
                return
            
            entries = list(AuditLog._audit_log_storage[guild_id].values())
            
            # Sort by timestamp (most recent first)
            def get_timestamp(entry):
                if entry.get('created_at'):
                    try:
                        return datetime.fromisoformat(entry['created_at'])
                    except (ValueError, TypeError):
                        return datetime.min
                return datetime.min
            
            entries.sort(key=get_timestamp, reverse=True)
            
            lines = []
            lines.append(f"**Audit Log for {data.guild.name}**\n")
            
            for entry in entries:
                timestamp_str = "Unknown"
                if entry.get('created_at'):
                    try:
                        dt = datetime.fromisoformat(entry['created_at'])
                        timestamp_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except (ValueError, TypeError):
                        pass
                
                entry_id = entry.get('id', 'Unknown')
                action = entry.get('action', 'Unknown')
                
                # Resolve user ID to username
                user_str = "Unknown"
                if entry.get('user_id'):
                    try:
                        user_id = int(entry['user_id'])
                        member = data.guild.get_member(user_id)
                        if member:
                            user_str = f"{member.display_name} ({member.name}#{member.discriminator})"
                        else:
                            user = bot.get_user(user_id)
                            if user:
                                user_str = f"{user.name}#{user.discriminator}"
                            else:
                                user_str = f"User ID: {user_id}"
                    except (ValueError, TypeError):
                        user_str = f"User ID: {entry['user_id']}"
                
                # Resolve target ID to username or channel name
                target_str = "None"
                if entry.get('target_id'):
                    try:
                        target_id = int(entry['target_id'])
                        # Try as member first
                        target_member = data.guild.get_member(target_id)
                        if target_member:
                            target_str = f"{target_member.display_name} ({target_member.name}#{target_member.discriminator})"
                        else:
                            # Try as channel
                            target_channel = data.guild.get_channel(target_id)
                            if target_channel:
                                target_str = f"#{target_channel.name}"
                            else:
                                # Try as role
                                target_role = data.guild.get_role(target_id)
                                if target_role:
                                    target_str = f"@{target_role.name}"
                                else:
                                    # Try as user (may not be in guild)
                                    target_user = bot.get_user(target_id)
                                    if target_user:
                                        target_str = f"{target_user.name}#{target_user.discriminator}"
                                    else:
                                        target_str = f"ID: {target_id}"
                    except (ValueError, TypeError):
                        target_str = f"ID: {entry['target_id']}"
                
                lines.append(f"**{timestamp_str}** | ID: `{entry_id}`")
                lines.append(f"  Action: {action}")
                lines.append(f"  User: {user_str}")
                lines.append(f"  Target: {target_str}")
                lines.append("")
            
            output_text = "\n".join(lines)
            
            try:
                dm_channel = await data.message.author.create_dm()
                
                if len(output_text) > 2000:
                    # Split into chunks
                    chunks = []
                    current_chunk = []
                    current_length = 0
                    
                    for line in lines:
                        line_length = len(line) + 1  # +1 for newline
                        if current_length + line_length > 1900:
                            if current_chunk:
                                chunks.append("\n".join(current_chunk))
                            current_chunk = [line]
                            current_length = line_length
                        else:
                            current_chunk.append(line)
                            current_length += line_length
                    
                    if current_chunk:
                        chunks.append("\n".join(current_chunk))
                    
                    for i, chunk in enumerate(chunks):
                        if i == 0:
                            await dm_channel.send(f"**Audit Log for {data.guild.name}** (Part {i+1}/{len(chunks)})\n```\n{chunk}\n```")
                        else:
                            await dm_channel.send(f"**Part {i+1}/{len(chunks)}**\n```\n{chunk}\n```")
                else:
                    await dm_channel.send(f"```\n{output_text}\n```")
                
                await data.message.channel.send(f"{data.message.author.mention}, I've sent the readable audit log to your DMs!")
            
            except disnake.Forbidden:
                await data.message.channel.send(
                    f"{data.message.author.mention}, I couldn't send you a DM. "
                    "Please enable DMs from server members to receive the audit log."
                )
            except Exception as dm_error:
                logger.error(f"Error sending readable audit log via DM: {dm_error}")
                await data.message.channel.send(
                    f"{data.message.author.mention}, I encountered an error sending the audit log via DM. "
                    "Please check your privacy settings."
                )
        
        except Exception as e:
            await AuditLog.exception_handler(data.message, e, True)
