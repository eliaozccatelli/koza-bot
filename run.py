#!/usr/bin/env python3
"""Entry point per avviare il bot KOZA Telegram."""

import sys
import os

# Assicura che la root del progetto sia nel path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.bot.telegram import main

if __name__ == "__main__":
    main()
