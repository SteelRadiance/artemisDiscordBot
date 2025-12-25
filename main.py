#!/usr/bin/env python3.11
"""
Copyright 2025, Vijay Challa - Use of this source code follows the MIT license found in the LICENSE file.

Artemis Bot - Main Entry Point
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from artemis.bot import ArtemisBot
from artemis.utils.logging import setup_logging
import logging

if __name__ == "__main__":
    # Setup logging first
    # Check for log file path in config, default to logs/artemis.log
    log_level = "INFO"
    log_file = "logs/artemis.log"
    
    try:
        from config import config
        log_level = getattr(config, 'LOG_LEVEL', log_level)
        log_file = getattr(config, 'LOG_FILE', log_file)
    except ImportError:
        pass  # Config not loaded yet, use defaults
    
    # Create logs directory if it doesn't exist
    if log_file:
        os.makedirs(os.path.dirname(log_file) if os.path.dirname(log_file) else '.', exist_ok=True)
    
    setup_logging(level=log_level, log_file=log_file)
    logger = logging.getLogger("artemis")
    
    try:
        # Load configuration
        try:
            from config import config
        except ImportError:
            logger.error("Configuration not found! Please copy config/config.example.py to config/config.py and configure it.")
            sys.exit(1)
        
        # Create and start bot
        bot = ArtemisBot(config)
        bot.run()
    except KeyboardInterrupt:
        logger.info("Bot shutdown requested")
    except Exception as e:
        logger.exception("Fatal error starting bot")
        sys.exit(1)
