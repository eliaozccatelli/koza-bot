"""
Parser automatico per estrarre risultati partite dai messaggi Telegram.
Estrae: squadra casa, squadra trasferta, risultato, risultato (H/D/A), competizione
"""

import re
import csv
import os
from datetime import datetime, timedelta

# Parole da ignorare (non sono nomi squadre)
IGNORE_WORDS = {
    'giornata', 'giorno', 'partita', 'match', 'finale', 'vittoria', 'sconfitta',
    'pareggio', 'rigori', 'gol', 'calcio', 'campionato', 'league', 'premier',
    'bundesliga', 'serie', 'liga', 'ligue', 'prima', 'seconda', 'divisione',
    'andata', 'ritorno', 'playoff', 'play', 'off', 'regular', 'season',
    'stagione', 'torneo', 'coppa', 'italia', 'europa', 'champions', 'supercoppa',
    'sabato', 'domenica', 'lunedi', 'martedi', 'mercoledi', 'giovedi', 'venerdi',
    'ieri', 'oggi', 'domani', 'live', 'risultato', 'risultati', 'formazione',
    'cronaca', 'tabellino', 'highlights', 'post', 'matchday', 'round'
}

# Database squadre note per matching fuzzy - Serie A + Serie B + altre
KNOWN_TEAMS = {
    # Serie A
    'inter': 'Inter', 'milan': 'Milan', 'juventus': 'Juventus', 'juve': 'Juventus',
    'napoli': 'Napoli', 'roma': 'Roma', 'lazio': 'Lazio', 'fiorentina': 'Fiorentina',
    'atalanta': 'Atalanta', 'bologna': 'Bologna', 'torino': 'Torino', 'udinese': 'Udinese',
    'monza': 'Monza', 'frosinone': 'Frosinone', 'empoli': 'Empoli', 'sassuolo': 'Sassuolo',
    'lecce': 'Lecce', 'cagliari': 'Cagliari', 'verona': 'Verona', 'genoa': 'Genoa',
    'salernitana': 'Salernitana', 'spezia': 'Spezia', 'cremonese': 'Cremonese',
    'sampdoria': 'Sampdoria', 'venezia': 'Venezia', 'benevento': 'Benevento',
    'crotone': 'Crotone', 'parma': 'Parma', 'como': 'Como', 'pisa': 'Pisa',

    # Serie B (completo)
    'cittadella': 'Cittadella',
    'brescia': 'Brescia', 'palermo': 'Palermo', 'modena': 'Modena',
    'sudtirol': 'Sudtirol', 'bari': 'Bari', 'reggiana': 'Reggiana', 'catanzaro': 'Catanzaro',
    'cesena': 'Cesena', 'juve stabia': 'Juve Stabia',
    'carrarese': 'Carrarese', 'mantova': 'Mantova',
    'cosenza': 'Cosenza', 'lecco': 'Lecco', 'ternana': 'Ternana',

    # Serie C - squadre comuni
    'padova': 'Padova', 'perugia': 'Perugia', 'vicenza': 'Vicenza', 'triestina': 'Triestina',
    'pro vercelli': 'Pro Vercelli', 'albinoleffe': 'Albinoleffe', 'renate': 'Renate',
    'pro patria': 'Pro Patria', 'trento': 'Trento',
    'virtus verona': 'Virtus Verona', 'legnago': 'Legnago', 'arzignano': 'Arzignano',
    'giana erminio': 'Giana Erminio', 'pro sesto': 'Pro Sesto',
    'pontedera': 'Pontedera', 'lucchese': 'Lucchese',
    'pescara': 'Pescara', 'ancona': 'Ancona', 'recanatese': 'Recanatese',
    'foggia': 'Foggia', 'turris': 'Turris', 'avellino': 'Avellino', 'cavese': 'Cavese',
    'potenza': 'Potenza', 'francavilla': 'Francavilla', 'taranto': 'Taranto',
    'monopoli': 'Monopoli', 'virtus francavilla': 'Virtus Francavilla',
    'brindisi': 'Brindisi', 'messina': 'Messina', 'catania': 'Catania',
    'picerno': 'Picerno', 'giugliano': 'Giugliano',
    'sorrento': 'Sorrento', 'paganese': 'Paganese',

    # Premier League
    'arsenal': 'Arsenal', 'liverpool': 'Liverpool', 'manchester city': 'Man City',
    'man city': 'Man City', 'mancity': 'Man City', 'chelsea': 'Chelsea',
    'tottenham': 'Tottenham', 'spurs': 'Tottenham', 'manchester united': 'Man United',
    'man united': 'Man United', 'man utd': 'Man United', 'manutd': 'Man United',
    'newcastle': 'Newcastle', 'brighton': 'Brighton', 'west ham': 'West Ham',
    'aston villa': 'Aston Villa', 'villa': 'Aston Villa', 'brentford': 'Brentford',
    'crystal palace': 'Crystal Palace', 'everton': 'Everton', 'fulham': 'Fulham',
    'wolves': 'Wolves', 'wolverhampton': 'Wolves', 'bournemouth': 'Bournemouth',
    'nottingham forest': 'Nottingham Forest', 'forest': 'Nottingham Forest',
    'sunderland': 'Sunderland',
    'ipswich': 'Ipswich', 'leicester': 'Leicester', 'southampton': 'Southampton',
    'burnley': 'Burnley', 'leeds': 'Leeds',

    # Ligue 1 (Francia)
    'psg': 'PSG', 'paris sg': 'PSG', 'paris saint-germain': 'PSG',
    'marseille': 'Marseille', 'olympique marseille': 'Marseille', 'om': 'Marseille',
    'marsiglia': 'Marsiglia',
    'lyon': 'Lyon', 'olympique lyon': 'Lyon', 'ol': 'Lyon',
    'lione': 'Lione',
    'monaco': 'Monaco', 'lille': 'Lille', 'rennes': 'Rennes', 'nice': 'Nice',
    'nizza': 'Nizza',
    'strasburgo': 'Strasbourg', 'strasbourg': 'Strasbourg',
    'lens': 'Lens', 'reims': 'Reims', 'montpellier': 'Montpellier',
    'angers': 'Angers', 'nantes': 'Nantes', 'toulouse': 'Toulouse',
    'le havre': 'Le Havre', 'clermont': 'Clermont', 'brest': 'Brest',
    'metz': 'Metz', 'lorient': 'Lorient', 'auxerre': 'Auxerre',
    'paris fc': 'Paris FC',

    # Bundesliga
    'bayern': 'Bayern Munich', 'bayern munich': 'Bayern Munich',
    'bayern monaco': 'Bayern Monaco',
    'dortmund': 'Dortmund', 'bvb': 'Dortmund',
    'leverkusen': 'Leverkusen', 'bayer leverkusen': 'Leverkusen',
    'leipzig': 'RB Leipzig', 'rb leipzig': 'RB Leipzig', 'lipsia': 'Lipsia',
    'union berlino': 'Union Berlin', 'union berlin': 'Union Berlin',
    'freiburg': 'Freiburg', 'friburgo': 'Friburgo',
    'frankfurt': 'Frankfurt', 'eintracht francoforte': 'Eintracht Francoforte',
    'wolfsburg': 'Wolfsburg',
    'mainz': 'Mainz', 'gladbach': 'Gladbach', 'hoffenheim': 'Hoffenheim',
    'werder brema': 'Werder Bremen', 'werder bremen': 'Werder Bremen',
    'heidenheim': 'Heidenheim', 'augsburg': 'Augsburg',
    'stuttgart': 'Stuttgart', 'stoccarda': 'Stoccarda',
    'bochum': 'Bochum', 'darmstadt': 'Darmstadt', 'koln': 'Koln',
    'pauli': 'Pauli', 'amburgo': 'Amburgo',

    # La Liga
    'real madrid': 'Real Madrid', 'madrid': 'Real Madrid',
    'barcellona': 'Barcelona', 'barcelona': 'Barcelona', 'barça': 'Barcelona',
    'atletico madrid': 'Atletico Madrid', 'atleti': 'Atletico Madrid',
    'sevilla': 'Sevilla', 'siviglia': 'Siviglia',
    'betis': 'Betis', 'real betis': 'Betis',
    'villarreal': 'Villarreal', 'real sociedad': 'Real Sociedad',
    'athletic bilbao': 'Athletic Bilbao', 'bilbao': 'Athletic Bilbao',
    'valencia': 'Valencia', 'celta vigo': 'Celta Vigo', 'getafe': 'Getafe',
    'osasuna': 'Osasuna', 'alaves': 'Alaves', 'girona': 'Girona',
    'rayo vallecano': 'Rayo Vallecano', 'espanyol': 'Espanyol',
    'cadiz': 'Cadiz', 'mallorca': 'Mallorca', 'las palmas': 'Las Palmas',
    'granada': 'Granada', 'almeria': 'Almeria', 'elche': 'Elche',
    'levante': 'Levante', 'real oviedo': 'Real Oviedo',
}

