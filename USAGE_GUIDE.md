# Artemis Bot Usage Guide

This guide will help you add Artemis to your Discord server, configure permissions, and use its commands.

## Table of Contents

1. [Adding the Bot to Your Server](#adding-the-bot-to-your-server)
2. [Setting Up Permissions](#setting-up-permissions)
3. [Available Commands](#available-commands)
4. [Plugin-Specific Usage](#plugin-specific-usage)
5. [Troubleshooting](#troubleshooting)

---

## Adding the Bot to Your Server

### Step 1: Generate Invite URL

1. Run the `!invite` command in any server where the bot is already present, OR
2. Manually create an invite URL with the following permissions:
   - **Bot** scope
   - **Applications Commands** scope
   - Required permissions:
     - View Channels
     - Send Messages
     - Embed Links
     - Attach Files
     - Read Message History
     - View Audit Log (for AuditLog plugin)

### Step 2: Invite the Bot

1. Click the generated invite URL or use the manual invite link
2. Select your server from the dropdown
3. Review and authorize the permissions
4. Click "Authorize"

### Step 3: Verify Bot is Online

Once added, you should see the bot appear in your server's member list. The bot will automatically start monitoring and responding to commands.

---

## Setting Up Permissions

Artemis uses a permission system to control who can use which features. Permissions are configured per-plugin and can be set for:
- **Roles**: All members with a specific role
- **Users**: Specific users by Discord ID
- **Default**: Default permission state (allow/deny)

### Permission Format

Permissions follow this format: `p.<plugin>.<feature>`

Examples:
- `p.auditlog.view` - View audit logs
- `p.serveractivity.view` - View server activity statistics
- `p.management.restart` - Restart the bot (admin only)

### Default Permissions

By default, the following permissions apply:

- **Admin Users**: Users listed in `ADMIN_USER_IDS` in the config have access to all commands
- **Management Commands**: 
  - `!ping` - Everyone
  - `!artemis` - Everyone
  - `!restart` - Admin only
  - `!update` - Admin only
  - `!invite` - Everyone
- **ServerActivity**: 
  - `!messagestats` - Default: allowed (can be restricted)
- **AuditLog**: 
  - `!auditlog` - Default: denied (requires permission)
- **User**: 
  - `!user` - Everyone
  - `!roster` - Default: allowed
  - `!av` - Everyone
- **Role**: 
  - `!role`, `!roles` - Default: allowed
  - `!bindrole` - Default: denied
  - `!inheritrole` - Default: denied
- **Event**: 
  - `!event` - Default: allowed
  - `!calendar` - Everyone
  - `!setCalendar` - Default: denied
- **Remind**: 
  - `!remind`, `!rem`, `!remindme`, `!reminder` - Everyone
- **Agenda**: 
  - `!agenda` - Everyone
- **State**: 
  - `!state` - Default: denied
- **Archive**: 
  - `!archive` - Admin only
- **GamesBot**: 
  - `!gamesbot`, `!gamebot`, `!gb` - Everyone
- **MatchVoting**: 
  - `!match` - Everyone (create/addcompetitor/announce: admin)
  - `!tally` - Everyone
- **Observer**: 
  - `!observer` - Admin only
- **Localization**: 
  - `!time` - Everyone
  - `!timezone` - Everyone
- **PermissionFrontend**: 
  - `!permission`, `!perm`, `!hpm` - Everyone (add: restricted)

### Configuring Permissions

Permissions are stored in JSON format. To configure permissions:

1. **Via Code** (for developers): Modify the permission resolver in `artemis/permissions/resolver.py`
2. **Via Storage** (future): Permissions can be stored in JSON files under `storage/permissions/`

Example permission structure:
```json
{
  "p.auditlog.view": {
    "guild_id": "123456789",
    "allowed": true,
    "roles": ["987654321"],
    "users": ["111222333"]
  }
}
```

### Setting Admin Users

To grant full admin access, add user IDs to the `ADMIN_USER_IDS` list in `config/config.py`:

```python
ADMIN_USER_IDS = [
    "123456789012345678",  # Your Discord User ID
    "987654321098765432",  # Another admin's ID
]
```

**How to find your User ID:**
1. Enable Developer Mode in Discord (User Settings → Advanced → Developer Mode)
2. Right-click on your username/avatar
3. Click "Copy ID"

---

## Available Commands

All commands use the prefix `!` by default (configurable in `config/config.py`).

### Management Commands

#### `!ping`
**Description**: Check bot latency and response time  
**Usage**: `!ping`  
**Permission**: Everyone  
**Example**:
```
You: !ping
Bot: Pong!
    123ms ping (artemis-rx)
    45ms ping (msg-snowflake)
```

#### `!artemis`
**Description**: Display bot information including memory usage, uptime, loaded plugins, dependencies, and emoji-based version hashes  
**Usage**: `!artemis`  
**Permission**: Everyone  
**Example**:
```
You: !artemis
Bot: [Embed with bot statistics and emoji hashes]
```

#### `!restart`
**Description**: Restart the bot (requires admin access)  
**Usage**: `!restart`  
**Permission**: Admin only  
**Example**:
```
You: !restart
Bot: 🃏🔫
[Bot restarts]
```

#### `!update`
**Description**: Pull latest code from git repository (requires admin access)  
**Usage**: `!update`  
**Permission**: Admin only  
**Example**:
```
You: !update
Bot: ```
     Already up to date.
     ```
```

#### `!invite`
**Description**: Generate an OAuth invite URL for adding the bot to other servers  
**Usage**: `!invite`  
**Permission**: Everyone  
**Example**:
```
You: !invite
Bot: Use the following URL to add this Artemis instance to your server!
     <https://discord.com/api/oauth2/authorize?...>
```

### ServerActivity Commands

#### `!messagestats`
**Description**: Display message activity statistics as graphs  
**Usage**: `!messagestats [all]`  
**Permission**: Default allowed (can be restricted)  
**Options**:
- No arguments: Shows day and week graphs
- `all`: Shows day, week, month, and year graphs

**Example**:
```
You: !messagestats
Bot: [Sends PNG images showing message activity graphs]

You: !messagestats all
Bot: [Sends PNG images showing extended statistics]
```

**Note**: Statistics are collected automatically. Graphs show:
- All messages (average and peak)
- Bot messages (average and peak)
- Message rates over time

### AuditLog Commands

#### `!auditlog`
**Description**: Output all stored audit log events as JSON  
**Usage**: `!auditlog`  
**Permission**: Requires `p.auditlog.view` permission (default: denied)  
**Example**:
```
You: !auditlog
Bot: ```json
     {
       "123456789": [
         {
           "id": "987654321",
           "guild_id": "123456789",
           "user_id": "111222333",
           "action": "MEMBER_BAN_ADD",
           "reason": "Spam",
           "created_at": "2024-01-15T10:30:00"
         }
       ]
     }
     ```
```

**Note**: 
- If output is too long (>2000 characters), it will be sent as a JSON file attachment
- Shows events for the current guild, or all guilds if none stored for current guild
- Audit logs are automatically fetched every 5 minutes

### User Commands

#### `!user`
**Description**: Display detailed user information including roles, permissions, and avatar  
**Usage**: `!user [user]`  
**Permission**: Everyone  
**Options**:
- No arguments: Shows information about yourself
- `[user]`: User mention, username#discriminator, or user ID

**Example**:
```
You: !user @SomeUser
Bot: [Embed with user information, roles, permissions]
```

#### `!roster`
**Description**: List all members with a specific role, sorted by join date  
**Usage**: `!roster <role>`  
**Permission**: Default allowed (can be restricted)  
**Example**:
```
You: !roster @Moderator
Bot: [Code block listing all moderators with join dates]
```

#### `!av`
**Description**: Get a user's avatar URL  
**Usage**: `!av [user]`  
**Permission**: Everyone  
**Example**:
```
You: !av @SomeUser
Bot: SomeUser's av: https://cdn.discordapp.com/avatars/...
```

### Role Commands

#### `!role` / `!roles`
**Description**: List available self-assignable roles or toggle a role  
**Usage**: `!role [role_name]`  
**Permission**: Default allowed (can be restricted)  
**Options**:
- No arguments: Lists all available roles
- `[role_name]`: Toggles the specified role

**Example**:
```
You: !role
Bot: [Embed listing all available roles]

You: !role Member
Bot: Role added: Member
```

#### `!bindrole`
**Description**: Make a role self-assignable (admin only)  
**Usage**: `!bindrole <role_id>`  
**Permission**: Default denied (requires `p.roles.bind`)  
**Example**:
```
You: !bindrole 123456789012345678
Bot: Role added to server bindings: Member
```

#### `!inheritrole`
**Description**: Set up role inheritance (admin only)  
**Usage**: `!inheritrole <source_role_id> <dest_role_id>`  
**Permission**: Default denied (requires `p.roles.bind`)  
**Example**:
```
You: !inheritrole 111111111111111111 222222222222222222
Bot: Role added to server role inheritance: Having @SourceRole will add @DestRole
```

**Note**: Role inheritance is checked every 10 seconds automatically.

### Event Commands

#### `!event`
**Description**: Add or remove an event from the calendar  
**Usage**: `!event <when> <title>` or `!event remove <event_id>`  
**Permission**: Default allowed (can be restricted)  
**Options**:
- `<when>`: Relative time (e.g., "5 hours", "next tuesday") or absolute time (e.g., "2025-02-18 5:00pm")
- `<title>`: Event name/description
- `remove <event_id>`: Remove an event you created

**Example**:
```
You: !event "next friday 7pm" Movie Night
Bot: [Embed confirming event creation with detected time]

You: !event remove 1234567890
Bot: If that was your event, it was removed :)
```

**Note**: Uses your timezone if set via `!timezone`, otherwise UTC.

#### `!calendar`
**Description**: View upcoming events for the server  
**Usage**: `!calendar`  
**Permission**: Everyone  
**Example**:
```
You: !calendar
Bot: [Embed showing upcoming events in your timezone]
```

#### `!setCalendar`
**Description**: Set a channel message to automatically update with the calendar (admin only)  
**Usage**: `!setCalendar <channel_mention>` or `!setCalendar <message_url>`  
**Permission**: Default denied (requires `p.events.setcalendar`)  
**Example**:
```
You: !setCalendar #events
Bot: Calendar set to https://discord.com/channels/...
```

**Note**: Calendar messages update automatically every minute.

### Remind Commands

#### `!remind` / `!rem` / `!remindme` / `!reminder`
**Description**: Set a reminder for yourself  
**Usage**: `!remind <when> [message]` or `!remind delete <reminder_id>`  
**Permission**: Everyone  
**Options**:
- `<when>`: Relative time (e.g., "2 hours", "tomorrow 3pm") or absolute time
- `[message]`: Optional reminder message
- `delete <reminder_id>`: Delete a pending reminder

**Example**:
```
You: !remind "in 30 minutes" Check the oven
Bot: [Embed confirming reminder with detected time]

You: !remind delete 1234567890
Bot: Reminder deleted.
```

**Note**: 
- Reminders are checked every 10 seconds
- Uses your timezone if set via `!timezone`, otherwise UTC
- Reminders are sent to the channel where they were created, or via DM if channel no longer exists

### Agenda Commands

#### `!agenda`
**Description**: Tally votes from reactions on a message for staff motions  
**Usage**: `!agenda <message_url_or_id>`  
**Permission**: Everyone  
**Example**:
```
You: !agenda https://discord.com/channels/.../.../123456789
Bot: [Detailed voting results with quorum check, vote breakdown, and result]
```

**Note**: 
- Requires configuration via `agendaPluginConf` event (plugins can provide this)
- Checks for quorum based on staff role membership
- Supports tiebreaker roles
- Shows vote breakdown by type (For/Against/Abstain/Absent)

### State Commands

#### `!state`
**Description**: Post an anonymous moderation statement  
**Usage**: `!state [channel] <message>`  
**Permission**: Default denied (requires `p.moderation.state`)  
**Options**:
- `[channel]`: Optional channel mention to post in (defaults to current channel)
- `<message>`: The statement text

**Example**:
```
You: !state #announcements Server maintenance scheduled for tomorrow
Bot: [Anonymous statement posted in #announcements with MOD STATEMENT embed]
```

**Note**: If posted to a different channel, the original message is deleted and a confirmation is sent.

### Archive Commands

#### `!archive`
**Description**: Archive all messages from a channel to a JSON file (admin only)  
**Usage**: `!archive <channel_mention>`  
**Permission**: Admin only  
**Example**:
```
You: !archive #old-channel
Bot: Beginning #old-channel (`old-channel`) archival...
     Done! 1234 messages saved. [File attachment]
```

**Note**: 
- Limited to bot owners only due to resource usage
- Files are saved to `temp/` directory
- Large archives are automatically compressed with gzip
- Includes message content, attachments, embeds, and user information

### GamesBot Commands

#### `!gamesbot` / `!gamebot` / `!gb`
**Description**: Manage game tags for finding players  
**Usage**: `!gamesbot <command> [arguments]`  
**Permission**: Everyone  
**Commands**:
- `add <game>` - Add yourself to a game tag
- `remove <game>` - Remove yourself from a game tag
- `list` - Show all game tags and member counts
- `ping <game>` - Ping all members with a game tag

**Example**:
```
You: !gamesbot add pathfinder
Bot: `YourName` has been added to `pathfinder`

You: !gamesbot ping pathfinder
Bot: `YourName` wants to play `pathfinder`
     @Player1, @Player2, @Player3
```

**Note**: Game tags are case-insensitive and stored per guild.

### MatchVoting Commands

#### `!match`
**Description**: Create and manage voting matches  
**Usage**: `!match <command> [arguments]`  
**Permission**: Varies by command  
**Commands**:
- `create <title> [period]` - Create a match (admin only, default period: 24h)
- `addcompetitor <match_id> <user> [data]` - Add competitor (admin only)
- `vote <match_id> <entry_id>` - Vote for a match (everyone)
- `announce <channel> <match_id>` - Announce match for voting (admin only)

**Example**:
```
You: !match create "Best Story" 48h
Bot: Match "Best Story" has been added with a deadline of *2025-02-20 12:00:00 UTC*.
     Add competitors using `!match addcompetitor 1234567890 <user> [<data>]`.

You: !match vote 1234567890 9876543210
Bot: YourName, your vote for match ID `1234567890` has been recorded!
     [Message deleted]
```

#### `!tally`
**Description**: Get voting results for a match  
**Usage**: `!tally <match_id>`  
**Permission**: Everyone (detailed results: admin only)  
**Example**:
```
You: !tally 1234567890
Bot: __**Match Best Story**__ `1234567890`
     Deadline: *in 12 hours*
     Total votes: 15
     [Detailed breakdown if admin]
```

**Note**: 
- Voting messages are automatically deleted after voting
- Only one vote per user per match
- Votes can be changed by voting again

### Observer Commands

#### `!observer`
**Description**: Configure moderation logging (admin only)  
**Usage**: `!observer <channel_id>` or `!observer <emote_id>`  
**Permission**: Admin only  
**Example**:
```
You: !observer 123456789012345678
Bot: #mod-logs set as reporting channel for guild `ServerName`

You: !observer 987654321098765432
Bot: `987654321098765432` set as reporting emote for guild `ServerName`
```

**Features**:
- Logs message deletions
- Logs member joins/leaves
- Logs invite creation
- Handles user reports via reactions (when configured)

**Note**: 
- First argument sets the logging channel
- Second argument sets the report emote ID
- Reports are sent when users react with the configured emote

### Localization Commands

#### `!timezone`
**Description**: Set or view your timezone  
**Usage**: `!timezone [timezone]`  
**Permission**: Everyone  
**Example**:
```
You: !timezone America/New_York
Bot: Your timezone has been updated to **America/New_York**.
     I have your local time as **Monday, January 15, 2024 03:45:30 PM**

You: !timezone
Bot: Your timezone is currently set to **America/New_York**.
     I have your local time as **Monday, January 15, 2024 03:45:30 PM**
```

**Note**: 
- Use timezone names from [PHP timezone list](https://www.php.net/manual/en/timezones.php)
- Prefer Continent/City format (e.g., `America/New_York`) for automatic DST handling
- Your timezone is used by Event and Remind plugins

#### `!time`
**Description**: Convert a time to all timezones of users in the channel  
**Usage**: `!time <time>`  
**Permission**: Everyone  
**Example**:
```
You: !time "next friday 7pm"
Bot: [Embed showing the time converted to all timezones of channel members]
```

**Note**: Only shows timezones for users who have set their timezone via `!timezone`.

### PermissionFrontend Commands

#### `!permission` / `!perm` / `!hpm`
**Description**: Manage permissions for commands and features  
**Usage**: `!permission <command> [options]`  
**Permission**: Varies by command  
**Commands**:
- `check <permission> [user]` - Check permission status
- `add <permission> [options]` - Add permission rule

**Options for `add`**:
- `--deny` - Deny instead of allow
- `--scope <global|guild|channel>` - Set scope (default: guild)
- `--all` - Target all users
- `--role <role>` - Target specific role
- `--user <user>` - Target specific user
- `--admins` - Target guild administrators
- `--evalusers` - Target bot owners

**Example**:
```
You: !permission check p.auditlog.view
Bot: [Embed showing permission check result]

You: !permission add p.auditlog.view --role @Moderator
Bot: The following permission has been added:
     **Allow**: `p.auditlog.view`
     **Scope**: Within this guild (`ServerName`)
     **Target**: Users with the @Moderator role
```

**Note**: 
- Global scope and bot admin permissions require bot owner access
- Guild scope requires guild owner or administrator permission
- Channel scope requires manage channels permission

---

## Plugin-Specific Usage

### Management Plugin

The Management plugin provides core bot functionality and is always enabled.

**Features**:
- Bot health monitoring
- System information
- Administrative controls

**Requirements**: No special setup needed.

### ServerActivity Plugin

Tracks message statistics per guild using RRDtool.

**Features**:
- Automatic message counting
- Activity graphs
- Per-guild statistics

**Requirements**:
- RRDtool must be installed on the server
- On Windows: Requires WSL (Windows Subsystem for Linux) with rrdtool installed
- Bot needs to be able to write to `temp/serveractivity/` directory

**Setup**:
1. Install RRDtool:
   - **Linux**: `sudo apt-get install rrdtool` or `sudo yum install rrdtool`
   - **Windows**: Install via WSL: `wsl sudo apt-get install rrdtool`
2. Ensure `temp/serveractivity/` directory exists and is writable
3. The plugin will automatically create RRD files for each guild

**Data Collection**:
- Messages are counted every 6 seconds
- Data is stored in RRD format for efficient time-series storage
- Graphs are generated on-demand when `!messagestats` is used

### AuditLog Plugin

Monitors and stores Discord audit log events.

**Features**:
- Automatic audit log fetching (every 10 seconds - as often as Discord's API allows)
- Rate limit handling with automatic backoff
- Unique event tracking (no duplicates)
- Persistent storage (survives bot restarts)
- JSON export

**Requirements**:
- Bot must have "View Audit Log" permission in the server
- Bot needs to be able to write to `storage/audit_log/` directory

**Setup**:
1. Ensure the bot has "View Audit Log" permission:
   - Go to Server Settings → Roles
   - Select the bot's role
   - Enable "View Audit Log" permission
2. The plugin will automatically start fetching audit logs

**What Gets Tracked**:
- All audit log entry types (bans, kicks, role changes, etc.)
- User who performed the action
- Target of the action
- Reason (if provided)
- Changes made
- Timestamp

**Storage**:
- Events are stored both in memory (for fast access) and JSON files (for persistence)
- Files are stored in `storage/audit_log/` directory
- Format: `{guild_id}_{entry_id}.json`

### User Plugin

Provides user information and utilities.

**Features**:
- User information display
- Role roster listing
- Avatar URL retrieval

**Requirements**: No special setup needed.

**Commands**: `!user`, `!roster`, `!av`

### Role Plugin

Self-assignable role management system.

**Features**:
- Role self-assignment
- Role inheritance (automatic role granting)
- Role binding (making roles self-assignable)

**Requirements**:
- Bot needs "Manage Roles" permission
- Bot's role must be higher than roles being assigned

**Setup**:
1. Use `!bindrole <role_id>` to make a role self-assignable
2. Users can then use `!role <role_name>` to toggle the role
3. Use `!inheritrole <source> <dest>` to set up inheritance

**Storage**:
- Role bindings stored in `storage/roles/`
- Inheritance rules stored in `storage/roles_inherit/`
- Inheritance is checked every 10 seconds

### Event Plugin

Event calendar system with timezone support.

**Features**:
- Event creation and management
- Calendar display
- Automatic calendar message updates
- Timezone-aware scheduling

**Requirements**: No special setup needed.

**Setup**:
1. Users set their timezone with `!timezone`
2. Create events with `!event <when> <title>`
3. View calendar with `!calendar`
4. (Optional) Set auto-updating calendar message with `!setCalendar`

**Storage**:
- Events stored in `storage/event/`
- Calendar message references stored in `storage/event_calendar/`
- Calendar updates every 60 seconds

**Time Parsing**:
- Supports relative times: "5 hours", "next tuesday", "2d3h"
- Supports absolute times: "2025-02-18 5:00pm", "september 3rd"
- Uses user's timezone if set, otherwise UTC

### Remind Plugin

Personal reminder system.

**Features**:
- Reminder creation
- Automatic reminder delivery
- Reminder deletion
- Timezone-aware scheduling

**Requirements**: No special setup needed.

**Storage**:
- Reminders stored in `storage/remind/`
- Checked every 10 seconds
- Reminders sent to original channel or via DM if channel deleted

**Usage**:
- Set reminders with `!remind <when> [message]`
- Delete reminders with `!remind delete <id>`
- Reminder ID shown in footer of confirmation message

### Agenda Plugin

Staff motion voting and tally system.

**Features**:
- Reaction-based voting tally
- Quorum checking
- Tiebreaker support
- Vote breakdown by type

**Requirements**:
- Requires configuration via `agendaPluginConf` event
- Other plugins can provide configuration (e.g., Ironreach plugin)

**Usage**:
1. Post a motion message
2. Staff react with configured vote types (For/Against/Abstain)
3. Run `!agenda <message_url>` to tally votes

**Configuration** (via other plugins):
- Staff role ID
- Tiebreaker role ID
- Quorum percentage
- Vote type emoji/role IDs

### State Plugin

Anonymous moderation statement system.

**Features**:
- Anonymous mod statements
- Cross-channel posting
- Mention support

**Requirements**:
- Requires `p.moderation.state` permission (default: denied)

**Usage**:
- `!state <message>` - Post in current channel
- `!state #channel <message>` - Post in specified channel

### Archive Plugin

Channel message archiving tool.

**Features**:
- Complete channel message export
- JSON format with metadata
- Automatic compression for large archives
- Includes attachments, embeds, and user data

**Requirements**:
- Bot owner access only (due to resource usage)
- Bot needs "Read Message History" permission

**Storage**:
- Archives saved to `temp/` directory
- Format: `{channel_id}_{channel_name}.json` or `.json.gz`
- Includes version, retrieval info, channel metadata, users, and messages

### GamesBot Plugin

Game tagging system for finding players.

**Features**:
- Game tag management
- Player discovery
- Tag-based pinging

**Requirements**: No special setup needed.

**Storage**:
- Game tags stored in `storage/gamesbot_games/`
- Format: `{guild_id}_{member_id}_{game}`

**Usage**:
- Add yourself: `!gamesbot add <game>`
- Remove yourself: `!gamesbot remove <game>`
- List games: `!gamesbot list`
- Ping players: `!gamesbot ping <game>`

### MatchVoting Plugin

Tournament match voting system.

**Features**:
- Match creation with deadlines
- Competitor management
- Voting system
- Result tallying

**Requirements**:
- Bot needs "Manage Roles" permission for admin commands
- Bot needs "Send Messages" permission

**Storage**:
- Matches stored in `storage/match_matches/`
- Competitors stored in `storage/match_competitors/`
- Votes stored in `storage/match_votes/`

**Workflow**:
1. Admin creates match: `!match create <title> [period]`
2. Admin adds competitors: `!match addcompetitor <match_id> <user> [data]`
3. Admin announces: `!match announce <channel> <match_id>`
4. Users vote: `!match vote <match_id> <entry_id>`
5. View results: `!tally <match_id>`

**Note**: Voting messages are automatically deleted after voting.

### Observer Plugin

Moderation logging and user reporting system.

**Features**:
- Message deletion logging
- Member join/leave logging
- Invite creation logging
- User report handling via reactions

**Requirements**:
- Bot needs "View Channel" and "Read Message History" permissions
- Bot needs "Send Messages" in logging channel

**Setup**:
1. Set logging channel: `!observer <channel_id>`
2. (Optional) Set report emote: `!observer <emote_id>`

**Storage**:
- Configuration stored in `storage/observer/`
- Format: `{guild_id}` with `channel_id` and `report_emote`

**Events Logged**:
- Message deletions (with content and author)
- Member joins (with account creation date)
- Member leaves (with roles)
- Invite creation (with creator and expiration)

**Reporting**:
- When report emote is configured, users can react to messages
- Reports are sent to the logging channel with message content and attachments

### Localization Plugin

Internationalization and timezone management.

**Features**:
- User timezone storage
- Time conversion utilities
- Timezone-aware time parsing

**Requirements**: No special setup needed.

**Storage**:
- User timezones stored in `storage/locale/`
- Format: `{user_id}` with `timezone` field

**Usage**:
- Set timezone: `!timezone <timezone_name>`
- View timezone: `!timezone`
- Convert time: `!time <time_string>`

**Timezone Format**:
- Use PHP timezone names (e.g., `America/New_York`, `Europe/London`)
- Prefer Continent/City format for automatic DST handling
- See [PHP timezone list](https://www.php.net/manual/en/timezones.php)

**Integration**:
- Used by Event plugin for event scheduling
- Used by Remind plugin for reminder scheduling
- Used by `!time` command for time conversion

### PermissionFrontend Plugin

Permission management interface.

**Features**:
- Permission checking
- Permission rule creation
- Scope management (global/guild/channel)
- Target management (all/role/user/admins/botowners)

**Requirements**:
- Bot owner access for global scope and bot admin permissions
- Guild owner/admin for guild scope
- Manage Channels permission for channel scope

**Storage**:
- Permissions stored in `storage/permissions/`
- Format: `{permission}_{setting}_{setting_value}_{target_type}_{target_value}`

**Usage**:
- Check permission: `!permission check <permission> [user]`
- Add permission: `!permission add <permission> [options]`

**Permission Format**:
- Format: `p.<plugin>.<feature>`
- Examples: `p.auditlog.view`, `p.roles.toggle`, `p.moderation.state`

**Scopes**:
- `global`: Applies everywhere
- `guild`: Applies to specific guild
- `channel`: Applies to specific channel

**Targets**:
- `all`: All users
- `role`: Users with specific role
- `user`: Specific user
- `admins`: Guild administrators
- `evalusers`: Bot owners

### Ironreach Plugin

Server-specific features for Ironreach server.

**Features**:
- Jury system management
- Talking stick requests
- Voice channel name rotation

**Requirements**:
- Only active on Ironreach server (ID: 673383165943087115)
- Requires `data/ironreach.txt` file for voice channel names

**Commands**:
- `!jury <user>` - Add user to jury
- `!talkingstick` - Request talking stick from staff
- `!vc` - Manually trigger voice channel name rotation

**Note**: This plugin is server-specific and may not be useful for other servers.

---

## Troubleshooting

### Bot Not Responding to Commands

1. **Check Bot Status**: Verify the bot is online (green dot in member list)
2. **Check Prefix**: Ensure you're using the correct prefix (default: `!`)
3. **Check Permissions**: Verify the bot has "Send Messages" permission in the channel
4. **Check Logs**: Review bot logs for error messages

### Permission Denied Errors

1. **Check User ID**: Verify your user ID is in `ADMIN_USER_IDS` for admin commands
2. **Check Plugin Permissions**: Some plugins require specific permissions (e.g., `p.auditlog.view`)
3. **Check Bot Permissions**: Ensure the bot has necessary permissions in the server

### ServerActivity Not Working

1. **Check RRDtool**: Verify RRDtool is installed and accessible
   - Test: Run `rrdtool` (or `wsl rrdtool` on Windows) in terminal
2. **Check Directory**: Ensure `temp/serveractivity/` exists and is writable
3. **Check Logs**: Look for RRDtool-related errors in bot logs
4. **Wait for Data**: Statistics need time to accumulate (at least a few minutes)

### AuditLog Not Fetching Events

1. **Check Permission**: Verify bot has "View Audit Log" permission
2. **Check Logs**: Review logs for permission errors or rate limit warnings
3. **Check Rate Limits**: If rate limited, the bot will automatically wait and retry
4. **Check Storage**: Verify `storage/audit_log/` directory exists and is writable
5. **Note**: Audit logs are fetched every 10 seconds, so events should appear quickly

### Commands Not Found

1. **Check Plugin Loading**: Verify plugins are loaded (check `!artemis` output)
2. **Check Command Name**: Ensure you're using the correct command name (case-insensitive)
3. **Check Bot Logs**: Look for plugin loading errors

### Bot Crashes or Restarts Unexpectedly

1. **Check Logs**: Review error logs for exceptions
2. **Check Memory**: Use `!artemis` to check memory usage
3. **Check Dependencies**: Ensure all Python packages are installed (`pip install -r requirements.txt`)
4. **Check Configuration**: Verify `config/config.py` is properly configured

### General Debugging Tips

1. **Enable Debug Logging**: Set `LOG_LEVEL = "DEBUG"` in `config/config.py`
2. **Check Console Output**: Bot logs important information to console
3. **Test in DM**: Try commands in a DM with the bot to isolate server-specific issues
4. **Review Documentation**: Check plugin-specific documentation for requirements

---

## Advanced Configuration

### Changing Command Prefix

Edit `config/config.py`:
```python
COMMAND_PREFIX = "?"  # Change from ! to ?
```

### Disabling Plugins

To disable a plugin, you can either:
1. Remove the plugin directory from `plugins/`
2. Add a check in the plugin's `register()` method
3. Use `TESTING_MODE = True` in config (disables some plugins)

### Custom Permission System

To implement custom permissions:
1. Modify `artemis/permissions/resolver.py`
2. Add permission storage in JSON format
3. Implement permission checking logic

---

## Support

For issues, questions, or contributions:
1. Check the logs for error messages
2. Review this guide for common solutions
3. Check the main README.md for setup instructions
4. Review the code comments for implementation details

---

## Quick Reference

### Command List
- `!ping` - Check latency
- `!artemis` - Bot info
- `!restart` - Restart bot (admin)
- `!update` - Git pull (admin)
- `!invite` - Generate invite
- `!messagestats [all]` - Message statistics
- `!auditlog` - Export audit logs
- `!user [user]` - User information
- `!roster <role>` - List role members
- `!av [user]` - Get avatar URL
- `!role [role]` - Toggle role or list roles
- `!bindrole <role_id>` - Make role self-assignable (admin)
- `!inheritrole <source> <dest>` - Set role inheritance (admin)
- `!event <when> <title>` - Create event
- `!event remove <id>` - Remove event
- `!calendar` - View events
- `!setCalendar <channel>` - Set auto-updating calendar (admin)
- `!remind <when> [message]` - Set reminder
- `!remind delete <id>` - Delete reminder
- `!agenda <message>` - Tally votes
- `!state [channel] <message>` - Post mod statement
- `!archive <channel>` - Archive channel (admin)
- `!gamesbot add/remove/list/ping <game>` - Game tagging
- `!match create/addcompetitor/vote/announce` - Match voting
- `!tally <match_id>` - View match results
- `!observer <channel_id>` - Configure logging (admin)
- `!timezone [timezone]` - Set timezone
- `!time <time>` - Convert time
- `!permission check/add` - Manage permissions

### Permission Strings
- `p.auditlog.view` - View audit logs
- `p.serveractivity.view` - View server stats
- `p.serveractivity.track` - Track server activity
- `p.management.restart` - Restart bot
- `p.management.update` - Update bot
- `p.userutils.roster` - View role roster
- `p.roles.toggle` - Toggle roles
- `p.roles.list` - List roles
- `p.roles.bind` - Bind/inherit roles
- `p.events.add` - Add events
- `p.events.setcalendar` - Set calendar
- `p.moderation.state` - Post mod statements
- `p.ironreach.changevc` - Change voice channels
- `p.reminder.delete` - Delete others' reminders

### Important Directories
- `storage/` - JSON storage files
  - `storage/audit_log/` - Audit log entries
  - `storage/event/` - Event calendar entries
  - `storage/remind/` - Reminder entries
  - `storage/roles/` - Role bindings
  - `storage/roles_inherit/` - Role inheritance rules
  - `storage/gamesbot_games/` - Game tags
  - `storage/match_*/` - Match voting data
  - `storage/observer/` - Observer configuration
  - `storage/locale/` - User timezones
  - `storage/permissions/` - Permission rules
- `temp/` - Temporary files
  - `temp/serveractivity/` - RRD files for statistics
  - `temp/` - Archive files
- `config/` - Configuration files
- `plugins/` - Plugin modules
- `data/` - Static data files (e.g., `data/ironreach.txt`)
