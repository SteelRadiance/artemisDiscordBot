"""
Copyright 2025, Vijay Challa - Use of this source code follows the MIT license found in the LICENSE file.

Agenda Plugin - Staff motion/voting tally system

This plugin provides a voting system for staff motions. It allows staff members to vote
on proposals using reactions, and then tabulates the results including vote counts,
quorum status, and tiebreaker logic. The plugin fires an 'agendaPluginConf' event that
other plugins can listen to for custom voting configurations.

Commands:
    !agenda <message_url_or_id> - Tally votes from a message with reactions

Features:
    - Tracks votes from staff members based on role membership
    - Supports multiple vote types (For, Against, Abstain, Absent)
    - Calculates quorum requirements
    - Handles tiebreaker roles for breaking ties
    - Provides detailed vote breakdowns with voter names
"""

import logging
import disnake
from datetime import datetime

from artemis.plugin.base import PluginInterface, PluginHelper
from artemis.events.listener import EventListener

logger = logging.getLogger("artemis.plugin.agenda")


class Agenda(PluginInterface, PluginHelper):
    """Agenda plugin for voting tally."""
    
    CONF_TPL = {
        'staffRole': 741883050278912050,
        'tiebreakerRole': 766785052163571734,
        'quorum': 2/3,
        'voteTypes': {
            "For": 747168156866314282,
            "Against": 747168184246861914,
            "Abstain": "👀",
            "Absent": None,
        },
    }
    
    @staticmethod
    def register(bot):
        """Register the plugin."""
        if Agenda.is_testing_client(bot):
            bot.log.info("Not adding agenda commands on testing.")
            return
        
        bot.eventManager.add_listener(
            EventListener.new()
            .add_command("agenda")
            .set_callback(Agenda.agenda_tally_handler)
            .set_help("**Usage**: `!agenda <message_url_or_id>`\n\nTally votes from a message with reactions. Counts votes from staff members based on configured vote types (For, Against, Abstain, Absent) and provides a detailed breakdown including quorum status.")
        )
        
        # Register event listener for configuration
        bot.eventManager.add_listener(
            EventListener.new()
            .add_event("agendaPluginConf")
            .set_callback(Agenda.handle_config_event)
        )
    
    @staticmethod
    async def handle_config_event(bot, configs: dict):
        """Handle agenda configuration event."""
        pass
    
    @staticmethod
    async def agenda_tally_handler(data):
        """Handle agenda tally command."""
        try:
            config = Agenda.CONF_TPL.copy()
            
            msg_ref = Agenda.arg_substr(data.message.content, 1, 1)
            if not msg_ref:
                await data.message.reply("Usage: `!agenda <message_url_or_id>`")
                return
            
            import_msg = await Agenda.fetch_message(data.artemis, msg_ref)
            if not import_msg:
                await data.message.reply("Could not find that message.")
                return
            
            import_msg = await data.message.channel.fetch_message(import_msg.id)
            
            staff_role_id = config.get('staffRole', 0)
            staff_members = {}
            if staff_role_id:
                staff_role = data.guild.get_role(staff_role_id)
                if staff_role:
                    for member in data.guild.members:
                        if staff_role in member.roles:
                            staff_members[member.id] = None
            
            vote_types = config.get('voteTypes', {})
            vote_counts = {vote_type: [] for vote_type in vote_types.keys()}
            
            for reaction in import_msg.reactions:
                emoji_id = reaction.emoji.id if reaction.emoji.id else str(reaction.emoji)
                users = [user async for user in reaction.users()]
                
                vote_type = None
                for vt_name, vt_id in vote_types.items():
                    if str(vt_id) == str(emoji_id) or (isinstance(vt_id, str) and vt_id == str(reaction.emoji)):
                        vote_type = vt_name
                        break
                
                if vote_type:
                    for user in users:
                        if user.id in staff_members:
                            staff_members[user.id] = vote_type
            
            total_staff = len(staff_members)
            present = sum(1 for v in staff_members.values() if v is not None)
            
            for member_id, vote_type in staff_members.items():
                if vote_type:
                    vote_counts[vote_type].append(member_id)
            
            totals = {vt: len(vote_counts[vt]) for vt in vote_types.keys()}
            
            resp = []
            resp.append(f"__**{data.guild.name} - Staff Motion Results**__")
            resp.append(f"*Motion date:* `{import_msg.created_at.strftime('%Y-%m-%d %H:%M:%S')}`, *tabulated:* `{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}`")
            resp.append(f"*Motion proposed by:* `{import_msg.author.display_name}` (`{import_msg.author}`)")
            resp.append("")
            
            qstr = f"{present}/{total_staff} staff voting ({present/total_staff*100:.1f}%)"
            if present >= total_staff * config['quorum']:
                resp.append(f"Quorum is present with {qstr}")
            else:
                resp.append(f"Quorum not present with {qstr}")
            resp.append("")
            resp.append("Motion text:")
            resp.append(f"> {import_msg.content[:500]}")
            resp.append("")
            
            for vote_type in vote_types.keys():
                count = totals[vote_type]
                voters = [data.guild.get_member(uid) for uid in vote_counts[vote_type]]
                voter_names = ", ".join([v.display_name for v in voters if v])
                resp.append(f"*{vote_type}*: {count} ({voter_names})")
            
            if totals['For'] > totals['Against']:
                resp.append("**Motion passes**")
                copyres = "Passed"
            elif totals['For'] == totals['Against']:
                tiebreaker_role_id = config.get('tiebreakerRole', 0)
                if tiebreaker_role_id:
                    tiebreaker_role = data.guild.get_role(tiebreaker_role_id)
                    if tiebreaker_role:
                        tiebreaker = next((m for m in data.guild.members if tiebreaker_role in m.roles), None)
                        if tiebreaker and tiebreaker.id in staff_members:
                            tiebreaker_vote = staff_members[tiebreaker.id]
                            if tiebreaker_vote == 'For':
                                resp.append("**Motion passes**")
                                copyres = "Passed"
                            elif tiebreaker_vote == 'Against':
                                resp.append("**Motion fails**")
                                copyres = "Failed"
                            else:
                                resp.append("**Unbroken tie**")
                                copyres = "Failed (unbroken tie)"
                        else:
                            resp.append("**Unbroken tie**")
                            copyres = "Failed (unbroken tie)"
                    else:
                        resp.append("**Unbroken tie**")
                        copyres = "Failed (unbroken tie)"
                else:
                    resp.append("**Unbroken tie**")
                    copyres = "Failed (unbroken tie)"
            else:
                resp.append("**Motion fails**")
                copyres = "Failed"
            
            copycount = f"[{totals['For']} for, {totals['Against']} against, {totals['Abstain']} abstained, {total_staff - present} absent]"
            
            resp.append("")
            resp.append("Copyable version:")
            resp.append("```markdown")
            resp.append(f"{data.guild.name} - Staff Motion Results **{copyres}** {copycount}")
            resp.append(import_msg.content[:500])
            resp.append("```")
            
            response_text = "\n".join(resp)
            if len(response_text) > 2000:
                chunks = [response_text[i:i+2000] for i in range(0, len(response_text), 2000)]
                for chunk in chunks:
                    await data.message.channel.send(chunk)
            else:
                await data.message.channel.send(response_text)
        except Exception as e:
            await Agenda.exception_handler(data.message, e, True)