# ============================================================
# MAPPATURA SQUADRE -> COMPETIZIONI (per inferire la competizione)
# ============================================================
TEAM_TO_COMPETITION = {
    # Serie A
    'Inter': 'Serie A', 'Milan': 'Serie A', 'Juventus': 'Serie A', 'Napoli': 'Serie A',
    'Roma': 'Serie A', 'Lazio': 'Serie A', 'Fiorentina': 'Serie A', 'Atalanta': 'Serie A',
    'Bologna': 'Serie A', 'Torino': 'Serie A', 'Udinese': 'Serie A', 'Monza': 'Serie A',
    'Sassuolo': 'Serie A', 'Lecce': 'Serie A', 'Cagliari': 'Serie A', 'Verona': 'Serie A',
    'Genoa': 'Serie A', 'Cremonese': 'Serie A', 'Parma': 'Serie A', 'Como': 'Serie A',
    'Empoli': 'Serie A', 'Pisa': 'Serie A',

    # Premier League
    'Arsenal': 'Premier League', 'Liverpool': 'Premier League', 'Man City': 'Premier League',
    'Chelsea': 'Premier League', 'Tottenham': 'Premier League', 'Man United': 'Premier League',
    'Newcastle': 'Premier League', 'Brighton': 'Premier League', 'West Ham': 'Premier League',
    'Aston Villa': 'Premier League', 'Brentford': 'Premier League', 'Crystal Palace': 'Premier League',
    'Everton': 'Premier League', 'Fulham': 'Premier League', 'Wolves': 'Premier League',
    'Nottingham Forest': 'Premier League', 'Bournemouth': 'Premier League',
    'Burnley': 'Premier League', 'Leeds': 'Premier League', 'Sunderland': 'Premier League',
    'Ipswich': 'Premier League', 'Leicester': 'Premier League', 'Southampton': 'Premier League',

    # Ligue 1
    'PSG': 'Ligue 1', 'Marsiglia': 'Ligue 1', 'Lyon': 'Ligue 1', 'Lione': 'Ligue 1',
    'Monaco': 'Ligue 1', 'Lille': 'Ligue 1', 'Rennes': 'Ligue 1', 'Nizza': 'Ligue 1',
    'Strasbourg': 'Ligue 1', 'Lens': 'Ligue 1', 'Reims': 'Ligue 1',
    'Nantes': 'Ligue 1', 'Toulouse': 'Ligue 1', 'Le Havre': 'Ligue 1',
    'Brest': 'Ligue 1', 'Metz': 'Ligue 1', 'Lorient': 'Ligue 1',
    'Auxerre': 'Ligue 1', 'Angers': 'Ligue 1', 'Paris FC': 'Ligue 1',
    'Montpellier': 'Ligue 1', 'Clermont': 'Ligue 1', 'Nice': 'Ligue 1',
    'Marseille': 'Ligue 1',

    # Bundesliga
    'Bayern Munich': 'Bundesliga', 'Bayern Monaco': 'Bundesliga', 'Dortmund': 'Bundesliga',
    'Leverkusen': 'Bundesliga', 'RB Leipzig': 'Bundesliga', 'Lipsia': 'Bundesliga',
    'Union Berlin': 'Bundesliga', 'Freiburg': 'Bundesliga', 'Friburgo': 'Bundesliga',
    'Frankfurt': 'Bundesliga', 'Eintracht Francoforte': 'Bundesliga',
    'Wolfsburg': 'Bundesliga', 'Mainz': 'Bundesliga', 'Gladbach': 'Bundesliga',
    'Hoffenheim': 'Bundesliga', 'Werder Bremen': 'Bundesliga',
    'Heidenheim': 'Bundesliga', 'Augsburg': 'Bundesliga',
    'Stuttgart': 'Bundesliga', 'Stoccarda': 'Bundesliga',
    'Bochum': 'Bundesliga', 'Koln': 'Bundesliga', 'Darmstadt': 'Bundesliga',
    'Pauli': 'Bundesliga', 'Amburgo': 'Bundesliga',

    # La Liga
    'Real Madrid': 'La Liga', 'Barcelona': 'La Liga', 'Atletico Madrid': 'La Liga',
    'Real Sociedad': 'La Liga', 'Athletic Bilbao': 'La Liga', 'Villarreal': 'La Liga',
    'Sevilla': 'La Liga', 'Siviglia': 'La Liga', 'Betis': 'La Liga',
    'Valencia': 'La Liga', 'Celta Vigo': 'La Liga', 'Getafe': 'La Liga',
    'Osasuna': 'La Liga', 'Alaves': 'La Liga', 'Girona': 'La Liga',
    'Rayo Vallecano': 'La Liga', 'Espanyol': 'La Liga', 'Cadiz': 'La Liga',
    'Mallorca': 'La Liga', 'Las Palmas': 'La Liga', 'Granada': 'La Liga',
    'Almeria': 'La Liga', 'Elche': 'La Liga', 'Levante': 'La Liga',
    'Real Oviedo': 'La Liga',
}


