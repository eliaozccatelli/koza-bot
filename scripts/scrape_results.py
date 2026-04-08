"""
🔄 Auto-scraper per risultati partite da football-data.org

Scarica automaticamente i risultati delle partite della settimana corrente
e li salva in parsed_matches.csv.

API: football-data.org (v4) - Piano gratuito: 10 chiamate/minuto
Leghe supportate: Serie A, Premier League, La Liga, Bundesliga, Ligue 1, Champions League

Uso:
    python scripts/scrape_results.py                  # Scarica ultimi 3 giorni
    python scripts/scrape_results.py --days 7         # Scarica ultima settimana
    python scripts/scrape_results.py --league SA      # Solo Serie A
    python scripts/scrape_results.py --dry-run        # Mostra senza salvare
"""

import argparse
import csv
import json
import logging
import os
import sys
import time
from datetime import datetime, timedelta

# Aggiungi radice progetto al path per importazioni
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    import requests
except ImportError:
    print("❌ Installa requests: pip install requests")
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════
# Configurazione
# ══════════════════════════════════════════════════════════

BASE_URL = "https://api.football-data.org/v4"

# Leghe supportate dal piano gratuito
LEAGUES = {
    'SA':  {'code': 'SA',  'name': 'Serie A',        'competition': 'Serie A'},
    'PL':  {'code': 'PL',  'name': 'Premier League',  'competition': 'Premier League'},
    'PD':  {'code': 'PD',  'name': 'La Liga',         'competition': 'La Liga'},
    'BL1': {'code': 'BL1', 'name': 'Bundesliga',      'competition': 'Bundesliga'},
    'FL1': {'code': 'FL1', 'name': 'Ligue 1',         'competition': 'Ligue 1'},
    'CL':  {'code': 'CL',  'name': 'Champions League', 'competition': 'Champions League'},
}

