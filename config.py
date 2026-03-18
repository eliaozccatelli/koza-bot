# ⚙️ Configurazione KOZA Bot

"""
File di configurazione centralizzato.
Modifica i valori nel file .env, non qui!
"""

import os
from dotenv import load_dotenv

# Carica le variabili d'ambiente dal file .env
load_dotenv()

# ════════════════════════════════════════════════════════════════
# 🔐 API KEYS (Essenziale per il funzionamento)
# ════════════════════════════════════════════════════════════════

# API-Football (ottieni da api-sports.io)
# Piano gratuito: 100 richieste/giorno
API_KEY = os.getenv("API_KEY", "")

# Telegram Bot Token (ottieni da BotFather)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")

# API-Football Host (football-data.org - free, supporta 2025/26)
API_HOST = "api.football-data.org"


# ════════════════════════════════════════════════════════════════
# ⚽ Configurazione Calcio
# ════════════════════════════════════════════════════════════════

# ID della Lega (football-data.org)
# Valori comuni:
#   398 = Premier League (England)
#   78 = Bundesliga (Germany)
#   61 = Ligue 1 (France)
#   775 = Serie A (Italy) ← DEFAULT
#   206 = La Liga (Spain)
# Per trovare altri: https://www.football-data.org/competitions
LEAGUE_ID = 775

# Stagione corrente (2025 = stagione 2025/26)
SEASON = 2025

# Numero massimo di scontri diretti da considerare
HEAD_TO_HEAD_MATCHES = 5


# ════════════════════════════════════════════════════════════════
# 🔍 Configurazione Fuzzy Matching
# ════════════════════════════════════════════════════════════════

# Soglia minima di match per accettare una squadra (0-100)
# 75 = accetta solo match molto simili
# 70 = più permissivo
# 80+ = molto rigoroso
FUZZY_MATCH_THRESHOLD = 75


# ════════════════════════════════════════════════════════════════
# ⏱️ Configurazione API
# ════════════════════════════════════════════════════════════════

# Timeout per le richieste HTTP (secondi)
API_TIMEOUT = 30

# Numero massimo di gol da considerare nei calcoli Poisson
MAX_GOALS = 10


# ════════════════════════════════════════════════════════════════
# 📊 Output Display
# ════════════════════════════════════════════════════════════════

# Numero di pronostici principali da mostrare
MOSTRA_TOP_SCOMMESSE = 5

# Mostrare gli scontri diretti
MOSTRA_HEAD_TO_HEAD = True


# ════════════════════════════════════════════════════════════════
# 📝 Logging
# ════════════════════════════════════════════════════════════════

import logging

LOG_LEVEL = logging.INFO
# Cambia in logging.DEBUG per più dettagli
# Cambia in logging.WARNING per meno dettagli