from src.utils.team_ratings import _resolve_alias, get_competition

def infer_competition(home_team, away_team):
    """Inferisce la competizione basandosi sulle squadre e sul database centrale."""
    comp_home = get_competition(home_team)
    comp_away = get_competition(away_team)

    if comp_home != "Unknown" and comp_away != "Unknown" and comp_home == comp_away:
        return comp_home
    elif comp_home != "Unknown":
        return comp_home
    elif comp_away != "Unknown":
        return comp_away
    
    # Fallback su mappatura locale se non trovata in JSON
    comp_home = TEAM_TO_COMPETITION.get(home_team)
    comp_away = TEAM_TO_COMPETITION.get(away_team)
    
    if comp_home and comp_away and comp_home == comp_away:
        return comp_home
    elif comp_home:
        return comp_home
    elif comp_away:
        return comp_away
    else:
        return "Unknown"


def normalize_team_name(name):
    """Normalizza nome squadra usando il database centrale degli alias."""
    if not name:
        return None
        
    name_lower = name.lower().strip()

    # Se contiene parole da ignorare, scartalo completamente se il nome è SOLO la parola
    for word in IGNORE_WORDS:
        if name_lower == word:
            return None
        # Rimuovi la parola ignorata se è all'inizio
        if name_lower.startswith(word + ' '):
            name_lower = name_lower[len(word):].strip()

    # Usa il resolver centrale che ora legge da JSON
    resolved = _resolve_alias(name_lower)
    
    # Se il resolver ha ritornato lo stesso nome originale (non ha trovato alias), 
    # ritorniamo il nome pulito
    return resolved if resolved else name.strip()