# Mapping nomi squadre API -> nomi KOZA (normalizzazione)
TEAM_NAME_MAPPING = {
    # Serie A
    'FC Internazionale Milano': 'Inter',
    'AC Milan': 'Milan',
    'SSC Napoli': 'Napoli',
    'AS Roma': 'Roma',
    'SS Lazio': 'Lazio',
    'Juventus FC': 'Juventus',
    'ACF Fiorentina': 'Fiorentina',
    'Atalanta BC': 'Atalanta',
    'Bologna FC 1909': 'Bologna',
    'Torino FC': 'Torino',
    'Udinese Calcio': 'Udinese',
    'AC Monza': 'Monza',
    'US Sassuolo Calcio': 'Sassuolo',
    'US Lecce': 'Lecce',
    'Cagliari Calcio': 'Cagliari',
    'Hellas Verona FC': 'Verona',
    'Genoa CFC': 'Genoa',
    'US Cremonese': 'Cremonese',
    'Parma Calcio 1913': 'Parma',
    'Como 1907': 'Como',
    'Empoli FC': 'Empoli',
    'AC Pisa 1909': 'Pisa',

    # Premier League
    'Manchester City FC': 'Man City',
    'Liverpool FC': 'Liverpool',
    'Arsenal FC': 'Arsenal',
    'Chelsea FC': 'Chelsea',
    'Manchester United FC': 'Man United',
    'Tottenham Hotspur FC': 'Tottenham',
    'Newcastle United FC': 'Newcastle',
    'Aston Villa FC': 'Aston Villa',
    'Brighton & Hove Albion FC': 'Brighton',
    'West Ham United FC': 'West Ham',
    'Brentford FC': 'Brentford',
    'Crystal Palace FC': 'Crystal Palace',
    'Wolverhampton Wanderers FC': 'Wolves',
    'Fulham FC': 'Fulham',
    'Everton FC': 'Everton',
    'Nottingham Forest FC': 'Nottingham Forest',
    'AFC Bournemouth': 'Bournemouth',
    'Burnley FC': 'Burnley',
    'Ipswich Town FC': 'Ipswich',
    'Leicester City FC': 'Leicester',
    'Southampton FC': 'Southampton',

    # La Liga
    'Real Madrid CF': 'Real Madrid',
    'FC Barcelona': 'Barcelona',
    'Club Atlético de Madrid': 'Atletico Madrid',
    'Real Sociedad de Fútbol': 'Real Sociedad',
    'Athletic Club': 'Athletic Bilbao',
    'Villarreal CF': 'Villarreal',
    'Sevilla FC': 'Siviglia',
    'Real Betis Balompié': 'Betis',
    'Valencia CF': 'Valencia',
    'RC Celta de Vigo': 'Celta Vigo',
    'Getafe CF': 'Getafe',
    'CA Osasuna': 'Osasuna',
    'UD Las Palmas': 'Las Palmas',
    'Rayo Vallecano de Madrid': 'Rayo Vallecano',
    'RCD Mallorca': 'Mallorca',
    'Deportivo Alavés': 'Alaves',
    'Girona FC': 'Girona',
    'RCD Espanyol de Barcelona': 'Espanyol',
    'Elche CF': 'Elche',
    'Levante UD': 'Levante',
    'Real Oviedo': 'Real Oviedo',

    # Bundesliga
    'FC Bayern München': 'Bayern Monaco',
    'Borussia Dortmund': 'Dortmund',
    'Bayer 04 Leverkusen': 'Leverkusen',
    'RB Leipzig': 'Lipsia',
    'VfB Stuttgart': 'Stoccarda',
    'Eintracht Frankfurt': 'Eintracht Francoforte',
    'VfL Wolfsburg': 'Wolfsburg',
    'SC Freiburg': 'Friburgo',
    'TSG 1899 Hoffenheim': 'Hoffenheim',
    '1. FSV Mainz 05': 'Mainz',
    '1. FC Union Berlin': 'Union Berlin',
    'Borussia Mönchengladbach': 'Gladbach',
    'SV Werder Bremen': 'Werder Bremen',
    'FC Augsburg': 'Augsburg',
    '1. FC Heidenheim 1846': 'Heidenheim',
    'VfL Bochum 1848': 'Bochum',
    'FC St. Pauli 1910': 'Pauli',
    'Hamburger SV': 'Amburgo',
    '1. FC Köln': 'Koln',
    'SV Darmstadt 98': 'Darmstadt',

    # Ligue 1
    'Paris Saint-Germain FC': 'PSG',
    'AS Monaco FC': 'Monaco',
    'LOSC Lille': 'Lille',
    'Olympique de Marseille': 'Marsiglia',
    'Stade Rennais FC 1901': 'Rennes',
    'OGC Nice': 'Nizza',
    'Olympique Lyonnais': 'Lione',
    'RC Lens': 'Lens',
    'RC Strasbourg Alsace': 'Strasbourg',
    'FC Nantes': 'Nantes',
    'Stade de Reims': 'Reims',
    'Stade Brestois 29': 'Brest',
    'FC Metz': 'Metz',
    'FC Lorient': 'Lorient',
    'AJ Auxerre': 'Auxerre',
    'Angers SCO': 'Angers',
    'Montpellier HSC': 'Montpellier',
    'Toulouse FC': 'Toulouse',
    'Le Havre AC': 'Le Havre',
    'Clermont Foot 63': 'Clermont',
    'Paris FC': 'Paris FC',
}


from src.utils.team_ratings import _resolve_alias, get_competition

def normalize_team(api_name):
    """Normalizza nome squadra da API a nome KOZA usando il resolver centrale."""
    # Prova prima il mapping specifico per le API (nomi completi)
    if api_name in TEAM_NAME_MAPPING:
        return TEAM_NAME_MAPPING[api_name]
    
    # Usa il resolver centrale per alias generali (carica da data/team_aliases.json)
    resolved = _resolve_alias(api_name)
    if resolved != api_name:
        return resolved

    # Fallback: pulizia manuale se non trovato
    cleaned = api_name
    for suffix in [' FC', ' CF', ' SC', ' AC', ' BC', ' 1907', ' 1909', ' 1913']:
        cleaned = cleaned.replace(suffix, '')
    return cleaned.strip()


