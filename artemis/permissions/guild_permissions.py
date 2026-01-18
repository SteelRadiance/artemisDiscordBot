"""
Copyright 2025, Vijay Challa - Use of this source code follows the MIT license found in the LICENSE file.

Guild-based permission helper functions.
"""

import logging
import random
from typing import Optional, Dict, Any

logger = logging.getLogger("artemis.permissions.guild_permissions")


def is_super_admin(user_id: str, config) -> bool:
    """
    Check if user is the super admin.
    
    Args:
        user_id: Discord user ID as string
        config: Bot config object with SUPER_ADMIN_ID attribute
        
    Returns:
        True if user is super admin, False otherwise
    """
    super_admin_id = getattr(config, 'SUPER_ADMIN_ID', None)
    if not super_admin_id:
        return False
    return str(user_id) == str(super_admin_id)


async def get_guild_permissions(guild_id: str, bot) -> Optional[Dict[str, Any]]:
    """
    Get guild permission structure from storage.
    
    Args:
        guild_id: Discord guild ID as string
        bot: Bot instance with storage
        
    Returns:
        Dictionary with admin_id and mods, or None if not found
    """
    try:
        if not hasattr(bot, 'storage'):
            return None
        
        data = await bot.storage.get("guild_permissions", str(guild_id))
        if data and isinstance(data, dict):
            return data
        return None
    except Exception as e:
        logger.error(f"Error getting guild permissions for guild {guild_id}: {e}")
        return None


async def is_guild_admin(user_id: str, guild_id: str, bot) -> bool:
    """
    Check if user is a guild admin.
    
    Args:
        user_id: Discord user ID as string
        guild_id: Discord guild ID as string
        bot: Bot instance
        
    Returns:
        True if user is guild admin, False otherwise
    """
    permissions = await get_guild_permissions(guild_id, bot)
    if not permissions:
        return False
    
    admin_id = permissions.get("admin_id")
    return admin_id and str(user_id) == str(admin_id)


async def is_guild_moderator(user_id: str, guild_id: str, bot) -> bool:
    """
    Check if user is a guild moderator.
    
    Args:
        user_id: Discord user ID as string
        guild_id: Discord guild ID as string
        bot: Bot instance
        
    Returns:
        True if user is guild moderator, False otherwise
    """
    permissions = await get_guild_permissions(guild_id, bot)
    if not permissions:
        return False
    
    mods = permissions.get("mods", {})
    if not isinstance(mods, dict):
        return False
    
    # Check if user_id is in the mods dictionary (either as key or value)
    # The structure is {mod_user_id: user_id} or {mod_name: user_id}
    for mod_key, mod_value in mods.items():
        if str(user_id) == str(mod_key) or str(user_id) == str(mod_value):
            return True
    
    return False


async def has_admin_access(user_id: str, guild_id: str, bot) -> bool:
    """
    Check if user has admin-level access.
    
    Admin access is granted to:
    - Super admin
    - Guild admin
    - Guild moderator
    
    Args:
        user_id: Discord user ID as string
        guild_id: Discord guild ID as string (can be None for super admin check)
        bot: Bot instance with config and storage
        
    Returns:
        True if user has admin access, False otherwise
    """
    # Check super admin first
    if hasattr(bot, 'config') and is_super_admin(user_id, bot.config):
        return True
    
    # If no guild_id provided, only super admin check applies
    if not guild_id:
        return False
    
    # Check guild admin
    if await is_guild_admin(user_id, guild_id, bot):
        return True
    
    # Check guild moderator
    if await is_guild_moderator(user_id, guild_id, bot):
        return True
    
    return False


async def set_guild_admin(guild_id: str, admin_id: str, bot) -> bool:
    """
    Set guild admin.
    
    Args:
        guild_id: Discord guild ID as string
        admin_id: Discord user ID to set as admin
        bot: Bot instance with storage
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if not hasattr(bot, 'storage'):
            return False
        
        permissions = await get_guild_permissions(guild_id, bot) or {}
        permissions["admin_id"] = str(admin_id)
        
        # Ensure mods dict exists
        if "mods" not in permissions:
            permissions["mods"] = {}
        
        success = await bot.storage.set("guild_permissions", str(guild_id), permissions)
        return success
    except Exception as e:
        logger.error(f"Error setting guild admin for guild {guild_id}: {e}")
        return False


async def add_guild_moderator(guild_id: str, mod_id: str, bot) -> bool:
    """
    Add moderator to guild.
    
    Args:
        guild_id: Discord guild ID as string
        mod_id: Discord user ID to add as moderator
        bot: Bot instance with storage
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if not hasattr(bot, 'storage'):
            return False
        
        permissions = await get_guild_permissions(guild_id, bot) or {}
        
        # Ensure structure exists
        if "mods" not in permissions:
            permissions["mods"] = {}
        
        # Use mod_id as both key and value for consistency
        permissions["mods"][str(mod_id)] = str(mod_id)
        
        success = await bot.storage.set("guild_permissions", str(guild_id), permissions)
        return success
    except Exception as e:
        logger.error(f"Error adding guild moderator for guild {guild_id}: {e}")
        return False