def is_valid_team_name(name):
    """Verifica se il nome sembra una squadra valida."""
    name_clean = name.lower().strip()

    # Deve avere almeno 3 caratteri
    if len(name_clean) < 3:
        return False

    # Non deve contenere newline o caratteri di controllo
    if '\n' in name or '\r' in name or '\t' in name:
        return False

    # Non deve contenere solo parole da ignorare
    for word in IGNORE_WORDS:
        if name_clean == word or name_clean.startswith(word + ' '):
            return False

    # Deve contenere lettere
    if not re.search(r'[a-zA-Z]{2,}', name):
        return False

    return True


def parse_match_result(text):
    """
    Estrae risultato partita da messaggio.
    Pattern supportati:
    - SquadraA-SquadraB 2-1
    - SquadraA vs SquadraB 2-1
    - SquadraA - SquadraB: 2-1
    - 🇫🇷 SquadraA-SquadraB 🇫🇷 1-2

    Ritorna dict con: home_team, away_team, home_goals, away_goals, result, confidence, competition
    """
    if not text:
        return None

    # Rimuovi emoji e caratteri speciali per parsing
    text_clean = text.encode('ascii', 'ignore').decode('ascii')

    # Pattern più restrittivo: cattura solo nomi squadre (2+ parole o nomi propri)
    pattern1 = r'(?:^|[\s\n\r])\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*[\-–]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*[^0-9a-zA-Z]*(\d+)\s*[\-–:]\s*(\d+)'
    pattern2 = r'(?:^|[\s\n\r])\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:vs\.?|VS\.?)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*[^0-9a-zA-Z]*(\d+)\s*[\-–:]\s*(\d+)'
    pattern3 = r'(?:^|[\s\n\r])\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*:\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*[^0-9a-zA-Z]*(\d+)\s*[\-–:]\s*(\d+)'
    pattern4 = r'(?:^|[\s\n\r])\s*([A-Z][a-zA-Z]+)\s*[\-–]\s*([A-Z][a-zA-Z]+)\s*[^0-9a-zA-Z]*(\d+)\s*[\-–:]\s*(\d+)'

    match = None

    match = re.search(pattern1, text_clean, re.IGNORECASE)
    if not match:
        match = re.search(pattern2, text_clean, re.IGNORECASE)
    if not match:
        match = re.search(pattern3, text_clean, re.IGNORECASE)
    if not match:
        match = re.search(pattern4, text_clean, re.IGNORECASE)

    if match:
        home_team_raw = match.group(1).strip()
        away_team_raw = match.group(2).strip()
        home_goals = int(match.group(3))
        away_goals = int(match.group(4))

        # Verifica nomi validi
        if not is_valid_team_name(home_team_raw) or not is_valid_team_name(away_team_raw):
            return None

        # Normalizza nomi squadre
        home_team = normalize_team_name(home_team_raw)
        away_team = normalize_team_name(away_team_raw)

        # Se la normalizzazione ha restituito None (parola ignorata), scarta
        if not home_team or not away_team:
            return None

        # Determina risultato H/D/A
        if home_goals > away_goals:
            result = 'H'
        elif home_goals < away_goals:
            result = 'A'
        else:
            result = 'D'

        # Inferisci competizione
        competition = infer_competition(home_team, away_team)

        return {
            'home_team': home_team,
            'away_team': away_team,
            'home_goals': home_goals,
            'away_goals': away_goals,
            'result': result,
            'match_desc': f"{home_team} {home_goals}-{away_goals} {away_team}",
            'confidence': 'high' if home_team in KNOWN_TEAMS.values() and away_team in KNOWN_TEAMS.values() else 'medium',
            'competition': competition,
        }

    return None