def fetch_matches(league_code, date_from, date_to, api_key=None):
    """
    Scarica le partite finite di una lega da football-data.org.

    Args:
        league_code: Codice lega (es: SA, PL, PD)
        date_from: Data inizio (YYYY-MM-DD)
        date_to: Data fine (YYYY-MM-DD)
        api_key: API key (opzionale, piano gratuito ha rate limit più basso)

    Returns:
        Lista di dict con i risultati
    """
    url = f"{BASE_URL}/competitions/{league_code}/matches"
    params = {
        'dateFrom': date_from,
        'dateTo': date_to,
        'status': 'FINISHED',
    }
    headers = {
        'X-Auth-Token': api_key or os.getenv('FOOTBALL_DATA_API_KEY', ''),
    }

    # Se non c'è API key, le richieste sono limitate ma funzionano
    if not headers['X-Auth-Token']:
        logger.warning(f"⚠️ Nessuna API key per football-data.org. Rate limit: 10/minuto")
        del headers['X-Auth-Token']

    try:
        logger.info(f"📡 Scaricando partite {league_code} ({date_from} → {date_to})...")
        response = requests.get(url, headers=headers, params=params, timeout=30)

        if response.status_code == 429:
            logger.warning("⏳ Rate limit raggiunto, attendo 60 secondi...")
            time.sleep(60)
            response = requests.get(url, headers=headers, params=params, timeout=30)

        if response.status_code != 200:
            logger.error(f"❌ Errore API ({response.status_code}): {response.text[:200]}")
            return []

        data = response.json()
        matches = data.get('matches', [])

        results = []
        for match in matches:
            home_team = match.get('homeTeam', {}).get('name', '')
            away_team = match.get('awayTeam', {}).get('name', '')
            score = match.get('score', {})
            full_time = score.get('fullTime', {})
            home_goals = full_time.get('home')
            away_goals = full_time.get('away')

            if home_goals is None or away_goals is None:
                continue

            # Determina risultato
            if home_goals > away_goals:
                ftr = 'H'
            elif home_goals < away_goals:
                ftr = 'A'
            else:
                ftr = 'D'

            # Normalizza nomi
            home_norm = normalize_team(home_team)
            away_norm = normalize_team(away_team)

            # Data del match
            utc_date = match.get('utcDate', '')
            match_date = ''
            if utc_date:
                try:
                    match_date = datetime.fromisoformat(utc_date.replace('Z', '+00:00')).strftime('%Y-%m-%d')
                except ValueError:
                    match_date = datetime.now().strftime('%Y-%m-%d')

            # Determina competizione (usa LEAGUES mapping o il DB centrale)
            competition = LEAGUES.get(league_code, {}).get('competition')
            if not competition:
                competition = get_competition(home_norm)
                if competition == "Unknown":
                    competition = "Unknown"

            results.append({
                'date': match_date,
                'home_team': home_norm,
                'away_team': away_norm,
                'fthg': home_goals,
                'ftag': away_goals,
                'ftr': ftr,
                'competition': competition,
            })

        logger.info(f"✅ {len(results)} partite trovate per {LEAGUES[league_code]['name']}")
        return results

    except requests.exceptions.Timeout:
        logger.error(f"⏱️ Timeout per {league_code}")
        return []
    except Exception as e:
        logger.error(f"❌ Errore fetch {league_code}: {e}")
        return []


def is_duplicate(match, csv_file):
    """Controlla se la partita è già presente nel CSV."""
    if not os.path.exists(csv_file):
        return False

    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rh = row.get('HomeTeam', '').strip().lower()
                ra = row.get('AwayTeam', '').strip().lower()
                rd = row.get('Date', '').strip()
                rhg = str(row.get('FTHG', '')).strip()
                rag = str(row.get('FTAG', '')).strip()

                mh = match['home_team'].lower()
                ma = match['away_team'].lower()
                md = match['date']
                mhg = str(match['fthg'])
                mag = str(match['ftag'])

                # Match su data + squadre
                if rd == md and rh == mh and ra == ma:
                    return True
                # Match su squadre + punteggio (date diverse ma stessa partita)
                if rh == mh and ra == ma and rhg == mhg and rag == mag:
                    return True
    except Exception:
        pass

    return False


