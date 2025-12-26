"""
Copyright 2025, Vijay Challa - Use of this source code follows the MIT license found in the LICENSE file.

JSON-based storage system for Artemis bot.

This module provides a simple key-value storage system using JSON files.
Data is organized by namespace, with each namespace stored in its own JSON file.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional
import aiofiles
import aiofiles.os

logger = logging.getLogger("artemis.storage")


class JSONStore:
    """
    JSON-based key-value storage system.
    
    Data is organized by namespace, with each namespace stored in a separate JSON file.
    Files are stored in the storage directory, one file per namespace.
    """
    
    def __init__(self, storage_dir: str = "storage"):
        """
        Initialize the JSON storage system.
        
        Args:
            storage_dir: Directory path where JSON files will be stored
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized JSONStore with storage directory: {self.storage_dir}")
    
    def _get_namespace_path(self, namespace: str) -> Path:
        """
        Get the file path for a namespace.
        
        Args:
            namespace: The namespace identifier
            
        Returns:
            Path to the JSON file for this namespace
        """
        # Sanitize namespace to prevent directory traversal
        safe_namespace = namespace.replace('/', '_').replace('\\', '_')
        return self.storage_dir / f"{safe_namespace}.json"
    
    async def get(self, namespace: str, key: str) -> Optional[Any]:
        """
        Get a value from storage.
        
        Args:
            namespace: The namespace to read from
            key: The key to retrieve
            
        Returns:
            The stored value, or None if not found
        """
        try:
            file_path = self._get_namespace_path(namespace)
            
            if not await aiofiles.os.path.exists(file_path):
                return None
            
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                if not content.strip():
                    return None
                
                data = json.loads(content)
                if not isinstance(data, dict):
                    logger.warning(f"Storage file {file_path} contains invalid data (not a dict)")
                    return None
                
                return data.get(key)
        
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from {file_path}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error reading from storage namespace '{namespace}': {e}")
            return None
    
    async def set(self, namespace: str, key: str, value: Any) -> bool:
        """
        Store a value in storage.
        
        Args:
            namespace: The namespace to write to
            key: The key to store
            value: The value to store (must be JSON-serializable)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            file_path = self._get_namespace_path(namespace)
            
            # Read existing data
            data = {}
            if await aiofiles.os.path.exists(file_path):
                try:
                    async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                        content = await f.read()
                        if content.strip():
                            data = json.loads(content)
                            if not isinstance(data, dict):
                                logger.warning(f"Storage file {file_path} contains invalid data, resetting")
                                data = {}
                except json.JSONDecodeError:
                    logger.warning(f"Storage file {file_path} is corrupted, resetting")
                    data = {}
            
            # Update data
            data[key] = value
            
            # Write back to file
            async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(data, indent=2, ensure_ascii=False))
            
            return True
        
        except Exception as e:
            logger.error(f"Error writing to storage namespace '{namespace}': {e}")
            return False
    
    async def get_all(self, namespace: str) -> Dict[str, Any]:
        """
        Get all key-value pairs from a namespace.
        
        Args:
            namespace: The namespace to read from
            
        Returns:
            Dictionary of all key-value pairs in the namespace, or empty dict if not found
        """
        try:
            file_path = self._get_namespace_path(namespace)
            
            if not await aiofiles.os.path.exists(file_path):
                return {}
            
            async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                content = await f.read()
                if not content.strip():
                    return {}
                
                data = json.loads(content)
                if not isinstance(data, dict):
                    logger.warning(f"Storage file {file_path} contains invalid data (not a dict)")
                    return {}
                
                return data
        
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON from {file_path}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error reading from storage namespace '{namespace}': {e}")
            return {}
    
    async def delete(self, namespace: str, key: str) -> bool:
        """
        Delete a key from storage.
        
        Args:
            namespace: The namespace to delete from
            key: The key to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            file_path = self._get_namespace_path(namespace)
            
            if not await aiofiles.os.path.exists(file_path):
                return False
            
            # Read existing data
            data = {}
            try:
                async with aiofiles.open(file_path, 'r', encoding='utf-8') as f:
                    content = await f.read()
                    if content.strip():
                        data = json.loads(content)
                        if not isinstance(data, dict):
                            logger.warning(f"Storage file {file_path} contains invalid data, resetting")
                            data = {}
            except json.JSONDecodeError:
                logger.warning(f"Storage file {file_path} is corrupted, resetting")
                data = {}
            
            # Delete key if it exists
            if key in data:
                del data[key]
                
                # Write back to file
                async with aiofiles.open(file_path, 'w', encoding='utf-8') as f:
                    await f.write(json.dumps(data, indent=2, ensure_ascii=False))
                
                return True
            
            return False
        
        except Exception as e:
            logger.error(f"Error deleting from storage namespace '{namespace}': {e}")
            return False

