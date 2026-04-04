#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Entry point principale per KOZA Bot 3.0
Avvia il bot Telegram con la nuova struttura organizzata
"""

import sys
import os

# Aggiungi la root del progetto al path per permettere gli import assoluti 'from src...'
sys.path.insert(0, os.path.dirname(__file__))

# Importa e avvia il bot
try:
    from src.bot.telegram import main
    
    if __name__ == "__main__":
        main()
except ImportError as e:
    import traceback
    print(f"❌ Errore import: {e}")
    traceback.print_exc()
    print("⚠️ Assicurati di avere tutte le dipendenze installate:")
    print("   pip install -r requirements.txt")
    sys.exit(1)
except Exception as e:
    print(f"❌ Errore avvio bot: {e}")
    sys.exit(1)