def parse_all_matches_in_message(text):
    """
    Trova TUTTE le partite in un messaggio (supporta messaggi multipli).
    Ritorna lista di dict con i risultati.
    """
    if not text:
        return []

    results = []
    seen = set()

    # Prima pulizia - rimuovi emoji ma mantieni struttura
    text_clean = text.encode('ascii', 'ignore').decode('ascii')

    # Dividi per newline per analizzare riga per riga
    lines = text_clean.split('\n')

    for line in lines:
        result = parse_match_result(line)
        if result:
            key = f"{result['home_team']}_{result['away_team']}_{result['home_goals']}_{result['away_goals']}"
            if key not in seen:
                seen.add(key)
                results.append(result)

    # Se non ho trovato niente per riga, prova con regex globale
    if not results:
        pattern_global = r'([A-Z][a-zA-Z]+(?:\s+[A-Z][a-z]+)?)\s*[\-–]\s*([A-Z][a-zA-Z]+(?:\s+[A-Z][a-z]+)?)\s*[^0-9a-zA-Z]*(\d+)\s*[\-–:]\s*(\d+)'
        matches = re.finditer(pattern_global, text_clean, re.IGNORECASE)

        for match in matches:
            try:
                home_team_raw = match.group(1).strip()
                away_team_raw = match.group(2).strip()
                home_goals = int(match.group(3))
                away_goals = int(match.group(4))

                if not is_valid_team_name(home_team_raw) or not is_valid_team_name(away_team_raw):
                    continue

                home_team = normalize_team_name(home_team_raw)
                away_team = normalize_team_name(away_team_raw)

                if not home_team or not away_team:
                    continue

                if home_goals > away_goals:
                    result_code = 'H'
                elif home_goals < away_goals:
                    result_code = 'A'
                else:
                    result_code = 'D'

                competition = infer_competition(home_team, away_team)

                key = f"{home_team}_{away_team}_{home_goals}_{away_goals}"
                if key not in seen:
                    seen.add(key)
                    results.append({
                        'home_team': home_team,
                        'away_team': away_team,
                        'home_goals': home_goals,
                        'away_goals': away_goals,
                        'result': result_code,
                        'match_desc': f"{home_team} {home_goals}-{away_goals} {away_team}",
                        'confidence': 'high' if home_team in KNOWN_TEAMS.values() and away_team in KNOWN_TEAMS.values() else 'medium',
                        'competition': competition,
                    })
            except Exception:
                continue

    # Se ancora niente, prova ricerca intelligente per testi narrativi
    if not results:
        text_lower = text_clean.lower()
        found_positions = []

        for key, canonical in KNOWN_TEAMS.items():
            if len(key) < 4:
                continue
            match_team = re.search(r'\b' + re.escape(key) + r'\b', text_lower)
            if match_team and canonical not in [t[1] for t in found_positions]:
                found_positions.append((match_team.start(), canonical))

        found_positions.sort(key=lambda x: x[0])
        found_teams = [t[1] for t in found_positions]

        score_matches = list(re.finditer(r'(\d{1,2})\s*[\-–]\s*(\d{1,2})', text_clean))

        if len(found_teams) >= 2 and score_matches:
            home_team = found_teams[0]
            away_team = found_teams[1]

            best_score = None
            for sm in score_matches:
                hg = int(sm.group(1))
                ag = int(sm.group(2))
                if hg <= 9 and ag <= 9 and (hg + ag) <= 15:
                    after = text_clean[sm.end():sm.end()+3]
                    before = text_clean[max(0, sm.start()-3):sm.start()]
                    if not re.search(r'[\'°]', after) and not re.search(r'al\s*$', before):
                        best_score = (hg, ag)
                        break

            if best_score:
                hg, ag = best_score
                if hg > ag:
                    result_code = 'H'
                elif hg < ag:
                    result_code = 'A'
                else:
                    result_code = 'D'

                competition = infer_competition(home_team, away_team)

                key = f"{home_team}_{away_team}_{hg}_{ag}"
                if key not in seen:
                    seen.add(key)
                    results.append({
                        'home_team': home_team,
                        'away_team': away_team,
                        'home_goals': hg,
                        'away_goals': ag,
                        'result': result_code,
                        'match_desc': f"{home_team} {hg}-{ag} {away_team}",
                        'confidence': 'medium',
                        'competition': competition,
                    })

    return results