def save_results(results, csv_file='parsed_matches.csv', dry_run=False):
    """
    Salva i risultati nel CSV, evitando duplicati.

    Args:
        results: Lista di dict con i risultati
        csv_file: Path al file CSV
        dry_run: Se True, mostra senza salvare

    Returns:
        Numero di partite salvate
    """
    saved = 0
    skipped = 0

    file_exists = os.path.exists(csv_file)

    # Controlla se il file ha la colonna Competition
    has_competition = False
    if file_exists:
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                header = f.readline().strip()
                has_competition = 'Competition' in header
        except Exception:
            pass

    for match in results:
        if is_duplicate(match, csv_file):
            skipped += 1
            continue

        if dry_run:
            logger.info(f"  📋 [DRY] {match['date']} | {match['home_team']} {match['fthg']}-{match['ftag']} {match['away_team']} ({match['ftr']}) [{match['competition']}]")
            saved += 1
            continue

        with open(csv_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(['Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTR', 'Competition'])
                file_exists = True
                has_competition = True

            row = [
                match['date'],
                match['home_team'],
                match['away_team'],
                match['fthg'],
                match['ftag'],
                match['ftr'],
            ]
            if has_competition:
                row.append(match['competition'])

            writer.writerow(row)
            saved += 1

        logger.info(f"  ✅ {match['date']} | {match['home_team']} {match['fthg']}-{match['ftag']} {match['away_team']} ({match['ftr']}) [{match['competition']}]")

    if skipped > 0:
        logger.info(f"  ⏭️ {skipped} partite saltate (già presenti)")

    return saved


def main():
    parser = argparse.ArgumentParser(
        description='🔄 Scarica risultati partite da football-data.org e salva in parsed_matches.csv',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Esempi:
  python scripts/scrape_results.py                      # Ultimi 3 giorni, tutte le leghe
  python scripts/scrape_results.py --days 7             # Ultima settimana
  python scripts/scrape_results.py --league SA          # Solo Serie A
  python scripts/scrape_results.py --league SA PL       # Serie A + Premier League
  python scripts/scrape_results.py --dry-run            # Anteprima senza salvare
  python scripts/scrape_results.py --output results.csv # CSV personalizzato
        """
    )
    parser.add_argument('--days', type=int, default=3,
                       help='Numero di giorni nel passato da scaricare (default: 3)')
    parser.add_argument('--league', nargs='+', default=None,
                       choices=list(LEAGUES.keys()),
                       help='Leghe da scaricare (default: tutte). Codici: SA PL PD BL1 FL1 CL')
    parser.add_argument('--output', type=str, default='parsed_matches.csv',
                       help='File CSV output (default: parsed_matches.csv)')
    parser.add_argument('--dry-run', action='store_true',
                       help='Mostra i risultati senza salvare')
    parser.add_argument('--api-key', type=str, default=None,
                       help='API key per football-data.org (opzionale)')

    args = parser.parse_args()

    # Date range
    date_to = datetime.now()
    date_from = date_to - timedelta(days=args.days)
    date_from_str = date_from.strftime('%Y-%m-%d')
    date_to_str = date_to.strftime('%Y-%m-%d')

    # Leghe da scaricare
    leagues_to_fetch = args.league if args.league else list(LEAGUES.keys())

    api_key = args.api_key or os.getenv('FOOTBALL_DATA_API_KEY', '')

    print(f"""
╔══════════════════════════════════════════════════════════╗
║  🔄 KOZA Auto-Scraper - Risultati Partite               ║
╠══════════════════════════════════════════════════════════╣
║  📅 Periodo: {date_from_str} → {date_to_str}              ║
║  ⚽ Leghe: {', '.join(leagues_to_fetch):<42} ║
║  📁 Output: {args.output:<42} ║
║  {'🔑 API Key: Configurata' if api_key else '⚠️  API Key: Non configurata (rate limit basso)':<52} ║
╚══════════════════════════════════════════════════════════╝
""")

    total_saved = 0
    total_fetched = 0

    for league_code in leagues_to_fetch:
        results = fetch_matches(league_code, date_from_str, date_to_str, api_key)
        total_fetched += len(results)

        if results:
            saved = save_results(results, args.output, args.dry_run)
            total_saved += saved

        # Rate limiting: attendi tra una lega e l'altra (solo con piano gratuito)
        if not api_key and league_code != leagues_to_fetch[-1]:
            logger.info("⏳ Attendo 7 secondi (rate limit)...")
            time.sleep(7)

    # Summary
    print(f"\n{'='*50}")
    print(f"📊 Riepilogo:")
    print(f"   Partite trovate: {total_fetched}")
    print(f"   Partite {'[DRY] da salvare' if args.dry_run else 'salvate'}: {total_saved}")
    print(f"   Partite duplicate: {total_fetched - total_saved}")
    if not args.dry_run and total_saved > 0:
        print(f"\n   ✅ Dati salvati in {args.output}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
