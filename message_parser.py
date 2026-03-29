"""
Parser automatico per estrarre risultati partite dai messaggi Telegram.
Estrae: squadra casa, squadra trasferta, risultato, risultato (H/D/A)
"""

import re
import csv
import os
from datetime import datetime

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
    'crotone': 'Crotone', 'parma': 'Parma', 'como': 'Como',
    'lazio': 'Lazio', 
    
    # Serie B (completo)
    'sassuolo': 'Sassuolo', 'spezia': 'Spezia', 'cittadella': 'Cittadella',
    'pisa': 'Pisa', 'brescia': 'Brescia', 'palermo': 'Palermo', 'modena': 'Modena',
    'sudtirol': 'Sudtirol', 'bari': 'Bari', 'reggiana': 'Reggiana', 'catanzaro': 'Catanzaro',
    'cesena': 'Cesena', 'juve stabia': 'Juve Stabia', 'sampdoria': 'Sampdoria',
    'carrarese': 'Carrarese', 'mantova': 'Mantova', 'frosinone': 'Frosinone',
    'salernitana': 'Salernitana', 'sampdoria': 'Sampdoria', 'cremonese': 'Cremonese',
    'brescia': 'Brescia', 'cosenza': 'Cosenza', 'lecco': 'Lecco', 'ternana': 'Ternana',
    'sampdoria': 'Sampdoria',
    
    # Serie C - squadre comuni
    'padova': 'Padova', 'perugia': 'Perugia', 'vicenza': 'Vicenza', 'triestina': 'Triestina',
    'pro vercelli': 'Pro Vercelli', 'albinoleffe': 'Albinoleffe', 'renate': 'Renate',
    'pro patria': 'Pro Patria', 'lecco': 'Lecco', 'alzano': 'Alzano', 'trento': 'Trento',
    'virtus verona': 'Virtus Verona', 'legnago': 'Legnago', 'arzignano': 'Arzignano',
    'calciopadova': 'Padova', 'giana erminio': 'Giana Erminio', 'pro sesto': 'Pro Sesto',
    'pontedera': 'Pontedera', 'carrarese': 'Carrarese', 'lucchese': 'Lucchese',
    'pescara': 'Pescara', 'ancona': 'Ancona', 'recanatese': 'Recanatese',
    'foggia': 'Foggia', 'turris': 'Turris', 'avellino': 'Avellino', 'cavese': 'Cavese',
    'potenza': 'Potenza', 'francavilla': 'Francavilla', 'taranto': 'Taranto',
    'monopoli': 'Monopoli', 'virtus francavilla': 'Virtus Francavilla',
    'brindisi': 'Brindisi', 'lecce': 'Lecce', 'messina': 'Messina', 'catania': 'Catania',
    'acerenza': 'Acerenza', 'picerno': 'Picerno', 'giugliano': 'Giugliano',
    'sorrento': 'Sorrento', 'paganese': 'Paganese', 'crotone': 'Crotone',
    
    # Premier League
    'arsenal': 'Arsenal', 'liverpool': 'Liverpool', 'manchester city': 'Man City',
    'man city': 'Man City', 'mancity': 'Man City', 'chelsea': 'Chelsea',
    'tottenham': 'Tottenham', 'spurs': 'Tottenham', 'manchester united': 'Man United',
    'man united': 'Man United', 'man utd': 'Man United', 'manutd': 'Man United',
    'newcastle': 'Newcastle', 'brighton': 'Brighton', 'west ham': 'West Ham',
    'aston villa': 'Aston Villa', 'villa': 'Aston Villa', 'brentford': 'Brentford',
    'crystal palace': 'Crystal Palace', 'everton': 'Everton', 'fulham': 'Fulham',
    'wolves': 'Wolves', 'wolverhampton': 'Wolves', 'bournemouth': 'Bournemouth',
    'nottingham forest': 'Forest', 'forest': 'Nottingham Forest', 'sunderland': 'Sunderland',
    'ipswich': 'Ipswich', 'leicester': 'Leicester', 'southampton': 'Southampton',
    
    # Ligue 1 (Francia)
    'psg': 'PSG', 'paris sg': 'PSG', 'paris saint-germain': 'PSG',
    'marseille': 'Marseille', 'olympique marseille': 'Marseille', 'om': 'Marseille',
    'lyon': 'Lyon', 'olympique lyon': 'Lyon', 'ol': 'Lyon',
    'monaco': 'Monaco', 'lille': 'Lille', 'rennes': 'Rennes', 'nice': 'Nice',
    'strasburgo': 'Strasbourg', 'strasbourg': 'Strasbourg',
    'lens': 'Lens', 'reims': 'Reims', 'montpellier': 'Montpellier',
    'angers': 'Angers', 'nantes': 'Nantes', 'toulouse': 'Toulouse',
    'le havre': 'Le Havre', 'clermont': 'Clermont', 'brest': 'Brest',
    'metz': 'Metz', 'lorient': 'Lorient',
    
    # Bundesliga
    'bayern': 'Bayern Munich', 'bayern munich': 'Bayern Munich',
    'dortmund': 'Dortmund', 'bvb': 'Dortmund',
    'leverkusen': 'Leverkusen', 'bayer leverkusen': 'Leverkusen',
    'leipzig': 'RB Leipzig', 'rb leipzig': 'RB Leipzig',
    'union berlino': 'Union Berlin', 'union berlin': 'Union Berlin',
    'freiburg': 'Freiburg', 'frankfurt': 'Frankfurt', 'wolfsburg': 'Wolfsburg',
    'mainz': 'Mainz', 'gladbach': 'Gladbach', 'hoffenheim': 'Hoffenheim',
    'werder brema': 'Werder Bremen', 'werder bremen': 'Werder Bremen',
    'heidenheim': 'Heidenheim', 'augsburg': 'Augsburg', 'stuttgart': 'Stuttgart',
    'bochum': 'Bochum', 'darmstadt': 'Darmstadt', 'koln': 'Koln', 'koln': 'Koln',
    
    # La Liga
    'real madrid': 'Real Madrid', 'madrid': 'Real Madrid',
    'barcellona': 'Barcelona', 'barcelona': 'Barcelona', 'barça': 'Barcelona',
    'atletico madrid': 'Atletico Madrid', 'atleti': 'Atletico Madrid',
    'sevilla': 'Sevilla', 'betis': 'Betis', 'real betis': 'Betis',
    'villarreal': 'Villarreal', 'real sociedad': 'Real Sociedad',
    'athletic bilbao': 'Athletic Bilbao', 'bilbao': 'Athletic Bilbao',
    'valencia': 'Valencia', 'celta vigo': 'Celta Vigo', 'getafe': 'Getafe',
    'osasuna': 'Osasuna', 'alaves': 'Alaves', 'girona': 'Girona',
    'rayo vallecano': 'Rayo Vallecano', 'espanyol': 'Espanyol',
    'cadiz': 'Cadiz', 'mallorca': 'Mallorca', 'las palmas': 'Las Palmas',
    'granada': 'Granada', 'almeria': 'Almeria', 'elche': 'Elche',
}


