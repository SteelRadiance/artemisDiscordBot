"""
Copyright 2025, Vijay Challa - Use of this source code follows the MIT license found in the LICENSE file.

Helper utility functions
"""

import re
import hashlib
from typing import List, Optional


def split_command(content: str, prefix: str = "!") -> List[str]:
    """
    Split a command message into parts.
    
    Args:
        content: Message content
        prefix: Command prefix
        
    Returns:
        List of command parts
    """
    if not content.startswith(prefix):
        return []
    
    # Remove prefix and split
    content = content[len(prefix):].strip()
    return content.split()


def arg_substr(content: str, index: int, length: Optional[int] = None) -> Optional[str]:
    """
    Extract substring argument from command.
    
    Args:
        content: Full message content
        index: Starting index
        length: Optional length (if None, returns rest of string)
        
    Returns:
        Substring or None
    """
    parts = split_command(content)
    if index >= len(parts):
        return None
    
    if length is None:
        return " ".join(parts[index:])
    
    if index + length > len(parts):
        return None
    
    return " ".join(parts[index:index + length])


def format_bytes(bytes: int) -> str:
    """
    Format bytes into human-readable string.
    
    Args:
        bytes: Number of bytes
        
    Returns:
        Formatted string (e.g., "1.5 MiB")
    """
    units = ["bytes", "KiB", "MiB", "GiB", "TiB", "PiB", "EiB", "ZiB", "YiB"]
    
    for i, unit in enumerate(units):
        value = bytes / (1024 ** i)
        if value < 1024 or i == len(units) - 1:
            return f"{value:.2f} {unit}"
    
    return f"{bytes} bytes"


def emoji_hash(text: str, length: int = 8) -> str:
    """
    Generate an emoji-based hash from a string.
    
    Args:
        text: Input string to hash
        length: Number of emojis to generate (default: 8)
        
    Returns:
        String of emojis representing the hash
    """
    # Create a list of emojis that are commonly available and visually distinct
    # Using emojis from various categories for variety
    emoji_list = [
        "🔴", "🟠", "🟡", "🟢", "🔵", "🟣", "🟤", "⚫", "⚪", "🟥",
        "🟧", "🟨", "🟩", "🟦", "🟪", "🟫", "⬛", "⬜", "🔶", "🔷",
        "🔸", "🔹", "🔺", "🔻", "💠", "🔘", "🔳", "🔲", "🟰", "➕",
        "➖", "✖️", "➗", "♾️", "💯", "🔢", "0️⃣", "1️⃣", "2️⃣", "3️⃣",
        "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "⭐", "🌟", "✨", "💫",
        "🔥", "💧", "🌊", "☀️", "🌙", "⭐", "🌟", "💎", "🎯", "🎲"
    ]
    
    # Hash the input string
    hash_obj = hashlib.sha256(text.encode('utf-8'))
    hash_bytes = hash_obj.digest()
    
    # Map hash bytes to emojis
    emoji_string = ""
    for i in range(length):
        byte_index = hash_bytes[i % len(hash_bytes)]
        emoji_index = byte_index % len(emoji_list)
        emoji_string += emoji_list[emoji_index]
    
    return emoji_string
