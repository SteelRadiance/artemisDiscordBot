"""
Copyright 2025, Vijay Challa - Use of this source code follows the MIT license found in the LICENSE file.

Archive Plugin - Channel archiving tool

This plugin allows administrators to archive entire Discord channels to JSON files.
It captures all messages, attachments, user information, and metadata, storing them
in a structured format. Large archives are automatically compressed with gzip.

Commands:
    !archive <channel_mention> - Archive a channel (admin only)

Features:
    - Exports all messages from a channel
    - Preserves message metadata (author, timestamps, edits, pins)
    - Captures attachment URLs and metadata
    - Stores user information and avatars
    - Automatically compresses large archives
    - Admin-only due to resource usage
"""

import logging
import disnake
import json
import gzip
from datetime import datetime
from pathlib import Path

from artemis.plugin.base import PluginInterface, PluginHelper
from artemis.events.listener import EventListener

logger = logging.getLogger("artemis.plugin.archive")


class Archive(PluginInterface, PluginHelper):
    """Archive plugin for channel archiving."""
    
    ARCHIVER_VERSION = "1.0.0"
    
    @staticmethod
    def register(bot):
        """Register the plugin."""
        if Archive.is_testing_client(bot):
            bot.log.info("Not adding archive commands on testing.")
            return
        
        bot.eventManager.add_listener(
            EventListener.new()
            .add_command("archive")
            .set_callback(Archive.archive)
            .set_help("**Usage**: `!archive <channel_mention>`\n\nArchive a channel. This command is admin only.")
        )
    
    @staticmethod
    async def archive(data):
        """Handle archive command."""
        try:
            admin_ids = getattr(data.artemis.config, 'ADMIN_USER_IDS', [])
            if str(data.message.author.id) not in admin_ids:
                await Archive.unauthorized(data.message)
                return
            
            channel_text = Archive.arg_substr(data.message.content, 1, 1)
            if not channel_text:
                await data.message.reply("Usage: `!archive <channel_mention>`")
                return
            
            channel = Archive.channel_mention(channel_text, data.message.guild)
            if not channel:
                await data.message.reply("Could not find that channel.")
                return
            
            if not channel.permissions_for(data.guild.me).view_channel:
                await data.message.channel.send("I don't have read access to that channel!")
                return
            
            await data.message.channel.send(f"Beginning {channel.mention} (`#{channel.name}`) archival...")
            await Archive._archive(channel, data)
        except Exception as e:
            await Archive.exception_handler(data.message, e)
    
    @staticmethod
    async def _archive(channel: disnake.TextChannel, data):
        """Archive channel messages."""
        try:
            messages = []
            async for message in channel.history(limit=None):
                messages.append(message)
            
            messages.sort(key=lambda m: m.id)
            
            payload = {
                "_version": Archive.ARCHIVER_VERSION,
                "_retrieval": {
                    "time": datetime.utcnow().isoformat(),
                    "user": str(data.artemis.user),
                    "agent": f"artemis/{data.artemis.__class__.__name__}"
                },
                "channel": {
                    "id": channel.id,
                    "name": channel.name,
                    "parent": channel.category_id,
                    "topic": channel.topic,
                    "isNSFW": channel.nsfw,
                    "created": channel.created_at.isoformat() if channel.created_at else None
                },
                "urls": {},
                "users": {},
                "pins": [],
                "messages": []
            }
            
            for message in messages:
                msg_data = {
                    "id": message.id,
                    "author": message.author.id,
                    "content": message.content,
                    "edited": message.edited_at.isoformat() if message.edited_at else None,
                    "created": message.created_at.isoformat() if message.created_at else None,
                    "attachments": [],
                    "embeds": [embed.to_dict() for embed in message.embeds]
                }
                
                if message.webhook_id:
                    msg_data["webhookName"] = message.author.name
                
                if message.pinned:
                    payload["pins"].append(message.id)
                
                for att in message.attachments:
                    payload["urls"][str(att.id)] = att.url
                    msg_data["attachments"].append({
                        "id": att.id,
                        "filename": att.filename,
                        "size": att.size,
                        "url": att.url,
                        "proxy_url": att.proxy_url,
                        "content_type": att.content_type
                    })
                
                if str(message.author.id) not in payload["users"]:
                    payload["users"][str(message.author.id)] = {
                        "id": message.author.id,
                        "tag": str(message.author),
                        "nick": message.author.display_name if hasattr(message.author, 'display_name') else message.author.name,
                        "av": message.author.display_avatar.url if message.author.display_avatar else None,
                        "webhook": bool(message.webhook_id)
                    }
                    if message.author.display_avatar:
                        payload["urls"][str(message.author.id)] = message.author.display_avatar.url
                
                payload["messages"].append(msg_data)
            
            # Save to file
            json_data = json.dumps(payload, indent=2, ensure_ascii=False)
            fname = f"{channel.id}_{channel.name}.json"
            
            temp_dir = Path("temp")
            temp_dir.mkdir(exist_ok=True)
            
            file_path = temp_dir / fname
            if len(json_data.encode('utf-8')) > (2 ** 20):  # 1MB
                file_path = temp_dir / f"{fname}.gz"
                with gzip.open(file_path, 'wb') as f:
                    f.write(json_data.encode('utf-8'))
            else:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(json_data)
            
            # Send file
            try:
                file_obj = disnake.File(str(file_path), filename=fname if not file_path.suffix == '.gz' else f"{fname}.gz")
                await data.message.channel.send(f"Done! {len(messages)} messages saved.", file=file_obj)
            except Exception as e:
                await data.message.channel.send(f"Done! Upload failed but you can grab it from {file_path.absolute()}")
        except Exception as e:
            await Archive.exception_handler(data.message, e)
