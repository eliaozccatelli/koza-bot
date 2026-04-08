"""
Database statico con forza realistica delle squadre principali.
I valori sono basati sulla qualità generale della squadra (0-100).
Aggiornati alla stagione 2025/2026.
"""

# Serie A 2025/2026 - Forza squadre (0-100)
# Basati sulla classifica REALE (aggiornamento aprile 2026)
# Formula: rating proporzionale ai punti reali in classifica
SERIE_A_RATINGS = {
    "Inter": 90,         # 1° - 72 pts
    "Milan": 86,         # 2° - 63 pts
    "Napoli": 85,        # 3° - 62 pts
    "Como": 83,          # 4° - 57 pts
    "Juventus": 81,      # 5° - 54 pts
    "Roma": 81,          # 6° - 54 pts
    "Atalanta": 78,      # 7° - 50 pts
    "Bologna": 75,       # 8° - 45 pts
    "Lazio": 74,         # 9° - 44 pts
    "Sassuolo": 72,      # 10° - 42 pts
    "Udinese": 70,       # 11° - 39 pts
    "Torino": 68,        # 12° - 36 pts
    "Parma": 67,         # 13° - 35 pts
    "Genoa": 66,         # 14° - 33 pts
    "Fiorentina": 65,    # 15° - 32 pts
    "Cagliari": 63,      # 16° - 30 pts
    "Cremonese": 61,     # 17° - 27 pts
    "Lecce": 61,         # 18° - 27 pts
    "Verona": 56,        # 19° - 18 pts
    "Pisa": 56,          # 20° - 18 pts
    "Monza": 58,
}

# Classifica e punti reali per contesto AI
SERIE_A_STANDINGS = {
    "Inter": {"pos": 1, "pts": 72, "played": 31},
    "Milan": {"pos": 2, "pts": 63, "played": 30},
    "Napoli": {"pos": 3, "pts": 62, "played": 30},
    "Como": {"pos": 4, "pts": 57, "played": 30},
    "Juventus": {"pos": 5, "pts": 54, "played": 30},
    "Roma": {"pos": 6, "pts": 54, "played": 31},
    "Atalanta": {"pos": 7, "pts": 50, "played": 30},
    "Bologna": {"pos": 8, "pts": 45, "played": 31},
    "Lazio": {"pos": 9, "pts": 44, "played": 31},
    "Sassuolo": {"pos": 10, "pts": 42, "played": 30},
    "Udinese": {"pos": 11, "pts": 39, "played": 30},
    "Torino": {"pos": 12, "pts": 36, "played": 31},
    "Parma": {"pos": 13, "pts": 35, "played": 31},
    "Genoa": {"pos": 14, "pts": 33, "played": 30},
    "Fiorentina": {"pos": 15, "pts": 32, "played": 31},
    "Cagliari": {"pos": 16, "pts": 30, "played": 31},
    "Cremonese": {"pos": 17, "pts": 27, "played": 31},
    "Lecce": {"pos": 18, "pts": 27, "played": 30},
    "Verona": {"pos": 19, "pts": 18, "played": 31},
    "Pisa": {"pos": 20, "pts": 18, "played": 31},
}

# Serie B - Squadre principali (0-100)
SERIE_B_RATINGS = {
    "Palermo": 70,
    "Sampdoria": 70,
    "Brescia": 68,
    "Spezia": 67,
    "Bari": 67,
    "Catanzaro": 66,
    "Cremonese B": 66,
    "Modena": 65,
    "Reggiana": 65,
    "Frosinone": 65,
    "Salernitana": 65,
    "Cesena": 64,
    "Cittadella": 63,
    "Sudtirol": 62,
    "Juve Stabia": 62,
    "Cosenza": 61,
    "Carrarese": 60,
    "Mantova": 60,
}

