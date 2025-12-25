"""
Copyright 2025, Vijay Challa - Use of this source code follows the MIT license found in the LICENSE file.

Localization Plugin - Internationalization and timezone management

This plugin provides timezone and localization utilities for users. It allows
users to set their timezone, which is then used by other plugins (like Event
and Remind) to parse times correctly. It also provides time conversion
utilities to help coordinate across different timezones.

Commands:
    !timezone [timezone] - Set or view your timezone
    !time <time> - Convert a time to all timezones of users in the channel

Features:
    - Per-user timezone storage
    - Uses standard timezone names (e.g., "America/New_York", "Europe/London")
    - Automatic DST handling via pytz
    - Time conversion for channel members
    - Used by Event and Remind plugins for time parsing
    - Supports all standard timezone identifiers
"""

import logging
from datetime import datetime
import pytz
import disnake
from disnake import Embed

from artemis.plugin.base import PluginInterface, PluginHelper
from artemis.events.listener import EventListener

logger = logging.getLogger("artemis.plugin.localization")


class Localization(PluginInterface, PluginHelper):
    """Localization plugin for timezone management."""
    
    @staticmethod
    def register(bot):
        """Register the plugin."""
        if Localization.is_testing_client(bot):
            bot.log.info("Not adding localization commands on testing.")
            return
        
        bot.eventManager.add_listener(
            EventListener.new()
            .add_command("time")
            .set_callback(Localization.time_helper)
            .set_help("**Usage**: `!time <time_string>`\n\nConvert a time string to all configured timezones. Useful for scheduling across different timezones.")
        )
        
        bot.eventManager.add_listener(
            EventListener.new()
            .add_command("timezone")
            .set_callback(Localization.timezone)
            .set_help("**Usage**: `!timezone [timezone]`\n\nSet or view your timezone. If a timezone is provided, it will be saved for use in other commands like `!remind`. Use timezone names from [this list](https://www.php.net/manual/en/timezones.php).")
        )
    
    @staticmethod
    async def fetch_timezone(member: disnake.Member) -> str:
        """Fetch user's timezone from storage."""
        try:
            storage = member.guild._state._get_client().storage if hasattr(member.guild._state, '_get_client') else None
            if storage:
                tz = await storage.get("locale", str(member.id), {})
                if isinstance(tz, dict):
                    return tz.get("timezone")
                elif isinstance(tz, str):
                    return tz
            return None
        except:
            return None
    
    @staticmethod
    async def timezone(data):
        """Handle timezone command."""
        try:
            args = Localization.split_command(data.message.content)
            now = datetime.now(pytz.UTC)
            
            if len(args) > 1:
                try:
                    tz_name = args[1]
                    zone = pytz.timezone(tz_name)
                except pytz.exceptions.UnknownTimeZoneError:
                    embed = Embed(
                        title="Unknown Timezone",
                        description="I couldn't understand that. Please pick a value from [this list](https://www.php.net/manual/en/timezones.php).",
                        color=0xff0000
                    )
                    await data.message.reply(embed=embed)
                    return
                
                try:
                    storage = data.artemis.storage
                    await storage.set("locale", str(data.message.author.id), {
                        "timezone": zone.zone,
                        "user": str(data.message.author.id)
                    })
                except Exception as e:
                    logger.error(f"Failed to store timezone: {e}")
                
                now_tz = now.astimezone(zone)
                msg = (
                    f"Your timezone has been updated to **{zone.zone}**.\n"
                    f"I have your local time as **{now_tz.strftime('%A, %B %d, %Y %I:%M:%S %p')}**\n\n"
                    f"If this was incorrect, please use one of the values in <https://www.php.net/manual/en/timezones.php>.\n"
                    f"*Note:* In most cases you should use the Continent/City values, as they will automatically compensate for Daylight Savings for your region."
                )
            else:
                tz_str = await Localization.fetch_timezone(data.message.member)
                if not tz_str:
                    tz_str = "<unset (default UTC)>"
                    zone = pytz.UTC
                else:
                    zone = pytz.timezone(tz_str)
                
                now_tz = now.astimezone(zone)
                msg = (
                    f"Your timezone is currently set to **{tz_str}**.\n"
                    f"I have your local time as **{now_tz.strftime('%A, %B %d, %Y %I:%M:%S %p')}**\n\n"
                    f"To update, run `!timezone NewTimeZone` with one of the values in <https://www.php.net/manual/en/timezones.php>.\n"
                    f"*Note:* In most cases you should use the Continent/City values, as they will automatically compensate for Daylight Savings for your region."
                )
            
            await data.message.reply(msg)
        except Exception as e:
            await Localization.exception_handler(data.message, e)
    
    @staticmethod
    async def time_helper(data):
        """Handle time command."""
        try:
            time_str = Localization.arg_substr(data.message.content, 1)
            if not time_str:
                await data.message.reply("Usage: `!time <time>`")
                return
            
            user_tz_str = await Localization.fetch_timezone(data.message.member)
            if not user_tz_str:
                user_tz_str = "UTC"
            
            try:
                parsed_time = Localization.read_time(time_str, user_tz_str)
            except Exception as e:
                await data.message.reply(f"I couldn't figure out what time `{time_str}` is :(")
                return
            
            member_timezones = {}
            for member in data.message.channel.members:
                if not member.bot:
                    tz = await Localization.fetch_timezone(member)
                    if tz:
                        member_timezones[tz] = member_timezones.get(tz, []) + [member]
            
            embed = Embed(
                title="Translated times for users in channel",
                description="Don't see your timezone? Use the `!timezone` command."
            )
            
            tz_info = f"{parsed_time.tzinfo} ({parsed_time.strftime('%z')})"
            embed.add_field(
                name="Detected Time",
                value=(
                    f"{parsed_time.strftime('%A, %B %d, %Y %I:%M:%S %p')}\n"
                    f"{tz_info}\n"
                    f"<t:{int(parsed_time.timestamp())}:F>"
                ),
                inline=False
            )
            
            lines = []
            for tz_name in sorted(member_timezones.keys()):
                tz = pytz.timezone(tz_name)
                local_time = parsed_time.astimezone(tz)
                lines.append(f"**{tz_name}**: {local_time.strftime('%A, %B %d, %Y %I:%M:%S %p')}")
            
            if lines:
                times_text = "\n".join(lines)
                if len(times_text) > 1024:
                    chunks = [times_text[i:i+1024] for i in range(0, len(times_text), 1024)]
                    for i, chunk in enumerate(chunks):
                        embed.add_field(
                            name="Times" if i == 0 else "Times (cont.)",
                            value=chunk,
                            inline=False
                        )
                else:
                    embed.add_field(name="Times", value=times_text, inline=False)
            
            await data.message.reply(embed=embed)
        except Exception as e:
            await Localization.exception_handler(data.message, e)
