"""
Copyright 2025, Vijay Challa - Use of this source code follows the MIT license found in the LICENSE file.

AuditLog Plugin - Fetches and stores Discord audit log events

This plugin continuously monitors Discord's audit log for all guilds the bot is in.
It fetches audit log entries periodically and stores them persistently, allowing
retrieval of moderation actions, role changes, channel modifications, and other
server events even after they've expired from Discord's audit log.

Commands:
    !auditlog - Output all stored audit log events as JSON

Features:
    - Periodically fetches audit logs for all guilds (every 10 seconds)
    - Stores entries persistently in JSON storage
    - Respects Discord rate limits with intelligent throttling
    - Tracks all audit log action types (bans, role changes, channel edits, etc.)
    - Provides programmatic access to historical audit data
    - Automatically handles rate limiting and retries
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any
from collections import defaultdict
from datetime import datetime, timedelta

import disnake

from artemis.plugin.base import PluginInterface, PluginHelper
from artemis.events.listener import EventListener
from artemis.permissions.resolver import Permission

logger = logging.getLogger("artemis.plugin.auditlog")


class AuditLog(PluginInterface, PluginHelper):
    """Audit log monitoring plugin."""
    
    # In-memory storage: {guild_id: {entry_id: entry_data}}
    _audit_log_storage: Dict[int, Dict[str, Any]] = defaultdict(dict)
    
    # Track last fetched entry ID per guild to avoid duplicates
    _last_entry_ids: Dict[int, Optional[int]] = {}
    
    # Rate limiting: track last fetch time per guild
    _last_fetch_times: Dict[int, datetime] = {}
    
    # Minimum interval between fetches per guild (10 seconds to respect rate limits)
    MIN_FETCH_INTERVAL = 10
    
    # Rate limit tracking
    _rate_limit_until: Optional[datetime] = None
    
    @staticmethod
    def register(bot):
        """Register the plugin."""
        if AuditLog.is_testing_client(bot):
            bot.log.info("Not adding audit log monitoring on testing.")
            return
        
        # Register ready event to load from storage
        bot.eventManager.addEventListener(
            EventListener.new()
            .add_event("ready")
            .set_callback(lambda bot_instance: asyncio.create_task(AuditLog.load_from_storage(bot_instance)))
        )
        
        # Periodic task to fetch new audit log entries (every 10 seconds)
        # This fetches as often as Discord's API allows while respecting rate limits
        bot.eventManager.addEventListener(
            EventListener.new()
            .set_periodic(10)  # 10 seconds - fetch as often as possible
            .set_callback(AuditLog.fetch_audit_logs)
        )
        
        # Command to output all events as JSON
        bot.eventManager.addEventListener(
            EventListener.new()
            .add_command("auditlog")
            .set_callback(AuditLog.output_audit_logs)
        )
    
    @staticmethod
    async def load_from_storage(bot):
        """Load existing audit log entries from JSON storage."""
        try:
            await asyncio.sleep(2)  # Wait for bot to be ready
            
            all_stored = await bot.storage.get_all("audit_log")
            for key, entry_data in all_stored.items():
                # Parse guild_id from key (format: guild_id_entry_id)
                parts = key.split('_', 1)
                if len(parts) == 2:
                    try:
                        guild_id = int(parts[0])
                        entry_id = parts[1]
                        
                        if guild_id not in AuditLog._audit_log_storage:
                            AuditLog._audit_log_storage[guild_id] = {}
                        
                        AuditLog._audit_log_storage[guild_id][entry_id] = entry_data
                        
                        # Update last entry ID
                        entry_id_int = int(entry_id)
                        if (guild_id not in AuditLog._last_entry_ids or 
                            AuditLog._last_entry_ids[guild_id] is None or
                            entry_id_int > AuditLog._last_entry_ids[guild_id]):
                            AuditLog._last_entry_ids[guild_id] = entry_id_int
                    except ValueError:
                        continue  # Skip invalid keys
            
            total_entries = sum(len(entries) for entries in AuditLog._audit_log_storage.values())
            if total_entries > 0:
                logger.info(f"Loaded {total_entries} audit log entries from storage")
        except Exception as e:
            logger.error(f"Error loading audit logs from storage: {e}", exc_info=True)
    
    @staticmethod
    async def fetch_audit_logs(bot):
        """Periodically fetch audit logs for all guilds with rate limiting."""
        try:
            # Check if we're currently rate limited globally
            if AuditLog._rate_limit_until and datetime.now() < AuditLog._rate_limit_until:
                return  # Skip this cycle, wait for rate limit to expire
            
            # Process guilds with staggered timing to avoid bursts
            now = datetime.now()
            guilds_to_fetch = []
            
            for guild in bot.guilds:
                # Check if bot has VIEW_AUDIT_LOG permission
                if not guild.me.guild_permissions.view_audit_log:
                    continue
                
                # Check per-guild rate limiting
                last_fetch = AuditLog._last_fetch_times.get(guild.id)
                if last_fetch:
                    time_since_fetch = (now - last_fetch).total_seconds()
                    if time_since_fetch < AuditLog.MIN_FETCH_INTERVAL:
                        continue  # Skip this guild, not enough time has passed
                
                guilds_to_fetch.append(guild)
            
            # Fetch guilds with small delays between them to avoid rate limits
            for i, guild in enumerate(guilds_to_fetch):
                if i > 0:
                    # Small delay between guild fetches (0.1 seconds)
                    await asyncio.sleep(0.1)
                
                try:
                    await AuditLog.fetch_guild_audit_logs(bot, guild)
                    AuditLog._last_fetch_times[guild.id] = datetime.now()
                except disnake.HTTPException as e:
                    # Handle rate limiting (429 status code)
                    if e.status == 429:
                        # Try to get retry_after from response headers or default to 1 second
                        retry_after = 1.0
                        if hasattr(e, 'response') and e.response:
                            retry_after_header = e.response.headers.get('Retry-After', '1')
                            try:
                                retry_after = float(retry_after_header)
                            except (ValueError, TypeError):
                                retry_after = 1.0
                        AuditLog._rate_limit_until = datetime.now() + timedelta(seconds=retry_after)
                        logger.warning(f"Rate limited on audit log fetch. Waiting {retry_after} seconds.")
                        break  # Stop processing more guilds
                    else:
                        logger.warning(f"HTTP error fetching audit logs for guild {guild.name}: {e}")
                except Exception as e:
                    logger.warning(f"Error fetching audit logs for guild {guild.name}: {e}")
        except Exception as e:
            logger.error(f"Error in fetch_audit_logs: {e}", exc_info=True)
    
    @staticmethod
    async def fetch_guild_audit_logs(bot, guild: disnake.Guild):
        """
        Fetch audit logs for a specific guild.
        
        Args:
            bot: Bot instance
            guild: Guild to fetch audit logs for
        """
        try:
            # Build limit and before parameters
            limit = 100  # Maximum allowed by Discord API
            before = None
            
            # If we have a last entry ID, fetch entries before it to get new ones
            if guild.id in AuditLog._last_entry_ids and AuditLog._last_entry_ids[guild.id]:
                before = disnake.Object(id=AuditLog._last_entry_ids[guild.id])
            
            new_entries_count = 0
            
            # Fetch audit logs
            async for entry in guild.audit_logs(limit=limit, before=before):
                entry_id = str(entry.id)
                
                # Only store if we haven't seen this entry before
                if entry_id not in AuditLog._audit_log_storage[guild.id]:
                    # Convert entry to dictionary for storage
                    entry_data = {
                        'id': entry_id,
                        'guild_id': str(guild.id),
                        'user_id': str(entry.user.id) if entry.user else None,
                        'target_id': str(entry.target.id) if entry.target else None,
                        'action': entry.action.name if hasattr(entry.action, 'name') else str(entry.action),
                        'action_type': entry.action.value if hasattr(entry.action, 'value') else None,
                        'reason': entry.reason,
                        'changes': [
                            {
                                'key': change.key,
                                'old_value': str(change.old_value) if change.old_value is not None else None,
                                'new_value': str(change.new_value) if change.new_value is not None else None,
                            }
                            for change in (entry.changes or [])
                        ],
                        'options': {
                            'type': entry.options.type.name if entry.options and entry.options.type else None,
                            'id': str(entry.options.id) if entry.options and entry.options.id else None,
                            'role_name': entry.options.role_name if entry.options else None,
                            'count': entry.options.count if entry.options else None,
                            'channel_id': str(entry.options.channel_id) if entry.options and entry.options.channel_id else None,
                            'message_id': str(entry.options.message_id) if entry.options and entry.options.message_id else None,
                            'auto_moderation_rule_name': entry.options.auto_moderation_rule_name if entry.options else None,
                            'auto_moderation_rule_trigger_type': entry.options.auto_moderation_rule_trigger_type.name if entry.options and entry.options.auto_moderation_rule_trigger_type else None,
                        } if entry.options else None,
                        'created_at': entry.created_at.isoformat() if entry.created_at else None,
                    }
                    
                    AuditLog._audit_log_storage[guild.id][entry_id] = entry_data
                    
                    # Also persist to JSON storage for durability
                    try:
                        await bot.storage.set("audit_log", f"{guild.id}_{entry_id}", entry_data)
                    except Exception as e:
                        logger.warning(f"Failed to persist audit log entry to storage: {e}")
                    
                    # Update last entry ID (most recent)
                    entry_id_int = int(entry.id)
                    if (guild.id not in AuditLog._last_entry_ids or 
                        AuditLog._last_entry_ids[guild.id] is None or
                        entry_id_int > AuditLog._last_entry_ids[guild.id]):
                        AuditLog._last_entry_ids[guild.id] = entry_id_int
                    
                    new_entries_count += 1
                    logger.debug(f"Stored new audit log entry {entry_id} for guild {guild.name}")
            
            if new_entries_count > 0:
                logger.info(f"Fetched audit logs for guild {guild.name}, stored {new_entries_count} new entries")
        
        except disnake.Forbidden:
            logger.warning(f"No permission to view audit logs for guild {guild.name}")
        except disnake.HTTPException as e:
            # Re-raise HTTP exceptions (including rate limits) to be handled by caller
            if e.status == 429:
                raise  # Rate limit, let caller handle it
            else:
                logger.error(f"HTTP error fetching audit logs for guild {guild.name}: {e}")
        except Exception as e:
            logger.error(f"Error fetching audit logs for guild {guild.name}: {e}", exc_info=True)
    
    @staticmethod
    async def output_audit_logs(data):
        """Output all stored audit log events as JSON."""
        try:
            p = Permission("p.auditlog.view", data.artemis, False)
            p.add_message_context(data.message)
            if not await p.resolve():
                await p.send_unauthorized_message(data.message.channel)
                return
            
            guild_id = data.guild.id if data.guild else None
            output = {}
            
            if guild_id and guild_id in AuditLog._audit_log_storage:
                # Output events for current guild
                output[str(guild_id)] = list(AuditLog._audit_log_storage[guild_id].values())
            else:
                # Output all events for all guilds
                for gid, entries in AuditLog._audit_log_storage.items():
                    output[str(gid)] = list(entries.values())
            
            import json
            json_output = json.dumps(output, indent=2, ensure_ascii=False)
            
            # If JSON is too long, send as file attachment
            if len(json_output) > 2000:
                import io
                file_obj = disnake.File(
                    fp=io.BytesIO(json_output.encode('utf-8')),
                    filename=f"audit_log_{guild_id or 'all'}.json"
                )
                await data.message.channel.send("", file=file_obj)
            else:
                await data.message.channel.send(f"```json\n{json_output}\n```")
        
        except Exception as e:
            await AuditLog.exception_handler(data.message, e, True)
    
    @staticmethod
    def get_all_events(guild_id: Optional[int] = None) -> Dict[str, Any]:
        """
        Get all stored audit log events (for programmatic access).
        
        Args:
            guild_id: Optional guild ID to filter by
            
        Returns:
            Dictionary mapping guild IDs to lists of events, or single guild's events
        """
        if guild_id and guild_id in AuditLog._audit_log_storage:
            return {str(guild_id): list(AuditLog._audit_log_storage[guild_id].values())}
        
        output = {}
        for gid, entries in AuditLog._audit_log_storage.items():
            output[str(gid)] = list(entries.values())
        
        return output