def _is_duplicate(match_data, filename='parsed_matches.csv'):
    """
    Controlla se la partita è già presente nel CSV.
    Controlla anche date vicine (±1 giorno) per evitare duplicati cross-day.
    """
    if not os.path.exists(filename):
        return False

    home = match_data['home_team'].strip().lower()
    away = match_data['away_team'].strip().lower()
    hg = str(match_data['home_goals'])
    ag = str(match_data['away_goals'])

    try:
        with open(filename, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rh = row.get('HomeTeam', '').strip().lower()
                ra = row.get('AwayTeam', '').strip().lower()
                rhg = str(row.get('FTHG', '')).strip()
                rag = str(row.get('FTAG', '')).strip()

                # Match esatto su squadre e gol
                if rh == home and ra == away and rhg == hg and rag == ag:
                    return True

                # Match stesse squadre (anche invertite) e stesso risultato, date vicine
                if (rh == home and ra == away) or (rh == away and ra == home):
                    row_date_str = row.get('Date', '').strip()
                    if row_date_str:
                        try:
                            row_date = datetime.strptime(row_date_str, '%Y-%m-%d').date()
                            today = datetime.now().date()
                            if abs((today - row_date).days) <= 1:
                                if rhg == hg and rag == ag:
                                    return True
                        except ValueError:
                            pass
    except Exception:
        pass

    return False


def save_parsed_match(match_data, filename='parsed_matches.csv'):
    """Salva risultato parsato in CSV con competizione. Ignora duplicati."""
    if not match_data:
        return False

    # Validazione extra: rifiuta nomi con newline o parole chiave spurie
    home = match_data.get('home_team', '')
    away = match_data.get('away_team', '')
    if '\n' in home or '\n' in away or '\r' in home or '\r' in away:
        return False
    if not home or not away or len(home) < 2 or len(away) < 2:
        return False

    # Controlla duplicati
    if _is_duplicate(match_data, filename):
        return False

    file_exists = os.path.exists(filename)

    # Controlla se il file ha già la colonna Competition
    has_competition_column = False
    if file_exists:
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                header = f.readline().strip()
                has_competition_column = 'Competition' in header
        except Exception:
            pass

    with open(filename, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)

        if not file_exists:
            writer.writerow(['Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTR', 'Competition'])
            has_competition_column = True

        competition = match_data.get('competition', infer_competition(home, away))

        row = [
            datetime.now().strftime('%Y-%m-%d'),
            match_data['home_team'],
            match_data['away_team'],
            match_data['home_goals'],
            match_data['away_goals'],
            match_data['result']
        ]
        if has_competition_column:
            row.append(competition)

        writer.writerow(row)

    return True


def process_message(text):
    """Processa un messaggio: parse di TUTTE le partite + save. Ignora duplicati."""
    results = parse_all_matches_in_message(text)
    saved_count = 0
    skipped = 0

    for result in results:
        if save_parsed_match(result):
            saved_count += 1
        else:
            skipped += 1

    if saved_count > 0 or skipped > 0:
        return {'saved': results[:saved_count] if saved_count else [],
                'saved_count': saved_count, 'skipped': skipped,
                'all_results': results}
    return None


# Test
if __name__ == "__main__":
    test_messages = [
        "🇫🇷 Lione-Monaco 🇫🇷 1-2: Vittoria del Monaco",
        "🇫🇷 Marsiglia-Lille 🇫🇷 1-2: Crolla Marsiglia",
        "Inter-Juve 2-1: Derby d'Italia",
        "Brighton-Liverpool 2-1: Sorpresa",
        "Real Madrid vs Barcelona 3-1: El Clasico",
        "Monopoli - Benevento 2-1: Serie C",
        "31° giornata\nMilan-Torino 3-2\nInter-Napoli 1-1",
        "giornata Elche-Mallorca 2-1",  # Deve essere gestito correttamente
    ]

    print("🧪 Test Parser:")
    for msg in test_messages:
        results = parse_all_matches_in_message(msg)
        if results:
            for r in results:
                print(f"✅ {msg[:40]}... → {r['match_desc']} ({r['result']}) [{r['confidence']}] [{r['competition']}]")
        else:
            print(f"❌ {msg[:40]}... → Non riconosciuto")
