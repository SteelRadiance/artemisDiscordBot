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
import os
import json
from typing import Dict, List, Optional, Any
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import disnake
import aiofiles
import aiofiles.os

from artemis.plugin.base import PluginInterface, PluginHelper
from artemis.events.listener import EventListener

logger = logging.getLogger("artemis.plugin.auditlog")


class AuditLog(PluginInterface, PluginHelper):
    """Audit log monitoring plugin."""
    
    # In-memory storage: {guild_id: {entry_id: entry_data}}
    _audit_log_storage: Dict[int, Dict[str, Any]] = defaultdict(dict)
    
    # Current log file per guild: {guild_id: file_path}
    _current_log_files: Dict[int, Path] = {}
    
    # Maximum file size in bytes (default 10MB)
    MAX_LOG_FILE_SIZE = 10 * 1024 * 1024
    
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
            .set_help("**Usage**: `!auditlog`\n\nView audit log entries. The log is sent via DM and contains records of moderation actions and other logged events.")
        )
    
    @staticmethod
    def _get_log_dir(bot) -> Path:
        """Get the log file directory path."""
        storage_dir = Path(getattr(bot.storage, 'storage_dir', Path('storage')))
        log_dir = storage_dir / "audit_log" / "logs"
        return log_dir
    
    @staticmethod
    async def _get_current_log_file(bot, guild_id: int) -> Path:
        """Get the current log file for a guild, creating it if needed."""
        log_dir = AuditLog._get_log_dir(bot)
        await aiofiles.os.makedirs(log_dir, exist_ok=True)
        
        if guild_id not in AuditLog._current_log_files:
            # Find the most recent log file or create a new one
            guild_prefix = f"{guild_id}_"
            log_files = []
            
            try:
                async for entry in aiofiles.os.scandir(log_dir):
                    if entry.name.startswith(guild_prefix) and entry.name.endswith('.json'):
                        log_files.append(entry.path)
            except FileNotFoundError:
                pass
            
            if log_files:
                # Sort by modification time, most recent first
                log_files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
                current_file = Path(log_files[0])
                
                # Check if current file is too large
                try:
                    size = await aiofiles.os.path.getsize(current_file)
                    if size >= AuditLog.MAX_LOG_FILE_SIZE:
                        # Create a new file
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        current_file = log_dir / f"{guild_id}_log_{timestamp}.json"
                except Exception:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    current_file = log_dir / f"{guild_id}_log_{timestamp}.json"
            else:
                # Create first log file
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                current_file = log_dir / f"{guild_id}_log_{timestamp}.json"
            
            AuditLog._current_log_files[guild_id] = current_file
        
        return AuditLog._current_log_files[guild_id]
    
    @staticmethod
    async def _append_to_log_file(bot, guild_id: int, entry_data: Dict[str, Any]):
        """Append an entry to the current log file, rotating if needed."""
        try:
            log_file = await AuditLog._get_current_log_file(bot, guild_id)
            
            # Check file size and rotate if needed
            try:
                size = await aiofiles.os.path.getsize(log_file)
                if size >= AuditLog.MAX_LOG_FILE_SIZE:
                    # Rotate to new file
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    log_dir = AuditLog._get_log_dir(bot)
                    new_file = log_dir / f"{guild_id}_log_{timestamp}.json"
                    AuditLog._current_log_files[guild_id] = new_file
                    log_file = new_file
            except FileNotFoundError:
                pass
            
            # Read existing entries or create new list
            entries = []
            if await aiofiles.os.path.exists(log_file):
                try:
                    async with aiofiles.open(log_file, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        if content.strip():
                            entries = json.loads(content)
                            if not isinstance(entries, list):
                                entries = []
                except (json.JSONDecodeError, Exception) as e:
                    logger.warning(f"Error reading log file {log_file}: {e}, creating new file")
                    entries = []
            
            # Append new entry
            entries.append(entry_data)
            
            # Write back to file
            async with aiofiles.open(log_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(entries, indent=2, ensure_ascii=False))
        
        except Exception as e:
            logger.error(f"Error appending to log file: {e}", exc_info=True)
    
    @staticmethod
    async def load_from_storage(bot):
        """Load existing audit log entries from JSON storage and log files."""
        try:
            await asyncio.sleep(2)
            
            # Load from JSON storage (legacy)
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
            
            # Load from log files
            log_dir = AuditLog._get_log_dir(bot)
            if await aiofiles.os.path.exists(log_dir):
                guild_files: Dict[int, List[Path]] = defaultdict(list)
                
                async for entry in aiofiles.os.scandir(log_dir):
                    if entry.name.endswith('.json'):
                        try:
                            # Parse filename: {guild_id}_log_{timestamp}.json
                            parts = entry.name.replace('.json', '').split('_log_')
                            if len(parts) == 2:
                                guild_id = int(parts[0])
                                guild_files[guild_id].append(Path(entry.path))
                        except (ValueError, IndexError):
                            continue
                
                # Load entries from all log files
                for guild_id, files in guild_files.items():
                    # Sort by modification time, most recent first
                    files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
                    
                    for log_file in files:
                        try:
                            async with aiofiles.open(log_file, 'r', encoding='utf-8') as f:
                                content = await f.read()
                                if content.strip():
                                    entries = json.loads(content)
                                    if isinstance(entries, list):
                                        for entry_data in entries:
                                            entry_id = entry_data.get('id')
                                            if entry_id:
                                                if guild_id not in AuditLog._audit_log_storage:
                                                    AuditLog._audit_log_storage[guild_id] = {}
                                                AuditLog._audit_log_storage[guild_id][entry_id] = entry_data
                        except Exception as e:
                            logger.warning(f"Error loading log file {log_file}: {e}")
            
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
            
            # Write to log file
            try:
                await AuditLog._append_to_log_file(bot, guild_id, entry_data)
            except Exception as e:
                logger.warning(f"Failed to write audit log entry to file: {e}")
            
            # Also write to legacy JSON storage for backward compatibility
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
    async def _get_all_log_files(bot, guild_id: int) -> List[Path]:
        """Get all log files for a guild, sorted by most recent first."""
        log_dir = AuditLog._get_log_dir(bot)
        log_files = []
        
        if not await aiofiles.os.path.exists(log_dir):
            return log_files
        
        guild_prefix = f"{guild_id}_"
        try:
            async for entry in aiofiles.os.scandir(log_dir):
                if entry.name.startswith(guild_prefix) and entry.name.endswith('.json'):
                    log_files.append(Path(entry.path))
        except FileNotFoundError:
            return log_files
        
        # Sort by modification time, most recent first
        log_files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return log_files
    
    @staticmethod
    async def output_audit_logs(data):
        """Output all stored audit log events as JSON or readable format via DM."""
        try:
            if not data.guild:
                await data.message.channel.send("This command can only be used in a server, not in DMs.")
                return
            
            args = AuditLog.split_command(data.message.content)
            readable = len(args) > 1 and args[1].lower() == '-readable'
            
            guild_id = data.guild.id
            bot = data.artemis
            
            # Get all log files for this guild
            log_files = await AuditLog._get_all_log_files(bot, guild_id)
            
            if not log_files:
                await data.message.channel.send("No audit log files found for this server.")
                return
            
            try:
                dm_channel = await data.message.author.create_dm()
                
                if readable:
                    # Send readable format from all log files
                    for i, log_file in enumerate(log_files):
                        try:
                            async with aiofiles.open(log_file, 'r', encoding='utf-8') as f:
                                content = await f.read()
                                if content.strip():
                                    entries = json.loads(content)
                                    if isinstance(entries, list) and entries:
                                        # Format as readable
                                        lines = []
                                        file_name = log_file.name
                                        lines.append(f"**Log File: {file_name}**\n")
                                        
                                        # Sort entries by timestamp (most recent first)
                                        def get_timestamp(entry):
                                            if entry.get('created_at'):
                                                try:
                                                    return datetime.fromisoformat(entry['created_at'])
                                                except (ValueError, TypeError):
                                                    return datetime.min
                                            return datetime.min
                                        
                                        sorted_entries = sorted(entries, key=get_timestamp, reverse=True)
                                        
                                        for entry in sorted_entries:
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
                                            
                                            # Resolve target ID
                                            target_str = "None"
                                            if entry.get('target_id'):
                                                try:
                                                    target_id = int(entry['target_id'])
                                                    target_member = data.guild.get_member(target_id)
                                                    if target_member:
                                                        target_str = f"{target_member.display_name} ({target_member.name}#{target_member.discriminator})"
                                                    else:
                                                        target_channel = data.guild.get_channel(target_id)
                                                        if target_channel:
                                                            target_str = f"#{target_channel.name}"
                                                        else:
                                                            target_role = data.guild.get_role(target_id)
                                                            if target_role:
                                                                target_str = f"@{target_role.name}"
                                                            else:
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
                                        
                                        if len(output_text) > 2000:
                                            # Split into chunks
                                            chunks = []
                                            current_chunk = []
                                            current_length = 0
                                            
                                            for line in lines:
                                                line_length = len(line) + 1
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
                                            
                                            for j, chunk in enumerate(chunks):
                                                if j == 0:
                                                    await dm_channel.send(f"**{file_name}** (Part {j+1}/{len(chunks)})\n```\n{chunk}\n```")
                                                else:
                                                    await dm_channel.send(f"**Part {j+1}/{len(chunks)}**\n```\n{chunk}\n```")
                                        else:
                                            await dm_channel.send(f"```\n{output_text}\n```")
                        except Exception as e:
                            logger.warning(f"Error reading log file {log_file}: {e}")
                            continue
                    
                    await data.message.channel.send(f"{data.message.author.mention}, I've sent the readable audit log to your DMs!")
                else:
                    # Send JSON files
                    for i, log_file in enumerate(log_files):
                        try:
                            file_obj = disnake.File(
                                fp=log_file,
                                filename=log_file.name
                            )
                            if i == 0:
                                await dm_channel.send(f"Audit log files for {data.guild.name} (most recent first):", file=file_obj)
                            else:
                                await dm_channel.send(file=file_obj)
                        except Exception as e:
                            logger.warning(f"Error sending log file {log_file}: {e}")
                    
                    await data.message.channel.send(f"{data.message.author.mention}, I've sent the audit log files to your DMs!")
                
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
        """Output a human-readable audit log via DM (legacy method, now handled by output_audit_logs)."""
        await AuditLog.output_audit_logs(data)
