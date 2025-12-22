# Artemis

A Discord bot framework written in Python using disnake, ported from the Huntress PHP bot.

## Features

- Plugin-based architecture
- Event-driven system
- JSON file storage
- Permission system
- Command handling (prefix and slash commands)

## Quick Start

### Installation

1. Install Python 3.12+
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `config/config.example.py` to `config/config.py` and configure:
   - Set `BOT_TOKEN` to your Discord bot token
   - Add admin user IDs to `ADMIN_USER_IDS`
4. Run: `python main.py`

### Adding to Discord

See [USAGE_GUIDE.md](USAGE_GUIDE.md) for detailed instructions on:
- Adding the bot to your server
- Setting up permissions
- Using commands
- Configuring plugins

## Project Structure

- `artemis/` - Core framework
- `plugins/` - Plugin modules
  - `management/` - Bot management commands
  - `server_activity/` - Message statistics tracking
  - `audit_log/` - Audit log monitoring
- `data/` - Static data files
- `storage/` - JSON storage files
- `config/` - Configuration files

## Available Plugins

### Management
Core bot management commands (`!ping`, `!artemis`, `!restart`, `!update`, `!invite`)

### ServerActivity
Tracks message statistics and generates activity graphs (`!messagestats`)

### AuditLog
Monitors and stores Discord audit log events (`!auditlog`)

## Documentation

- [Usage Guide](USAGE_GUIDE.md) - Complete guide for server admins
- [Configuration](config/config.example.py) - Configuration examples

## License

MIT
