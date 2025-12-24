"""
Event Plugin - Event calendar system

This plugin provides a calendar system for scheduling and managing events within
Discord servers. Users can create events with natural language time parsing,
view upcoming events, and set up calendar channels that automatically update.

Commands:
    !event <when> <title> - Create a new event
    !event remove <event_id> - Remove an event
    !calendar - View upcoming events
    !setCalendar <channel> - Set a channel to display calendar (auto-updates)

Features:
    - Natural language time parsing (e.g., "5 hours", "next tuesday", "2025-02-18")
    - Timezone-aware scheduling using user's configured timezone
    - Automatic calendar message updates every minute
    - Displays events sorted by time with Discord timestamps
    - Supports relative and absolute time formats
"""

import logging
import disnake
from disnake import Embed
from datetime import datetime
import pytz

from artemis.plugin.base import PluginInterface, PluginHelper
from artemis.events.listener import EventListener
from artemis.permissions.resolver import Permission

logger = logging.getLogger("artemis.plugin.event")


class Event(PluginInterface, PluginHelper):
    """Event plugin for calendar management."""
    
    @staticmethod
    def register(bot):
        """Register the plugin."""
        if Event.is_testing_client(bot):
            bot.log.info("Not adding event commands on testing.")
            return
        
        bot.eventManager.addEventListener(
            EventListener.new()
            .add_command("event")
            .set_callback(Event.event_handler)
        )
        
        bot.eventManager.addEventListener(
            EventListener.new()
            .add_command("calendar")
            .set_callback(Event.calendar)
        )
        
        bot.eventManager.addEventListener(
            EventListener.new()
            .add_command("setCalendar")
            .set_callback(Event.set_calendar)
        )
        
        # Periodic calendar update
        bot.eventManager.addEventListener(
            EventListener.new()
            .set_periodic(60)
            .set_callback(Event.calendar_update)
        )
    
    @staticmethod
    async def event_handler(data):
        """Handle event command."""
        try:
            p = Permission("p.events.add", data.artemis, True)
            p.add_message_context(data.message)
            if not await p.resolve():
                await p.send_unauthorized_message(data.message.channel)
                return
            
            time_str = Event.arg_substr(data.message.content, 1, 1)
            text = Event.arg_substr(data.message.content, 2)
            
            if not time_str or not text:
                await data.message.reply(Event.get_help())
                return
            
            if time_str == "remove":
                # Remove event
                event_id = text.strip()
                await Event.remove_event(data, event_id)
                await data.message.reply("If that was your event, it was removed :)")
                return
            
            # Get user's timezone
            from plugins.localization.localization import Localization
            user_tz_str = await Localization.fetch_timezone(data.message.member)
            if not user_tz_str:
                user_tz_str = "UTC"
            
            try:
                parsed_time = Event.read_time(time_str, user_tz_str)
            except Exception as e:
                await data.message.reply(f"I couldn't figure out what time `{time_str}` is :(")
                return
            
            # Generate event ID
            import time
            event_id = f"{int(time.time() * 1000)}"
            
            # Store event
            await Event.add_event(data, parsed_time, text, event_id)
            
            # Create embed
            embed = Embed(
                title="Event added",
                description=text,
                timestamp=parsed_time,
                color=data.message.member.color.value if data.message.member.color.value else 0x00ff00
            )
            embed.set_author(
                name=data.message.member.display_name,
                icon_url=data.message.member.display_avatar.url
            )
            embed.set_footer(text=f"Event ID {event_id}")
            
            tz_info = f"{parsed_time.tzinfo} ({parsed_time.strftime('%z')})"
            embed.add_field(
                name="Detected Time",
                value=(
                    f"{parsed_time.strftime('%A, %B %d, %Y %I:%M:%S %p')}\n"
                    f"{tz_info}\n"
                    f"<t:{int(parsed_time.timestamp())}:R>"
                ),
                inline=False
            )
            
            await data.message.reply(embed=embed)
        except Exception as e:
            await Event.exception_handler(data.message, e, False)
    
    @staticmethod
    def get_help() -> str:
        """Get help text for event command."""
        return (
            "**Usage**: `!event (when) (title)`\n\n"
            "`(when)` can be one of the following:\n"
            "- a relative time, such as \"5 hours\" \"next tuesday\" \"5h45m\". Avoid words like \"in\" and \"at\" because I don't understand them.\n"
            "- an absolute time, such as \"september 3rd\" \"2025-02-18\" \"5:00am\". I'm pretty versatile but if I have trouble `YYYY-MM-DD HH:MM:SS AM/PM` will almost always work.\n\n"
            "Notes:\n"
            "- I will use your timezone if you've told it to me via the `!timezone` command, or UTC otherwise.\n"
            "- If you have spaces in your `(when)` then you need to wrap it in double quotes, or escape the spaces. Sorry!\n"
            "- To cancel an event, run `!event remove EVENT_ID`"
        )
    
    @staticmethod
    async def add_event(data, time: datetime, text: str, event_id: str):
        """Add an event to storage."""
        try:
            # Convert to UTC for storage
            utc_time = time.astimezone(pytz.UTC)
            await data.artemis.storage.set("event", f"{data.guild.id}_{event_id}", {
                "event_id": event_id,
                "guild_id": str(data.guild.id),
                "member_id": str(data.message.author.id),
                "time": utc_time.isoformat(),
                "name": text
            })
        except Exception as e:
            logger.error(f"Failed to store event: {e}")
    
    @staticmethod
    async def remove_event(data, event_id: str):
        """Remove an event."""
        try:
            events = await data.artemis.storage.get_all("event")
            for key, value in events.items():
                if isinstance(value, dict) and value.get("event_id") == event_id and value.get("member_id") == str(data.message.author.id):
                    await data.artemis.storage.delete("event", key)
                    break
        except Exception as e:
            logger.error(f"Failed to remove event: {e}")
    
    @staticmethod
    async def calendar(data):
        """Show calendar."""
        try:
            from plugins.localization.localization import Localization
            user_tz_str = await Localization.fetch_timezone(data.message.member)
            if not user_tz_str:
                user_tz_str = "UTC"
            
            embed = await Event.create_calendar_embed(data.guild, user_tz_str)
            await data.message.reply(embed=embed)
        except Exception as e:
            await Event.exception_handler(data.message, e)
    
    @staticmethod
    async def create_calendar_embed(guild: disnake.Guild, tz_str: str = "UTC") -> Embed:
        """Create calendar embed."""
        try:
            tz = pytz.timezone(tz_str)
            now = datetime.now(pytz.UTC)
            
            # Get all events for guild
            events_data = await guild._state._get_client().storage.get_all("event")
            upcoming_events = []
            
            for key, value in events_data.items():
                if isinstance(value, dict) and value.get("guild_id") == str(guild.id):
                    event_time = datetime.fromisoformat(value["time"].replace('Z', '+00:00'))
                    if event_time >= now:
                        event_time = event_time.astimezone(tz)
                        upcoming_events.append({
                            "time": event_time,
                            "name": value.get("name", "Unnamed event"),
                            "id": value.get("event_id", "")
                        })
            
            # Sort by time
            upcoming_events.sort(key=lambda x: x["time"])
            
            embed = Embed(
                title=f"Events - {guild.name}",
                footer=f"Timezone: {tz_str}",
                timestamp=datetime.now()
            )
            
            if upcoming_events:
                events_text = "\n".join([
                    f"**{ev['name']}**: {ev['time'].strftime('%A, %B %d, %Y %I:%M %p')} (<t:{int(ev['time'].timestamp())}:R>)"
                    for ev in upcoming_events[:10]
                ])
                
                if len(events_text) > 1024:
                    chunks = [events_text[i:i+1024] for i in range(0, len(events_text), 1024)]
                    for i, chunk in enumerate(chunks):
                        embed.add_field(
                            name="Events" if i == 0 else "Events (cont.)",
                            value=chunk,
                            inline=False
                        )
                else:
                    embed.add_field(name="Events", value=events_text, inline=False)
            else:
                embed.description = "There are no events scheduled. Add some using `!event`."
            
            return embed
        except Exception as e:
            logger.error(f"Error creating calendar embed: {e}")
            return Embed(title="Error", description="Failed to load calendar.")
    
    @staticmethod
    async def set_calendar(data):
        """Set calendar message."""
        try:
            p = Permission("p.events.setcalendar", data.artemis, False)
            p.add_message_context(data.message)
            if not await p.resolve():
                await p.send_unauthorized_message(data.message.channel)
                return
            
            ctxt = Event.arg_substr(data.message.content, 1, 1)
            if not ctxt:
                await data.message.reply("Usage: `!setCalendar (channel mention or message URL)`")
                return
            
            channel = Event.channel_mention(ctxt, data.message.guild)
            if channel:
                embed = await Event.create_calendar_embed(data.guild)
                msg = await channel.send(embed=embed)
                await Event.set_calendar_message(data, msg)
                await data.message.reply(f"Calendar set to {msg.jump_url}")
            else:
                # Try to fetch message from URL
                msg = await Event.fetch_message(data.artemis, ctxt)
                if msg:
                    await Event.set_calendar_message(data, msg)
                    await data.message.reply(f"Calendar set to {msg.jump_url}")
                else:
                    await data.message.reply("Could not find that channel or message.")
        except Exception as e:
            await Event.exception_handler(data.message, e, True)
    
    @staticmethod
    async def set_calendar_message(data, message: disnake.Message):
        """Store calendar message reference."""
        try:
            await data.artemis.storage.set("event_calendar", str(message.guild.id), {
                "guild_id": str(message.guild.id),
                "channel_id": str(message.channel.id),
                "message_id": str(message.id)
            })
        except Exception as e:
            logger.error(f"Failed to store calendar message: {e}")
    
    @staticmethod
    async def calendar_update(bot):
        """Periodically update calendar messages."""
        try:
            calendars = await bot.storage.get_all("event_calendar")
            for key, value in calendars.items():
                if not isinstance(value, dict):
                    continue
                
                guild_id = int(value.get("guild_id", 0))
                channel_id = int(value.get("channel_id", 0))
                message_id = int(value.get("message_id", 0))
                
                guild = bot.get_guild(guild_id)
                if not guild:
                    continue
                
                channel = guild.get_channel(channel_id)
                if not channel or not isinstance(channel, disnake.TextChannel):
                    continue
                
                try:
                    msg = await channel.fetch_message(message_id)
                    if msg.author.id == bot.user.id:
                        embed = await Event.create_calendar_embed(guild)
                        await msg.edit(embed=embed)
                except Exception as e:
                    logger.debug(f"Failed to update calendar message: {e}")
        except Exception as e:
            logger.error(f"Error in calendar_update: {e}")