def normalize_team_name(name):
    """Normalizza nome squadra cercando nel database."""
    name_lower = name.lower().strip()
    
    # Se contiene parole da ignorare, è probabilmente un falso positivo
    for word in IGNORE_WORDS:
        if word in name_lower:
            # Prova a rimuovere la parola ignorata
            name_lower = name_lower.replace(word, '').strip()
    
    # Cerca match esatto
    if name_lower in KNOWN_TEAMS:
        return KNOWN_TEAMS[name_lower]
    
    # Cerca match parziale
    for key, value in KNOWN_TEAMS.items():
        if key in name_lower or name_lower in key:
            return value
    
    # Ritorna originale se non trovato (ma pulito)
    return name.strip()


def is_valid_team_name(name):
    """Verifica se il nome sembra una squadra valida."""
    name_clean = name.lower().strip()
    
    # Deve avere almeno 3 caratteri
    if len(name_clean) < 3:
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
    
    Ritorna dict con: home_team, away_team, home_goals, away_goals, result, confidence
    """
    if not text:
        return None
    
    # Rimuovi emoji e caratteri speciali per parsing
    text_clean = text.encode('ascii', 'ignore').decode('ascii')
    
    # Pattern più restrittivo: cattura solo nomi squadre (2+ parole o nomi propri)
    # Pattern 1: Squadra-Squadra X-Y (con eventuali emoji prima/dopo)
    # Usa look-behind per evitare di catturare testo prima delle squadre
    pattern1 = r'(?:^|[\s\n\r])\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*[\-–]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*[^0-9a-zA-Z]*(\d+)\s*[\-–:]\s*(\d+)'
    
    # Pattern 2: Squadra vs Squadra X-Y
    pattern2 = r'(?:^|[\s\n\r])\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:vs\.?|VS\.?)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*[^0-9a-zA-Z]*(\d+)\s*[\-–:]\s*(\d+)'
    
    # Pattern 3: Squadra : Squadra X-Y
    pattern3 = r'(?:^|[\s\n\r])\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*:\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s*[^0-9a-zA-Z]*(\d+)\s*[\-–:]\s*(\d+)'
    
    # Pattern 4: Cattura anche nomi singoli (senza spazi) per squadre come Inter, Milan
    pattern4 = r'(?:^|[\s\n\r])\s*([A-Z][a-zA-Z]+)\s*[\-–]\s*([A-Z][a-zA-Z]+)\s*[^0-9a-zA-Z]*(\d+)\s*[\-–:]\s*(\d+)'
    
    match = None
    
    # Prova pattern 1
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
        
        # Determina risultato H/D/A
        if home_goals > away_goals:
            result = 'H'  # Home win
        elif home_goals < away_goals:
            result = 'A'  # Away win
        else:
            result = 'D'  # Draw
        
        return {
            'home_team': home_team,
            'away_team': away_team,
            'home_goals': home_goals,
            'away_goals': away_goals,
            'result': result,
            'match_desc': f"{home_team} {home_goals}-{away_goals} {away_team}",
            'confidence': 'high' if home_team in KNOWN_TEAMS.values() and away_team in KNOWN_TEAMS.values() else 'medium'
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
    seen = set()  # Per evitare duplicati
    
    # Pattern per trovare tutte le possibili partite nel testo
    # Cerca sequenze: Nome-Nome numeri-numeri
    
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
        # Cerca tutti i pattern nel testo completo
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
                
                if home_goals > away_goals:
                    result_code = 'H'
                elif home_goals < away_goals:
                    result_code = 'A'
                else:
                    result_code = 'D'
                
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
                        'confidence': 'high' if home_team in KNOWN_TEAMS.values() and away_team in KNOWN_TEAMS.values() else 'medium'
                    })
            except:
                continue
    
    return results


def save_parsed_match(match_data, filename='parsed_matches.csv'):
    """Salva risultato parsato in CSV."""
    if not match_data:
        return False
    
    file_exists = os.path.exists(filename)
    
    with open(filename, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        # Header se file nuovo
        if not file_exists:
            writer.writerow(['Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTR'])
        
        # Scrivi dati
        writer.writerow([
            datetime.now().strftime('%Y-%m-%d'),
            match_data['home_team'],
            match_data['away_team'],
            match_data['home_goals'],
            match_data['away_goals'],
            match_data['result']
        ])
    
    return True


def process_message(text):
    """Processa un messaggio: parse di TUTTE le partite + save."""
    results = parse_all_matches_in_message(text)
    saved_count = 0
    
    for result in results:
        if save_parsed_match(result):
            saved_count += 1
    
    return results if saved_count > 0 else None


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
    ]
    
    print("🧪 Test Parser:")
    for msg in test_messages:
        results = parse_all_matches_in_message(msg)
        if results:
            for r in results:
                print(f"✅ {msg[:40]}... → {r['match_desc']} ({r['result']}) [{r['confidence']}]")
        else:
            print(f"❌ {msg[:40]}... → Non riconosciuto")