# Premier League - Forza squadre (0-100)
PREMIER_RATINGS = {
    "Manchester City": 91,
    "Liverpool": 89,
    "Arsenal": 87,
    "Chelsea": 84,
    "Manchester United": 83,
    "Tottenham": 82,
    "Newcastle": 81,
    "Aston Villa": 80,
    "Brighton": 79,
    "West Ham": 78,
    "Brentford": 76,
    "Crystal Palace": 75,
    "Wolves": 74,
    "Fulham": 73,
    "Everton": 72,
    "Nottingham Forest": 71,
    "Bournemouth": 70,
    "Burnley": 68,
    "Sheffield United": 67,
    "Luton": 66,
}

# La Liga - Forza squadre (0-100)
LA_LIGA_RATINGS = {
    "Real Madrid": 90,
    "Barcelona": 88,
    "Atletico Madrid": 86,
    "Real Sociedad": 82,
    "Athletic Bilbao": 81,
    "Villarreal": 80,
    "Sevilla": 79,
    "Real Betis": 78,
    "Valencia": 77,
    "Celta Vigo": 75,
    "Getafe": 74,
    "Osasuna": 73,
    "Las Palmas": 72,
    "Rayo Vallecano": 71,
    "Mallorca": 70,
    "Alaves": 69,
    "Cadiz": 68,
    "Granada": 67,
    "Almeria": 66,
}

# Bundesliga - Forza squadre (0-100)
BUNDESLIGA_RATINGS = {
    "Bayern Monaco": 90,
    "Borussia Dortmund": 85,
    "RB Leipzig": 84,
    "Bayer Leverkusen": 83,
    "Eintracht Frankfurt": 80,
    "Wolfsburg": 78,
    "Freiburg": 77,
    "Stuttgart": 76,
    "Hoffenheim": 75,
    "Union Berlin": 74,
    "Augsburg": 73,
    "Gladbach": 72,
    "Mainz": 71,
    "Werder Bremen": 70,
    "Heidenheim": 68,
    "Bochum": 67,
    "Koln": 66,
    "Darmstadt": 65,
}

# Ligue 1 - Forza squadre (0-100)
LIGUE_1_RATINGS = {
    "Paris Saint-Germain": 88,
    "Monaco": 82,
    "Lille": 81,
    "Marseille": 80,
    "Rennes": 78,
    "Nice": 77,
    "Lyon": 76,
    "Lens": 75,
    "Reims": 73,
    "Strasbourg": 72,
    "Nantes": 71,
    "Montpellier": 70,
    "Le Havre": 69,
    "Metz": 68,
    "Toulouse": 67,
    "Brest": 66,
    "Clermont": 65,
    "Lorient": 64,
}

# Altre squadre europee (Champions/Europa League)
OTHER_EUROPEAN_RATINGS = {
    "Sporting": 80,
    "Benfica": 82,
    "Porto": 80,
    "Ajax": 78,
    "PSV": 79,
    "Feyenoord": 77,
    "Club Brugge": 75,
    "Celtic": 76,
    "Rangers": 74,
    "Galatasaray": 77,
    "Fenerbahce": 76,
    "Besiktas": 74,
    "Red Bull Salzburg": 75,
    "Sturm Graz": 72,
    "Shakhtar Donetsk": 74,
    "Dinamo Zagreb": 73,
    "Olympiacos": 74,
    "PAOK": 72,
    "Slavia Prague": 73,
    "Sparta Prague": 72,
}

