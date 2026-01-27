"""
Copyright 2025, Vijay Challa - Use of this source code follows the MIT license found in the LICENSE file.
"""

import logging
from datetime import datetime

from artemis.plugin.base import PluginInterface, PluginHelper
from artemis.events.listener import EventListener

logger = logging.getLogger("artemis.plugin.stats")

STATS_NAMESPACE = "stats"


def _storage_key(guild_id: int, user_id: int) -> str:
    return f"{guild_id}_{user_id}"


def _parse_last_at(last_at):
    if not last_at:
        return datetime.min, "Never"
    try:
        dt = datetime.fromisoformat(last_at.replace("Z", "+00:00"))
        return dt, dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return datetime.min, last_at or "Never"


class Stats(PluginInterface, PluginHelper):

    @staticmethod
    def register(bot):
        if Stats.is_testing_client(bot):
            bot.log.info("Not adding stats on testing.")
            return
        bot.eventManager.add_listener(
            EventListener.new().add_event("message").set_callback(Stats._on_message)
        )
        bot.eventManager.add_listener(
            EventListener.new()
            .add_command("stats")
            .set_callback(Stats.stats_command)
            .set_help("**Usage**: `!stats` – List users by message count and last message time.")
        )

    @staticmethod
    async def _on_message(event_data):
        try:
            message = getattr(event_data, "message", None)
            if not message or message.author.bot or not message.guild:
                return
            storage = getattr(event_data.artemis, "storage", None)
            if not storage:
                return
            key = _storage_key(message.guild.id, message.author.id)
            record = await storage.get(STATS_NAMESPACE, key)
            if not record or not isinstance(record, dict):
                record = {"count": 0, "last_message_at": None, "username": None}
            record["count"] = record.get("count", 0) + 1
            record["last_message_at"] = message.created_at.isoformat()
            record["username"] = message.author.display_name or message.author.name
            await storage.set(STATS_NAMESPACE, key, record)
        except Exception as e:
            logger.warning("Error recording message for stats: %s", e)

    @staticmethod
    async def stats_command(data):
        try:
            if not data.guild:
                await data.message.channel.send("This command can only be used in a server.")
                return
            storage = data.artemis.storage
            guild_id = data.guild.id
            prefix = f"{guild_id}_"
            rows = []
            for key, value in (await storage.get_all(STATS_NAMESPACE)).items():
                if not key.startswith(prefix) or not isinstance(value, dict):
                    continue
                try:
                    user_id = int(key[len(prefix):])
                except ValueError:
                    continue
                count = value.get("count", 0)
                last_at = value.get("last_message_at")
                username = value.get("username") or "Unknown"
                member = data.guild.get_member(user_id)
                if member:
                    username = member.display_name or member.name
                _, last_str = _parse_last_at(last_at)
                rows.append((username, count, last_at, last_str))
            rows.sort(key=lambda r: (-r[1], _parse_last_at(r[2])[0]))
            if not rows:
                await data.message.channel.send("No message stats recorded yet for this server.")
                return
            lines = [f"{i}. {u}, Messages:{c}, Last Message {s}" for i, (u, c, _, s) in enumerate(rows, 1)]
            block = "\n".join(lines)
            if len(block) <= 2000:
                await data.message.channel.send(block)
            else:
                buf, length = [], 0
                for line in lines:
                    if length + len(line) + 1 > 1990:
                        await data.message.channel.send("\n".join(buf))
                        buf, length = [], 0
                    buf.append(line)
                    length += len(line) + 1
                if buf:
                    await data.message.channel.send("\n".join(buf))
        except Exception as e:
            await Stats.exception_handler(data.message, e)