async def remove_guild_moderator(guild_id: str, mod_id: str, bot) -> bool:
    """
    Remove moderator from guild.
    
    Args:
        guild_id: Discord guild ID as string
        mod_id: Discord user ID to remove as moderator
        bot: Bot instance with storage
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if not hasattr(bot, 'storage'):
            return False
        
        permissions = await get_guild_permissions(guild_id, bot)
        if not permissions:
            return False
        
        mods = permissions.get("mods", {})
        if not isinstance(mods, dict):
            return False
        
        # Remove moderator - check both key and value
        removed = False
        mod_id_str = str(mod_id)
        
        # Remove by key
        if mod_id_str in mods:
            del mods[mod_id_str]
            removed = True
        else:
            # Remove by value
            keys_to_remove = [key for key, value in mods.items() if str(value) == mod_id_str]
            for key in keys_to_remove:
                del mods[key]
                removed = True
        
        if removed:
            permissions["mods"] = mods
            success = await bot.storage.set("guild_permissions", str(guild_id), permissions)
            return success
        
        return False
    except Exception as e:
        logger.error(f"Error removing guild moderator for guild {guild_id}: {e}")
        return False


async def transfer_guild_admin(guild_id: str, new_admin_id: str, old_admin_id: str, bot) -> bool:
    """
    Transfer admin from old admin to new admin.
    Old admin becomes a moderator.
    
    Args:
        guild_id: Discord guild ID as string
        new_admin_id: Discord user ID to become new admin
        old_admin_id: Discord user ID of current admin
        bot: Bot instance with storage
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if not hasattr(bot, 'storage'):
            return False
        
        permissions = await get_guild_permissions(guild_id, bot)
        if not permissions:
            return False
        
        # Verify old_admin_id is the current admin
        current_admin = permissions.get("admin_id")
        if str(old_admin_id) != str(current_admin):
            logger.warning(f"Transfer attempt: {old_admin_id} is not the current admin {current_admin}")
            return False
        
        # Set new admin
        permissions["admin_id"] = str(new_admin_id)
        
        # Add old admin as moderator
        if "mods" not in permissions:
            permissions["mods"] = {}
        permissions["mods"][str(old_admin_id)] = str(old_admin_id)
        
        # Remove new_admin_id from mods if they were a moderator
        mod_id_str = str(new_admin_id)
        if mod_id_str in permissions["mods"]:
            del permissions["mods"][mod_id_str]
        else:
            # Also check by value
            keys_to_remove = [key for key, value in permissions["mods"].items() if str(value) == mod_id_str]
            for key in keys_to_remove:
                del permissions["mods"][key]
        
        success = await bot.storage.set("guild_permissions", str(guild_id), permissions)
        return success
    except Exception as e:
        logger.error(f"Error transferring guild admin for guild {guild_id}: {e}")
        return False


async def get_random_moderator(guild_id: str, bot) -> Optional[str]:
    """
    Get a random moderator ID from the guild.
    
    Args:
        guild_id: Discord guild ID as string
        bot: Bot instance with storage
        
    Returns:
        Moderator user ID as string, or None if no moderators
    """
    try:
        permissions = await get_guild_permissions(guild_id, bot)
        if not permissions:
            return None
        
        mods = permissions.get("mods", {})
        if not isinstance(mods, dict) or not mods:
            return None
        
        # Get all moderator IDs (from keys)
        moderator_ids = [str(mod_id) for mod_id in mods.keys()]
        
        if not moderator_ids:
            return None
        
        # Return random moderator
        return random.choice(moderator_ids)
    except Exception as e:
        logger.error(f"Error getting random moderator for guild {guild_id}: {e}")
        return None