# Alias nomi API -> nomi interni (API-Football/TheSportsDB usano nomi diversi)
TEAM_ALIASES = {
    # Bundesliga
    "Bayern München": "Bayern Monaco",
    "Bayern Munich": "Bayern Monaco",
    "FC Bayern München": "Bayern Monaco",
    "Borussia Mönchengladbach": "Gladbach",
    "Bor. Monchengladbach": "Gladbach",
    "1. FC Köln": "Koln",
    "FC Köln": "Koln",
    "1899 Hoffenheim": "Hoffenheim",
    "TSG Hoffenheim": "Hoffenheim",
    "SC Freiburg": "Freiburg",
    "VfB Stuttgart": "Stuttgart",
    "VfL Wolfsburg": "Wolfsburg",
    "FC Augsburg": "Augsburg",
    "SV Darmstadt 98": "Darmstadt",
    "1. FC Heidenheim": "Heidenheim",
    "VfL Bochum": "Bochum",
    "Werder": "Werder Bremen",
    # Serie A
    "AC Milan": "Milan",
    "FC Internazionale": "Inter",
    "Inter Milan": "Inter",
    "AS Roma": "Roma",
    "SS Lazio": "Lazio",
    "SSC Napoli": "Napoli",
    "ACF Fiorentina": "Fiorentina",
    "US Sassuolo": "Sassuolo",
    "US Lecce": "Lecce",
    "Hellas Verona": "Verona",
    # Premier League
    "Manchester United": "Man United",
    "Manchester City": "Man City",
    "Wolverhampton": "Wolves",
    "Wolverhampton Wanderers": "Wolves",
    "Nottingham Forest": "Nott. Forest",
    "Sheffield United": "Sheffield Utd",
    # La Liga
    "Atletico Madrid": "Atletico",
    "Atlético Madrid": "Atletico",
    "Athletic Club": "Athletic Bilbao",
    "Athletic Bilbao": "Athletic Bilbao",
    "Real Sociedad": "Real Sociedad",
    "Real Betis": "Real Betis",
    "Celta Vigo": "Celta",
    "Celta de Vigo": "Celta",
    # Ligue 1
    "Paris Saint Germain": "Paris Saint-Germain",
    "PSG": "Paris Saint-Germain",
    "AS Monaco": "Monaco",
    "Olympique Marseille": "Marseille",
    "Olympique de Marseille": "Marseille",
    "Olympique Lyonnais": "Lyon",
    "Olympique Lyon": "Lyon",
    "LOSC Lille": "Lille",
    "Stade Rennais": "Rennes",
    "OGC Nice": "Nice",
    "RC Lens": "Lens",
    "RC Strasbourg": "Strasbourg",
    "Stade de Reims": "Reims",
    # Champions League / Europa League
    "Sporting CP": "Sporting",
    "Sporting Lisbon": "Sporting",
    "FC Porto": "Porto",
    "SL Benfica": "Benfica",
    "Club Brugge KV": "Club Brugge",
    "FC Barcelona": "Barcelona",
    "Real Madrid CF": "Real Madrid",
}

# Unione di tutti i rating
TEAM_RATINGS = {}
TEAM_RATINGS.update(SERIE_B_RATINGS)
TEAM_RATINGS.update(SERIE_A_RATINGS)
TEAM_RATINGS.update(PREMIER_RATINGS)
TEAM_RATINGS.update(LA_LIGA_RATINGS)
TEAM_RATINGS.update(BUNDESLIGA_RATINGS)
TEAM_RATINGS.update(LIGUE_1_RATINGS)
TEAM_RATINGS.update(OTHER_EUROPEAN_RATINGS)


import json
import os
import logging

logger = logging.getLogger(__name__)

# Cache per gli alias caricati da JSON
_TEAM_ALIASES_CACHE = None
_TEAM_COMPETITIONS_CACHE = None

