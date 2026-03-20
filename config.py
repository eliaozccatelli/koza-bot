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
# DEPRECATED: Ora usiamo Gemini AI
API_KEY = os.getenv("API_KEY", "")

# Google Gemini API Key (ottieni da Google AI Studio)
# URL: https://aistudio.google.com/app/apikey
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# TheSportsDB API Key (gratuito da thesportsdb.com)
# Default: 123 per piano FREE, puoi registrarti per API key personale
THESPORTSDB_API_KEY = os.getenv("THESPORTSDB_API_KEY", "123")

# Telegram Bot Token (ottieni da BotFather)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")

# API Host
# football-data.org (v4) - Rate limit: 10 chiamate/minuto (piano gratuito)
API_HOST = os.getenv("API_HOST", "api.football-data.org")


# ════════════════════════════════════════════════════════════════
# ⚽ Configurazione Calcio
# ════════════════════════════════════════════════════════════════

# ID della Lega (football-data.org v4)
# Leghe principali piano gratuito:
#   2021 = Premier League (England)
#   2002 = Bundesliga (Germany)
#   2015 = Ligue 1 (France)
#   2019 = Serie A (Italy)
#   2014 = La Liga (Spain)
#   2001 = Champions League
#   2000 = Europa League
LEAGUE_ID = 2019  # Serie A default

# Stagione corrente (2024 = stagione 2024/25)
SEASON = 2024

# Numero massimo di scontri diretti da considerare
HEAD_TO_HEAD_MATCHES = 5


# ════════════════════════════════════════════════════════════════
# 🔍 Configurazione Fuzzy Matching
# ════════════════════════════════════════════════════════════════

# Soglia minima di match per accettare una squadra (0-100)
# 75 = accetta solo match molto simili
# 70 = più permissivo  
# 80+ = molto rigoroso (RACCOMANDATO per evitare Roma => Romania)
FUZZY_MATCH_THRESHOLD = 82


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
