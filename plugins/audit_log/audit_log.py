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
        log_dir = Path("logs") / "audit_logs"
        return log_dir
    
    @staticmethod
    def _get_entry_timestamp(entry_data: Dict[str, Any]) -> Optional[datetime]:
        """Extract timestamp from an entry data dict."""
        if entry_data.get('created_at'):
            try:
                return datetime.fromisoformat(entry_data['created_at'])
            except (ValueError, TypeError):
                return None
        return None
    
    @staticmethod
    def _generate_log_filename(guild_id: int, start_time: Optional[datetime] = None, end_time: Optional[datetime] = None) -> str:
        """Generate a log filename based on time range.
        
        Format: {guild_id}_{YYYYMMDD}_{HHMMSS}_to_{YYYYMMDD}_{HHMMSS}.json
        If only start_time is provided: {guild_id}_{YYYYMMDD}_{HHMMSS}.json
        """
        if start_time is None:
            start_time = datetime.now()
        
        start_str = start_time.strftime("%Y%m%d_%H%M%S")
        
        if end_time and end_time != start_time:
            end_str = end_time.strftime("%Y%m%d_%H%M%S")
            return f"{guild_id}_{start_str}_to_{end_str}.json"
        else:
            return f"{guild_id}_{start_str}.json"
    
    @staticmethod
    async def _get_current_log_file(bot, guild_id: int, entry_timestamp: Optional[datetime] = None) -> Path:
        """Get the current log file for a guild, creating it if needed.
        
        If entry_timestamp is provided, it will be used to name new files.
        """
        log_dir = AuditLog._get_log_dir(bot)
        await aiofiles.os.makedirs(log_dir, exist_ok=True)
        
        if guild_id not in AuditLog._current_log_files:
            # Find the most recent log file or create a new one
            guild_prefix = f"{guild_id}_"
            log_files = []
            
            try:
                # Use os.scandir() wrapped in executor since aiofiles doesn't provide scandir
                loop = asyncio.get_running_loop()
                entries = await loop.run_in_executor(None, lambda d=log_dir: list(os.scandir(d)))
                for entry in entries:
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
                        # Create a new file based on entry timestamp or current time
                        if entry_timestamp is None:
                            entry_timestamp = datetime.now()
                        filename = AuditLog._generate_log_filename(guild_id, entry_timestamp)
                        current_file = log_dir / filename
                except Exception:
                    # Create a new file if there was an error reading the existing one
                    if entry_timestamp is None:
                        entry_timestamp = datetime.now()
                    filename = AuditLog._generate_log_filename(guild_id, entry_timestamp)
                    current_file = log_dir / filename
            else:
                # Create first log file based on entry timestamp or current time
                if entry_timestamp is None:
                    entry_timestamp = datetime.now()
                filename = AuditLog._generate_log_filename(guild_id, entry_timestamp)
                current_file = log_dir / filename
            
            AuditLog._current_log_files[guild_id] = current_file
        
        return AuditLog._current_log_files[guild_id]
    
    @staticmethod
    async def _append_to_log_file(bot, guild_id: int, entry_data: Dict[str, Any]):
        """Append an entry to the current log file, rotating if needed.
        
        Files are named based on the time range of entries they contain.
        """
        try:
            # Get entry timestamp for naming
            entry_timestamp = AuditLog._get_entry_timestamp(entry_data)
            log_file = await AuditLog._get_current_log_file(bot, guild_id, entry_timestamp)
            log_dir = AuditLog._get_log_dir(bot)
            
            # Check file size and rotate if needed
            try:
                size = await aiofiles.os.path.getsize(log_file)
                if size >= AuditLog.MAX_LOG_FILE_SIZE:
                    # Rotate to new file named with the new entry's timestamp
                    if entry_timestamp is None:
                        entry_timestamp = datetime.now()
                    filename = AuditLog._generate_log_filename(guild_id, entry_timestamp)
                    new_file = log_dir / filename
                    AuditLog._current_log_files[guild_id] = new_file
                    log_file = new_file
            except FileNotFoundError:
                # File doesn't exist yet, will be created below
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
            
            # Calculate time range from all entries
            timestamps = []
            for entry in entries:
                ts = AuditLog._get_entry_timestamp(entry)
                if ts:
                    timestamps.append(ts)
            
            if timestamps:
                start_time = min(timestamps)
                end_time = max(timestamps)
                
                # Generate filename based on time range
                expected_filename = AuditLog._generate_log_filename(guild_id, start_time, end_time)
                expected_file = log_dir / expected_filename
                
                # Rename file if needed to reflect the actual time range
                if log_file != expected_file:
                    try:
                        # If target file exists (shouldn't happen, but be safe), append to it instead
                        if await aiofiles.os.path.exists(expected_file):
                            async with aiofiles.open(expected_file, 'r', encoding='utf-8') as f:
                                content = await f.read()
                                if content.strip():
                                    existing_entries = json.loads(content)
                                    if isinstance(existing_entries, list):
                                        # Merge entries and update
                                        all_entries = existing_entries + entries
                                        # Re-sort by timestamp
                                        all_entries.sort(key=lambda e: AuditLog._get_entry_timestamp(e) or datetime.min)
                                        entries = all_entries
                                        # Recalculate time range
                                        timestamps = []
                                        for entry in entries:
                                            ts = AuditLog._get_entry_timestamp(entry)
                                            if ts:
                                                timestamps.append(ts)
                                        if timestamps:
                                            start_time = min(timestamps)
                                            end_time = max(timestamps)
                                            expected_filename = AuditLog._generate_log_filename(guild_id, start_time, end_time)
                                            expected_file = log_dir / expected_filename
                            # Remove old file if it exists and is different
                            if log_file != expected_file and await aiofiles.os.path.exists(log_file):
                                await aiofiles.os.remove(log_file)
                        
                        # Use the expected file path
                        log_file = expected_file
                        AuditLog._current_log_files[guild_id] = log_file
                    except Exception as e:
                        logger.warning(f"Error renaming log file to reflect time range: {e}")
            
            # Write back to file
            async with aiofiles.open(log_file, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(entries, indent=2, ensure_ascii=False))
        
        except Exception as e:
            logger.error(f"Error appending to log file: {e}", exc_info=True)
    
    @staticmethod
    async def load_from_storage(bot):
        """Load existing audit log entries from log files."""
        try:
            await asyncio.sleep(2)
            
            # Load from log files
            log_dir = AuditLog._get_log_dir(bot)
            if await aiofiles.os.path.exists(log_dir):
                guild_files: Dict[int, List[Path]] = defaultdict(list)
                
                # Use os.scandir() wrapped in executor since aiofiles doesn't provide scandir
                try:
                    loop = asyncio.get_running_loop()
                    entries = await loop.run_in_executor(None, lambda d=log_dir: list(os.scandir(d)))
                    for entry in entries:
                        if entry.name.endswith('.json'):
                            try:
                                name_no_ext = entry.name.replace('.json', '')
                                # Extract guild_id from filename
                                # New format: {guild_id}_{YYYYMMDD}_{HHMMSS}_to_{YYYYMMDD}_{HHMMSS}.json
                                # or: {guild_id}_{YYYYMMDD}_{HHMMSS}.json
                                # Old format: {guild_id}_log_{timestamp}.json
                                
                                if '_log_' in name_no_ext:
                                    # Old format: {guild_id}_log_{timestamp}.json
                                    parts = name_no_ext.split('_log_', 1)
                                    if len(parts) == 2:
                                        guild_id = int(parts[0])
                                        guild_files[guild_id].append(Path(entry.path))
                                elif '_to_' in name_no_ext:
                                    # New format with range: {guild_id}_{YYYYMMDD}_{HHMMSS}_to_{YYYYMMDD}_{HHMMSS}.json
                                    # Extract guild_id (everything before first date/time pattern)
                                    parts = name_no_ext.split('_to_', 1)
                                    if len(parts) == 2:
                                        # First part is {guild_id}_{YYYYMMDD}_{HHMMSS}
                                        # Split and take the first part as guild_id
                                        start_part = parts[0]
                                        # Split by underscore and take the first token as guild_id
                                        guild_id_str = start_part.split('_')[0]
                                        guild_id = int(guild_id_str)
                                        guild_files[guild_id].append(Path(entry.path))
                                else:
                                    # New format without range: {guild_id}_{YYYYMMDD}_{HHMMSS}.json
                                    # First part before first underscore is guild_id
                                    parts = name_no_ext.split('_', 1)
                                    if len(parts) >= 2:
                                        # Should have at least {guild_id}_{YYYYMMDD}
                                        guild_id = int(parts[0])
                                        guild_files[guild_id].append(Path(entry.path))
                            except (ValueError, IndexError):
                                continue
                except FileNotFoundError:
                    pass
                
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
            # Use os.scandir() wrapped in executor since aiofiles doesn't provide scandir
            loop = asyncio.get_running_loop()
            entries = await loop.run_in_executor(None, lambda d=log_dir: list(os.scandir(d)))
            for entry in entries:
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