def _load_aliases():
    """Carica gli alias dal file JSON centralizzato."""
    global _TEAM_ALIASES_CACHE, _TEAM_COMPETITIONS_CACHE
    if _TEAM_ALIASES_CACHE is not None:
        return _TEAM_ALIASES_CACHE, _TEAM_COMPETITIONS_CACHE
    
    alias_file = os.path.join('data', 'team_aliases.json')
    if os.path.exists(alias_file):
        try:
            with open(alias_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                _TEAM_ALIASES_CACHE = data.get('aliases', {})
                _TEAM_COMPETITIONS_CACHE = data.get('competitions', {})
                return _TEAM_ALIASES_CACHE, _TEAM_COMPETITIONS_CACHE
        except Exception as e:
            logger.error(f"Errore nel caricamento di team_aliases.json: {e}")
    
    _TEAM_ALIASES_CACHE = {}
    _TEAM_COMPETITIONS_CACHE = {}
    return _TEAM_ALIASES_CACHE, _TEAM_COMPETITIONS_CACHE

def _resolve_alias(team_name):
    """Risolve alias nome squadra (API/Telegram) -> nome canonico KOZA."""
    if not team_name:
        return team_name
    
    aliases, _ = _load_aliases()
    
    # Pulizia base
    name_clean = team_name.strip().lower()
    
    # 1. Match diretto (case insensitive) nel JSON
    if name_clean in aliases:
        return aliases[name_clean]
    
    # 2. Match parziale nel JSON (es. "Inter" in "Inter Milan")
    for alias, canonical in aliases.items():
        if alias in name_clean or name_clean in alias:
            return canonical
            
    # 3. Fallback sul vecchio dizionario statico (se non trovato nel JSON)
    if team_name in TEAM_ALIASES:
        return TEAM_ALIASES[team_name]
    for alias, canonical in TEAM_ALIASES.items():
        if name_clean == alias.lower():
            return canonical
            
    return team_name

def get_competition(team_name):
    """Ritorna la competizione principale di una squadra."""
    resolved = _resolve_alias(team_name)
    _, comps = _load_aliases()
    return comps.get(resolved, "Unknown")


def get_team_rating(team_name, default=60):
    """
    Recupera il rating di una squadra.
    Cerca corrispondenza esatta o parziale.
    """
    # Risolvi alias (es: "Bayern München" -> "Bayern Monaco")
    resolved = _resolve_alias(team_name)

    # Cerca corrispondenza esatta
    if resolved in TEAM_RATINGS:
        return TEAM_RATINGS[resolved]

    # Cerca corrispondenza parziale (case insensitive)
    team_lower = resolved.lower()
    for name, rating in TEAM_RATINGS.items():
        if team_lower in name.lower() or name.lower() in team_lower:
            return rating

    # Fallback conservativo: squadre sconosciute = deboli (60-69)
    name_hash = sum(ord(c) for c in team_name)
    return default + (name_hash % 10)


def rating_from_standings_position(position, total_teams=20):
    """
    Converte una posizione in classifica in un rating 0-100.
    1° posto = 90, ultimo posto = 61.
    """
    if position < 1:
        position = 1
    if position > total_teams:
        position = total_teams
    return int(90 - (position - 1) * (29 / max(total_teams - 1, 1)))


def get_team_form(team_name, giornata_offset=0):
    """
    Ritorna la forma recente della squadra basata sul suo rating.
    Squadre più forti tendono ad avere forme migliori.
    La forma è deterministica per squadra ma varia leggermente nel tempo.
    """
    resolved = _resolve_alias(team_name)
    rating = get_team_rating(resolved)

    # Usa hash del nome CANONICO per consistenza tra alias
    import random
    name_hash = sum(ord(c) for c in resolved)
    random.seed(name_hash + giornata_offset * 7)  # Cambia ogni settimana
    
    # Probabilità forma in base al rating
    if rating >= 85:
        # Squadre top: 70% forma buona/ottima, 30% media
        forme = [
            "WWWWD",  # 4 vittorie, 1 pareggio
            "WWWWW",  # 5 vittorie
            "LWWWW",  # 1 sconfitta, poi 4 vittorie
            "WWWLW",  # 4 vittorie, 1 sconfitta
            "WDWWW",  # 3 vittorie, 1 pareggio, 1 vittoria
        ]
    elif rating >= 78:
        # Squadre forti: 50% buona, 40% media, 10% scarsa
        forme = [
            "WWWDL",
            "WWLWD",
            "LWWLW",
            "WWDDW",
            "WLWWL",
        ]
    elif rating >= 70:
        # Squadre medie: 30% buona, 50% media, 20% scarsa
        forme = [
            "WDLWD",
            "LWDWL",
            "DWLDW",
            "WLLDW",
            "DDWDL",
        ]
    else:
        # Squadre deboli: 20% media, 80% scarsa
        forme = [
            "LDLLW",
            "DLLLD",
            "LLDWL",
            "LDWLL",
            "DLLDL",
        ]
    
    forma = random.choice(forme)
    
    # Ritorna solo la sequenza W/D/L senza emoji
    # Es: "WWDLW"
    return forma
