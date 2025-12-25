"""
Copyright 2025, Vijay Challa - Use of this source code follows the MIT license found in the LICENSE file.

MatchVoting Plugin - Match voting system

This plugin provides a tournament-style match voting system. It allows creating
matches with competitors, setting voting deadlines, and tallying votes. Useful
for competitions, tournaments, or any scenario where you need structured voting
with multiple options and deadlines.

Commands:
    !match create <title> [period] - Create a new match
    !match addcompetitor <match_id> <user> [data] - Add a competitor
    !match vote <match_id> <entry_id> - Vote for a competitor
    !match announce <channel> <match_id> - Announce a match for voting
    !tally <match_id> - View match results

Features:
    - Create matches with custom deadlines
    - Add multiple competitors per match
    - Vote tracking with deadline enforcement
    - Detailed vote tallies (admin can see voter names)
    - Match announcements with embed formatting
    - Automatic vote expiration after deadline
"""

import logging
import disnake
from disnake import Embed
from datetime import datetime
import pytz

from artemis.plugin.base import PluginInterface, PluginHelper
from artemis.events.listener import EventListener

logger = logging.getLogger("artemis.plugin.matchvoting")


class MatchVoting(PluginInterface, PluginHelper):
    """MatchVoting plugin for tournament voting."""
    
    @staticmethod
    def register(bot):
        """Register the plugin."""
        if MatchVoting.is_testing_client(bot):
            bot.log.info("Not adding match voting commands on testing.")
            return
        
        bot.eventManager.add_listener(
            EventListener.new()
            .add_command("match")
            .set_callback(MatchVoting.match_handler)
            .set_help(MatchVoting.get_help)
        )
        
        bot.eventManager.add_listener(
            EventListener.new()
            .add_command("tally")
            .set_callback(MatchVoting.tally_handler)
            .set_help("**Usage**: `!tally <match_id>`\n\nView match voting results for a specific match. Shows vote counts and winners.")
        )
    
    @staticmethod
    async def match_handler(data):
        """Handle match command."""
        try:
            args = MatchVoting.split_command(data.message.content)
            if len(args) < 2:
                await data.message.reply(MatchVoting.get_help())
                return
            
            command = args[1].lower()
            
            if command == "create":
                await MatchVoting.create_match(data, args[2:])
            elif command == "addcompetitor":
                await MatchVoting.add_competitor(data, args[2:])
            elif command == "vote":
                await MatchVoting.vote_match(data, args[2:])
            elif command == "announce":
                await MatchVoting.announce_match(data, args[2:])
            else:
                await data.message.reply(MatchVoting.get_help())
        except Exception as e:
            await MatchVoting.exception_handler(data.message, e)
    
    @staticmethod
    def get_help() -> str:
        """Get help text."""
        return (
            "**Usage**: `!match <command>`\n\n"
            "Commands:\n"
            "- `create <title> [period]` - Create a match\n"
            "- `addcompetitor <match_id> <user> [data]` - Add competitor\n"
            "- `vote <match_id> <entry_id>` - Vote for a match\n"
            "- `announce <channel> <match_id>` - Announce match\n"
            "- `tally <match_id>` - Get results"
        )
    
    @staticmethod
    async def create_match(data, args: list):
        """Create a match."""
        try:
            if not data.message.member.guild_permissions.manage_roles:
                admin_ids = getattr(data.artemis.config, 'ADMIN_USER_IDS', [])
                if str(data.message.author.id) not in admin_ids:
                    await MatchVoting.unauthorized(data.message)
                    return
            
            if not args:
                await data.message.reply("Usage: `!match create <title> [period]`")
                return
            
            title = args[0]
            period = args[1] if len(args) > 1 else "24h"
            
            try:
                parsed_time = MatchVoting.read_time(period)
                deadline = datetime.now(pytz.UTC) + (parsed_time - datetime.now(pytz.UTC))
            except:
                deadline = datetime.now(pytz.UTC)
                import dateutil.relativedelta as rd
                deadline += rd.relativedelta(hours=24)
            
            import time
            match_id = f"{int(time.time() * 1000)}"
            
            await data.artemis.storage.set("match_matches", match_id, {
                "match_id": match_id,
                "created": datetime.now(pytz.UTC).isoformat(),
                "duedate": deadline.isoformat(),
                "title": title
            })
            
            await data.message.reply(
                f"Match \"{title}\" has been added with a deadline of *{deadline.strftime('%Y-%m-%d %H:%M:%S UTC')}*.\n"
                f"Add competitors using `!match addcompetitor {match_id} <user> [<data>]`."
            )
        except Exception as e:
            await MatchVoting.exception_handler(data.message, e)
    
    @staticmethod
    async def add_competitor(data, args: list):
        """Add competitor to match."""
        try:
            if not data.message.member.guild_permissions.manage_roles:
                admin_ids = getattr(data.artemis.config, 'ADMIN_USER_IDS', [])
                if str(data.message.author.id) not in admin_ids:
                    await MatchVoting.unauthorized(data.message)
                    return
            
            if len(args) < 2:
                await data.message.reply("Usage: `!match addcompetitor <match_id> <user> [data]`")
                return
            
            match_id = args[0]
            user_text = args[1]
            competitor_data = " ".join(args[2:]) if len(args) > 2 else None
            
            member = await MatchVoting.parse_guild_user(data.guild, user_text)
            if not member:
                await data.message.reply("Could not parse user.")
                return
            
            import time
            competitor_id = f"{int(time.time() * 1000)}"
            
            await data.artemis.storage.set("match_competitors", f"{match_id}_{competitor_id}", {
                "competitor_id": competitor_id,
                "match_id": match_id,
                "discord_id": str(member.id),
                "created": datetime.now(pytz.UTC).isoformat(),
                "data": competitor_data
            })
            
            await data.message.reply(
                f"Competitor {member.mention} added with value `{competitor_data or '<no data>'}`\n"
                f"Add more competitors or announce with `!match announce <room> {match_id}`."
            )
        except Exception as e:
            await MatchVoting.exception_handler(data.message, e)
    
    @staticmethod
    async def vote_match(data, args: list):
        """Vote for a match."""
        try:
            if data.message.author.bot:
                await data.message.reply("Bots can't vote.")
                return
            
            if len(args) < 2:
                await data.message.reply("Usage: `!match vote <match_id> <entry_id>`")
                return
            
            match_id = args[0]
            entry_id = args[1]
            
            match_data = await data.artemis.storage.get("match_matches", match_id)
            if not match_data:
                await data.message.reply("Match not found.")
                await data.message.delete()
                return
            
            deadline = datetime.fromisoformat(match_data["duedate"].replace('Z', '+00:00'))
            if deadline < datetime.now(pytz.UTC):
                await data.message.reply("Voting has expired for that match.")
                await data.message.delete()
                return
            
            await data.artemis.storage.set("match_votes", f"{match_id}_{data.message.author.id}", {
                "voter_id": str(data.message.author.id),
                "match_id": match_id,
                "competitor_id": entry_id,
                "created": datetime.now(pytz.UTC).isoformat()
            })
            
            await data.message.reply(f"{data.message.member.display_name}, your vote for match ID `{match_id}` has been recorded!")
            await data.message.delete()
        except Exception as e:
            await MatchVoting.exception_handler(data.message, e)
    
    @staticmethod
    async def announce_match(data, args: list):
        """Announce a match."""
        try:
            admin_ids = getattr(data.artemis.config, 'ADMIN_USER_IDS', [])
            if str(data.message.author.id) not in admin_ids:
                await MatchVoting.unauthorized(data.message)
                return
            
            if len(args) < 2:
                await data.message.reply("Usage: `!match announce <channel> <match_id>`")
                return
            
            channel_text = args[0]
            match_id = args[1]
            
            channel = MatchVoting.channel_mention(channel_text, data.guild)
            if not channel:
                await data.message.reply("Invalid channel.")
                return
            
            match_data = await data.artemis.storage.get("match_matches", match_id)
            if not match_data:
                await data.message.reply("Match not found.")
                return
            
            competitors_data = await data.artemis.storage.get_all("match_competitors")
            competitors = [
                v for k, v in competitors_data.items()
                if isinstance(v, dict) and v.get("match_id") == match_id
            ]
            
            deadline = datetime.fromisoformat(match_data["duedate"].replace('Z', '+00:00'))
            
            embed = Embed(
                title=match_data["title"],
                description=f"Voting is open until *{deadline.strftime('%Y-%m-%d %H:%M:%S UTC')}*",
                timestamp=deadline
            )
            
            for i, comp in enumerate(competitors, 1):
                member = data.guild.get_member(int(comp["discord_id"]))
                comp_data = comp.get("data", "<no data>")
                embed.add_field(
                    name=f"Option {i}",
                    value=f"{comp_data}\nVote with `!match vote {match_id} {comp['competitor_id']}`",
                    inline=False
                )
            
            await channel.send("A match is available for voting!", embed=embed)
            await data.message.reply("Announcement sent!")
        except Exception as e:
            await MatchVoting.exception_handler(data.message, e)
    
    @staticmethod
    async def tally_handler(data):
        """Handle tally command."""
        try:
            args = MatchVoting.split_command(data.message.content)
            if len(args) < 2:
                await data.message.reply("Usage: `!tally <match_id>`")
                return
            
            match_id = args[1]
            
            match_data = await data.artemis.storage.get("match_matches", match_id)
            if not match_data:
                await data.message.reply("Match not found.")
                return
            
            competitors_data = await data.artemis.storage.get_all("match_competitors")
            competitors = {
                v["competitor_id"]: v
                for k, v in competitors_data.items()
                if isinstance(v, dict) and v.get("match_id") == match_id
            }
            
            votes_data = await data.artemis.storage.get_all("match_votes")
            votes = [
                v for k, v in votes_data.items()
                if isinstance(v, dict) and v.get("match_id") == match_id
            ]
            
            deadline = datetime.fromisoformat(match_data["duedate"].replace('Z', '+00:00'))
            
            resp = []
            resp.append(f"__**Match {match_data['title']}**__ `{match_id}`")
            resp.append(f"Deadline: *{deadline.strftime('%Y-%m-%d %H:%M:%S UTC')}*")
            resp.append("")
            
            admin_ids = getattr(data.artemis.config, 'ADMIN_USER_IDS', [])
            is_admin = str(data.message.author.id) in admin_ids
            
            total_votes = len(votes)
            resp.append(f"Total votes: {total_votes}")
            
            if is_admin:
                for comp_id, comp in competitors.items():
                    comp_votes = [v for v in votes if v.get("competitor_id") == comp_id]
                    member = data.guild.get_member(int(comp["discord_id"]))
                    voter_names = []
                    for vote in comp_votes:
                        voter = data.guild.get_member(int(vote["voter_id"]))
                        if voter:
                            voter_names.append(voter.display_name)
                    
                    resp.append(f"Competitor {member.display_name if member else 'Unknown'} (ID {comp_id}) - Data `{comp.get('data', '<null>')}`")
                    resp.append(f"{len(comp_votes)} votes - {', '.join(voter_names) if voter_names else 'None'}")
                    resp.append("")
            
            response_text = "\n".join(resp)
            if len(response_text) > 2000:
                chunks = [response_text[i:i+2000] for i in range(0, len(response_text), 2000)]
                for chunk in chunks:
                    await data.message.channel.send(chunk)
            else:
                await data.message.channel.send(response_text)
        except Exception as e:
            await MatchVoting.exception_handler(data.message, e)
