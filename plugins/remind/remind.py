"""
Remind Plugin - Reminder system
"""

import logging
import disnake
from disnake import Embed
from datetime import datetime
import pytz

from artemis.plugin.base import PluginInterface, PluginHelper
from artemis.events.listener import EventListener

logger = logging.getLogger("artemis.plugin.remind")


class Remind(PluginInterface, PluginHelper):
    """Remind plugin for reminders."""
    
    @staticmethod
    def register(bot):
        """Register the plugin."""
        if Remind.is_testing_client(bot):
            bot.log.info("Not adding remind commands on testing.")
            return
        
        bot.eventManager.addEventListener(
            EventListener.new()
            .add_command("rem")
            .add_command("remind")
            .add_command("remindme")
            .add_command("reminder")
            .set_callback(Remind.remind_me)
        )
        
        # Periodic reminder check
        bot.eventManager.addEventListener(
            EventListener.new()
            .set_periodic(10)
            .set_callback(Remind.reminder_poll)
        )
    
    @staticmethod
    async def remind_me(data):
        """Handle remind command."""
        try:
            time_str = Remind.arg_substr(data.message.content, 1, 1)
            text = Remind.arg_substr(data.message.content, 2)
            
            if not time_str or time_str == "help":
                await data.message.reply(Remind.get_help())
                return
            elif time_str in ["del", "delete"]:
                await Remind.delete_reminder(data, text)
                return
            
            if not text:
                text = "*No reminder message left*"
            
            # Get user's timezone
            from plugins.localization.localization import Localization
            user_tz_str = await Localization.fetch_timezone(data.message.member)
            if not user_tz_str:
                user_tz_str = "UTC"
            
            try:
                parsed_time = Remind.read_time(time_str, user_tz_str)
            except Exception as e:
                await data.message.reply(f"I couldn't figure out what time `{time_str}` is :(")
                return
            
            # Generate reminder ID
            import time
            reminder_id = f"{int(time.time() * 1000)}"
            
            # Store reminder
            await Remind.add_reminder(data, parsed_time, text, reminder_id)
            
            # Create embed
            embed = Embed(
                title="Reminder added",
                description=text,
                timestamp=parsed_time,
                color=data.message.member.color.value if data.message.member.color.value else 0x00ff00
            )
            embed.set_author(
                name=data.message.member.display_name,
                icon_url=data.message.member.display_avatar.url
            )
            embed.set_footer(text=f"Reminder {reminder_id}")
            
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
            await Remind.exception_handler(data.message, e, False)
    
    @staticmethod
    def get_help() -> str:
        """Get help text."""
        return (
            "**Usage**: `!remind (when) (message)`\n\n"
            "`(when)` can be one of the following:\n"
            "- a relative time, such as \"5 hours\" \"next tuesday\" \"5h45m\". Avoid words like \"in\" and \"at\" because I don't understand them.\n"
            "- an absolute time, such as \"september 3rd\" \"2025-02-18\" \"5:00am\". I'm pretty versatile but if I have trouble `YYYY-MM-DD HH:MM:SS AM/PM` will almost always work.\n\n"
            "To delete a pending reminder, use the command: `!remind delete (id)`. The `(id)` value is given in the footer of the confirmation message when the reminder is created.\n\n"
            "Notes:\n"
            "- I will use your timezone if you've told it to me via the `!timezone` command, or UTC otherwise.\n"
            "- If you have spaces in your `(when)` then you need to wrap it in double quotes, or escape the spaces. Sorry!"
        )
    
    @staticmethod
    async def add_reminder(data, time: datetime, text: str, reminder_id: str):
        """Add a reminder to storage."""
        try:
            utc_time = time.astimezone(pytz.UTC)
            await data.artemis.storage.set("remind", reminder_id, {
                "reminder_id": reminder_id,
                "message_id": str(data.message.id),
                "member_id": str(data.message.author.id),
                "channel_id": str(data.message.channel.id),
                "time_remind": utc_time.isoformat(),
                "message": text
            })
        except Exception as e:
            logger.error(f"Failed to store reminder: {e}")
    
    @staticmethod
    async def delete_reminder(data, reminder_id: str):
        """Delete a reminder."""
        try:
            reminder = await data.artemis.storage.get("remind", reminder_id)
            if not reminder:
                await data.message.reply(f"No reminder matching `{reminder_id}` was found.")
                return
            
            if reminder.get("member_id") != str(data.message.author.id):
                from artemis.permissions.resolver import Permission
                p = Permission("p.reminder.delete", data.artemis, False)
                p.add_message_context(data.message)
                if not await p.resolve():
                    await data.message.reply("You cannot delete a reminder created by another user.")
                    return
            
            await data.artemis.storage.delete("remind", reminder_id)
            await data.message.reply("Reminder deleted.")
        except Exception as e:
            await Remind.exception_handler(data.message, e)
    
    @staticmethod
    async def reminder_poll(bot):
        """Periodically check and send reminders."""
        try:
            if Remind.is_testing_client(bot):
                return
            
            now = datetime.now(pytz.UTC)
            reminders = await bot.storage.get_all("remind")
            
            for key, value in reminders.items():
                if not isinstance(value, dict):
                    continue
                
                remind_time_str = value.get("time_remind")
                if not remind_time_str:
                    continue
                
                try:
                    remind_time = datetime.fromisoformat(remind_time_str.replace('Z', '+00:00'))
                    if remind_time <= now:
                        await Remind.send_reminder(bot, value)
                        await bot.storage.delete("remind", key)
                except Exception as e:
                    logger.error(f"Error processing reminder: {e}")
        except Exception as e:
            logger.error(f"Error in reminder_poll: {e}")
    
    @staticmethod
    async def send_reminder(bot, reminder_data: dict):
        """Send a reminder."""
        try:
            channel_id = int(reminder_data.get("channel_id", 0))
            member_id = int(reminder_data.get("member_id", 0))
            message_id = int(reminder_data.get("message_id", 0))
            text = reminder_data.get("message", "Reminder!")
            
            channel = bot.get_channel(channel_id)
            if not channel:
                # Try DM
                user = bot.get_user(member_id)
                if user:
                    channel = await user.create_dm()
                else:
                    return
            
            # Get original message timestamp
            try:
                if isinstance(channel, disnake.TextChannel):
                    orig_msg = await channel.fetch_message(message_id)
                    timestamp = orig_msg.created_at
                else:
                    timestamp = datetime.now(pytz.UTC)
            except:
                timestamp = datetime.now(pytz.UTC)
            
            embed = Embed(
                title="Reminder!",
                description=text,
                timestamp=timestamp,
                color=0x00ff00
            )
            
            if isinstance(channel, disnake.TextChannel):
                member = channel.guild.get_member(member_id)
                if member:
                    embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
                    embed.color = member.color.value if member.color.value else 0x00ff00
                    jump_url = f"https://discord.com/channels/{channel.guild.id}/{channel.id}/{message_id}"
                    await channel.send(f"{member.mention}: {jump_url}", embed=embed)
            else:
                user = bot.get_user(member_id)
                if user:
                    embed.set_author(name=str(user), icon_url=user.display_avatar.url)
                    await channel.send(f"{user.mention}", embed=embed)
        except Exception as e:
            logger.error(f"Failed to send reminder: {e}")
