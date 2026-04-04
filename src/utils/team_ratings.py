"""
Database statico con forza realistica delle squadre principali.
I valori sono basati sulla qualità generale della squadra (0-100).
Aggiornati alla stagione 2024/2025.
"""

# Serie A - Forza squadre (0-100)
SERIE_A_RATINGS = {
    "Inter": 88,
    "Milan": 85,
    "Juventus": 84,
    "Napoli": 83,
    "Atalanta": 82,
    "Roma": 81,
    "Lazio": 80,
    "Fiorentina": 78,
    "Torino": 76,
    "Bologna": 75,
    "Monza": 74,
    "Genoa": 73,
    "Sassuolo": 72,
    "Udinese": 71,
    "Lecce": 70,
    "Empoli": 69,
    "Verona": 68,
    "Cagliari": 67,
    "Frosinone": 66,
    "Salernitana": 65,
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

# Unione di tutti i rating
TEAM_RATINGS = {}
TEAM_RATINGS.update(SERIE_A_RATINGS)
TEAM_RATINGS.update(PREMIER_RATINGS)
TEAM_RATINGS.update(LA_LIGA_RATINGS)
TEAM_RATINGS.update(BUNDESLIGA_RATINGS)
TEAM_RATINGS.update(LIGUE_1_RATINGS)


def get_team_rating(team_name, default=70):
    """
    Recupera il rating di una squadra.
    Cerca corrispondenza esatta o parziale.
    """
    # Cerca corrispondenza esatta
    if team_name in TEAM_RATINGS:
        return TEAM_RATINGS[team_name]
    
    # Cerca corrispondenza parziale (case insensitive)
    team_lower = team_name.lower()
    for name, rating in TEAM_RATINGS.items():
        if team_lower in name.lower() or name.lower() in team_lower:
            return rating
    
    # Fallback: usa default + variazione basata sul nome
    name_hash = sum(ord(c) for c in team_name)
    return default + (name_hash % 15)


def get_team_form(team_name, giornata_offset=0):
    """
    Ritorna la forma recente della squadra basata sul suo rating.
    Squadre più forti tendono ad avere forme migliori.
    La forma è deterministica per squadra ma varia leggermente nel tempo.
    """
    rating = get_team_rating(team_name)
    
    # Usa hash del nome + offset per variabilità controllata
    import random
    name_hash = sum(ord(c) for c in team_name)
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
