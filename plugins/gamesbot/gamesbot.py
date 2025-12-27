"""
Copyright 2025, Vijay Challa - Use of this source code follows the MIT license found in the LICENSE file.

GamesBot Plugin - Game tagging system

This plugin allows users to tag themselves with games they play, making it easy
for others to find and ping players interested in specific games. Users can add
or remove game tags, view all available game tags, and ping everyone with a
particular game tag.

Commands:
    !gamesbot add <game> - Add yourself to a game tag
    !gamesbot remove <game> - Remove yourself from a game tag
    !gamesbot list - List all game tags and member counts
    !gamesbot ping <game> - Ping all members with a game tag
    
Shortcuts:
    !gb - Alias for !gamesbot

Features:
    - Per-guild game tagging system
    - Shows member count for each game tag
    - Highlights games the user has tagged themselves with
    - Easy ping functionality to find players
    - Case-insensitive game matching
"""

import logging
import disnake
from disnake import Embed

from artemis.plugin.base import PluginInterface, PluginHelper
from artemis.events.listener import EventListener

logger = logging.getLogger("artemis.plugin.gamesbot")


class GamesBot(PluginInterface, PluginHelper):
    """GamesBot plugin for game tagging."""
    
    @staticmethod
    def register(bot):
        """Register the plugin."""
        if GamesBot.is_testing_client(bot):
            bot.log.info("Not adding gamesbot commands on testing.")
            return
        
        for cmd in ["gamesbot", "gamebot", "gb"]:
            bot.eventManager.add_listener(
                EventListener.new()
                .add_command(cmd)
                .set_callback(GamesBot.game_handler)
                .set_help(GamesBot.get_help)
            )
    
    @staticmethod
    async def game_handler(data):
        """Handle gamesbot command."""
        try:
            args = GamesBot.split_command(data.message.content)
            if len(args) < 2:
                await data.message.reply(GamesBot.get_help())
                return
            
            command = args[1].lower()
            
            if command == "add":
                await GamesBot.add_game_handler(data, args[2:] if len(args) > 2 else [])
            elif command == "remove":
                await GamesBot.remove_game_handler(data, args[2:] if len(args) > 2 else [])
            elif command == "list":
                await GamesBot.list_game_handler(data, args[2:] if len(args) > 2 else [])
            elif command == "ping":
                await GamesBot.ping_game_handler(data, args[2:] if len(args) > 2 else [])
            elif len(args) > 2 and args[-1].lower() == "show":
                await GamesBot.show_game_handler(data, args[1:-1])
            else:
                await data.message.reply(GamesBot.get_help())
        except Exception as e:
            await GamesBot.exception_handler(data.message, e, False)
    
    @staticmethod
    def get_help() -> str:
        """Get help text."""
        return (
            "**Usage**: `!gamesbot (command) (argument)` or `!gb (command) (argument)`\n\n"
            "valid commands:\n"
            "- `add`: add yourself to a game\n"
            "- `remove`: remove yourself from a game\n"
            "- `list`: show current game tags in use\n"
            "- `ping`: ping a particular game\n"
            "- `<game> show`: list everyone who plays that game (without pinging)"
        )
    
    @staticmethod
    async def add_game_handler(data, args: list):
        """Add game tag."""
        try:
            if not args:
                await data.message.reply("Usage: `!gamesbot add GAME`")
                return
            
            game = " ".join(args).lower()
            member = data.guild.get_member(data.message.author.id) if data.guild else None
            if not member:
                await data.message.reply("Could not find member information.")
                return
            
            await GamesBot.add_game(data, member, game)
            await data.message.reply(f"`{member.display_name}` has been added to `{game}`")
        except Exception as e:
            await GamesBot.exception_handler(data.message, e)
    
    @staticmethod
    async def add_game(data, member: disnake.Member, game: str):
        """Add game to storage."""
        try:
            await data.artemis.storage.set("gamesbot_games", f"{data.guild.id}_{member.id}_{game}", {
                "member_id": str(member.id),
                "guild_id": str(data.guild.id),
                "game": game
            })
        except Exception as e:
            logger.error(f"Failed to add game: {e}")
    
    @staticmethod
    async def remove_game_handler(data, args: list):
        """Remove game tag."""
        try:
            if not args:
                await data.message.reply("Usage: `!gamesbot remove GAME`")
                return
            
            game = " ".join(args).lower()
            member = data.guild.get_member(data.message.author.id) if data.guild else None
            if not member:
                await data.message.reply("Could not find member information.")
                return
            
            await GamesBot.remove_game(data, member, game)
            await data.message.reply(f"`{member.display_name}` has been removed from `{game}`")
        except Exception as e:
            await GamesBot.exception_handler(data.message, e)
    
    @staticmethod
    async def remove_game(data, member: disnake.Member, game: str):
        """Remove game from storage."""
        try:
            await data.artemis.storage.delete("gamesbot_games", f"{data.guild.id}_{member.id}_{game}")
        except Exception as e:
            logger.error(f"Failed to remove game: {e}")
    
    @staticmethod
    async def list_game_handler(data, args: list):
        """List game tags."""
        try:
            games = await GamesBot.get_games(data.guild)
            
            member = data.guild.get_member(data.message.author.id) if data.guild else None
            member_color = member.color if member and member.color.value else 0x00ff00
            
            embed = Embed(
                title=f"Games - {data.guild.name}",
                color=member_color
            )
            
            if games:
                sorted_games = sorted(games.items(), key=lambda x: (-len(x[1]), x[0]))
                
                entries = []
                author_id_str = str(data.message.author.id)
                for game, member_ids in sorted_games:
                    star = "⭐" if author_id_str in member_ids else ""
                    entries.append(f"{star} ({len(member_ids)}) {game}")
                
                entries_text = "\n".join(entries)
                
                if len(entries_text) > 1024:
                    chunks = [entries_text[i:i+1024] for i in range(0, len(entries_text), 1024)]
                    for i, chunk in enumerate(chunks):
                        embed.add_field(
                            name="Games" if i == 0 else "Games (cont.)",
                            value=chunk,
                            inline=True
                        )
                else:
                    embed.add_field(name="Games", value=entries_text, inline=True)
                
                embed.description = (
                    "Use `!gamesbot add GAME` to add a game\n"
                    "A ⭐ indicates you have that game added\n"
                    "The number in parentheses shows how many server members have that tag"
                )
            else:
                embed.description = "No games found. Use `!gamesbot add GAME` to add one!"
            
            await data.message.reply(embed=embed)
        except Exception as e:
            await GamesBot.exception_handler(data.message, e)
    
    @staticmethod
    async def ping_game_handler(data, args: list):
        """Ping game tag."""
        try:
            if not args:
                await data.message.reply("Usage: `!gamesbot ping GAME`")
                return
            
            game = " ".join(args).lower()
            games = await GamesBot.get_games(data.guild)
            
            if game not in games:
                await data.message.reply(f"No members with `{game}` are present on this server")
                return
            
            member_ids = games[game]
            members = []
            for mid in member_ids:
                member = data.guild.get_member(int(mid))
                if member:
                    members.append(member)
            member_mentions = ", ".join([m.mention for m in members])
            
            member = data.guild.get_member(data.message.author.id) if data.guild else None
            display_name = member.display_name if member else data.message.author.display_name
            await data.message.channel.send(f"`{display_name}` wants to play `{game}`\n{member_mentions}")
        except Exception as e:
            await GamesBot.exception_handler(data.message, e)
    
    @staticmethod
    async def show_game_handler(data, args: list):
        """Show game tag players without pinging."""
        try:
            if not args:
                await data.message.reply("Usage: `!gamesbot <game> show`")
                return
            
            game = " ".join(args).lower()
            games = await GamesBot.get_games(data.guild)
            
            if game not in games:
                await data.message.reply(f"No members with `{game}` are present on this server")
                return
            
            member_ids = games[game]
            members = []
            for mid in member_ids:
                member = data.guild.get_member(int(mid))
                if member:
                    members.append(member)
            
            if not members:
                await data.message.reply(f"No members with `{game}` are currently in this server")
                return
            
            member_names = ", ".join([m.display_name for m in members])
            
            embed = Embed(
                title=f"Players of {game}",
                description=f"**{len(members)} player(s):**\n{member_names}",
                color=0x00ff00
            )
            
            await data.message.reply(embed=embed)
        except Exception as e:
            await GamesBot.exception_handler(data.message, e)
    
    @staticmethod
    async def get_games(guild: disnake.Guild) -> dict:
        """Get all games for a guild."""
        try:
            storage = guild._state._get_client().storage if hasattr(guild._state, '_get_client') else None
            if not storage:
                return {}
            
            games_data = await storage.get_all("gamesbot_games")
            games = {}
            
            for key, value in games_data.items():
                if isinstance(value, dict) and value.get("guild_id") == str(guild.id):
                    game = value.get("game", "").lower()
                    member_id = value.get("member_id")
                    if game and member_id:
                        if game not in games:
                            games[game] = []
                        games[game].append(member_id)
            
            return games
        except Exception as e:
            logger.error(f"Failed to get games: {e}")
            return {}
