"""
Team Form Bridge - Recupera forma squadre da multiple fonti.
Priorità: 1. parsed_matches.csv (dati live dal gruppo Telegram)
           1.5. data/*.csv (dati storici reali da football-data.co.uk)
           2. API-Football (piano gratuito)
           3. Dati statici (fallback)
"""

import csv
import logging
import os
import glob
from typing import Optional, Dict, Any, List
from datetime import datetime
from rapidfuzz import fuzz

from src.engines.apifootball_engine import get_apifootball_engine
from src.utils.team_ratings import get_team_form as get_static_team_form, _resolve_alias

logger = logging.getLogger(__name__)

# Cache per evitare letture ripetute
_form_cache = {}
_cache_ttl = 1800  # 30 minuti

PARSED_MATCHES_FILE = 'parsed_matches.csv'
TRAINING_DATA_DIR = 'data'


def _find_team_in_parsed(team_name, csv_team):
    """Verifica se un nome squadra nel CSV corrisponde al team cercato (usando la normalizzazione KOZA)."""
    t1 = _resolve_alias(team_name).strip().lower()
    t2 = _resolve_alias(csv_team).strip().lower()
    if t1 == t2:
        return True
    if t1 in t2 or t2 in t1:
        return True
    if fuzz.ratio(t1, t2) > 80:
        return True
    return False


def get_form_from_parsed_matches(team_name, last_n=5, competition=None):
    """
    Cerca le ultime N partite di una squadra in parsed_matches.csv.
    Questi sono dati REALI della stagione corrente, inseriti dall'utente.
    Se competition è specificata, filtra per quella competizione (fallback: tutte).

    Returns:
        dict con forma o None se non trovata
    """
    if not os.path.exists(PARSED_MATCHES_FILE):
        return None

    try:
        matches = []
        with open(PARSED_MATCHES_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                home = row.get('HomeTeam', '').strip()
                away = row.get('AwayTeam', '').strip()

                if not home or not away:
                    continue

                # Salta righe corrotte (nomi con newline)
                if '\n' in home or '\n' in away or '\r' in home or '\r' in away:
                    continue

                is_home = _find_team_in_parsed(team_name, home)
                is_away = _find_team_in_parsed(team_name, away)

                if not is_home and not is_away:
                    continue

                try:
                    fthg = int(row.get('FTHG', 0))
                    ftag = int(row.get('FTAG', 0))
                except (ValueError, TypeError):
                    continue

                date = row.get('Date', '')

                if is_home:
                    gf, ga = fthg, ftag
                    opponent = away
                    venue = 'home'
                else:
                    gf, ga = ftag, fthg
                    opponent = home
                    venue = 'away'

                if gf > ga:
                    result = 'W'
                elif gf < ga:
                    result = 'L'
                else:
                    result = 'D'

                match_competition = row.get('Competition', '').strip()

                matches.append({
                    'date': date,
                    'opponent': opponent,
                    'result': result,
                    'goals_for': gf,
                    'goals_against': ga,
                    'score': f"{fthg}-{ftag}",
                    'venue': venue,
                    'competition': match_competition,
                })

        if not matches:
            return None

        # Ordina per data decrescente
        matches.sort(key=lambda m: m.get('date', ''), reverse=True)

        # Filtra per competizione se specificata (fallback: tutte le partite)
        if competition:
            comp_lower = competition.lower()
            filtered = [m for m in matches if m.get('competition', '').lower() == comp_lower]
            if len(filtered) >= 2:
                matches = filtered

        matches = matches[:last_n]

        if not matches:
            return None

        form_str = "".join(m['result'] for m in matches)
        wins = sum(1 for m in matches if m['result'] == 'W')
        draws = sum(1 for m in matches if m['result'] == 'D')
        losses = sum(1 for m in matches if m['result'] == 'L')
        gf = sum(m['goals_for'] for m in matches)
        ga = sum(m['goals_against'] for m in matches)

        logger.info(f"Forma LIVE per {team_name}: {form_str} ({wins}V-{draws}P-{losses}S) da parsed_matches ({len(matches)} partite)")

        return {
            'form': form_str,
            'wins': wins,
            'draws': draws,
            'losses': losses,
            'goals_for': gf,
            'goals_against': ga,
            'source': 'telegram_live',
            'matches': matches
        }

    except Exception as e:
        logger.error(f"Errore lettura parsed_matches per {team_name}: {e}")
        return None


def get_form_from_training_data(team_name, last_n=5, competition=None):
    """
    Cerca le ultime N partite di una squadra nei CSV di training (data/*.csv).
    Questi sono dati REALI completi della stagione corrente (football-data.co.uk).
    Se competition è specificata, filtra per quella competizione (fallback: tutte).

    I file seguono il formato: Div,Date,Time,HomeTeam,AwayTeam,FTHG,FTAG,FTR,...
    Date è in formato DD/MM/YYYY.

    Returns:
        dict con forma o None se non trovata
    """
    if not os.path.isdir(TRAINING_DATA_DIR):
        return None

    # Trova tutti i CSV nella cartella data/
    csv_files = glob.glob(os.path.join(TRAINING_DATA_DIR, '*.csv'))
    if not csv_files:
        return None

    # Risolvi alias per il nome squadra
    resolved_name = _resolve_alias(team_name)

    all_matches = []

    for csv_file in csv_files:
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    home = row.get('HomeTeam', '').strip()
                    away = row.get('AwayTeam', '').strip()

                    if not home or not away:
                        continue

                    # Cerca corrispondenza con il nome squadra (o alias)
                    is_home = _find_team_in_training(team_name, resolved_name, home)
                    is_away = _find_team_in_training(team_name, resolved_name, away)

                    if not is_home and not is_away:
                        continue

                    try:
                        fthg = int(row.get('FTHG', 0))
                        ftag = int(row.get('FTAG', 0))
                    except (ValueError, TypeError):
                        continue

                    # Parsa la data (formato DD/MM/YYYY)
                    date_str = row.get('Date', '')
                    parsed_date = ''
                    if date_str:
                        try:
                            parsed_date = datetime.strptime(date_str, '%d/%m/%Y').strftime('%Y-%m-%d')
                        except ValueError:
                            parsed_date = date_str  # Fallback

                    if is_home:
                        gf, ga = fthg, ftag
                        opponent = away
                        venue = 'home'
                    else:
                        gf, ga = ftag, fthg
                        opponent = home
                        venue = 'away'

                    if gf > ga:
                        result = 'W'
                    elif gf < ga:
                        result = 'L'
                    else:
                        result = 'D'

                    # Estrai statistiche extra se disponibili
                    shots = int(row.get('HS' if is_home else 'AS', 0) or 0)
                    shots_target = int(row.get('HST' if is_home else 'AST', 0) or 0)

                    # Determina la lega dal campo Div
                    div = row.get('Div', '')
                    league = _div_to_league(div)

                    all_matches.append({
                        'date': parsed_date,
                        'opponent': opponent,
                        'result': result,
                        'goals_for': gf,
                        'goals_against': ga,
                        'score': f"{fthg}-{ftag}",
                        'venue': venue,
                        'shots': shots,
                        'shots_on_target': shots_target,
                        'league': league,
                    })

        except Exception as e:
            logger.warning(f"Errore lettura training CSV {csv_file}: {e}")
            continue

    if not all_matches:
        return None

    # Ordina per data decrescente
    all_matches.sort(key=lambda m: m.get('date', ''), reverse=True)

    # Filtra per competizione se specificata (fallback: tutte le partite)
    if competition:
        comp_lower = competition.lower()
        filtered = [m for m in all_matches if m.get('league', '').lower() == comp_lower]
        if len(filtered) >= 2:
            all_matches = filtered

    matches = all_matches[:last_n]

    if not matches:
        return None

    form_str = "".join(m['result'] for m in matches)
    wins = sum(1 for m in matches if m['result'] == 'W')
    draws = sum(1 for m in matches if m['result'] == 'D')
    losses = sum(1 for m in matches if m['result'] == 'L')
    gf = sum(m['goals_for'] for m in matches)
    ga = sum(m['goals_against'] for m in matches)

    logger.info(f"Forma TRAINING per {team_name}: {form_str} ({wins}V-{draws}P-{losses}S) da dati storici ({len(matches)} partite)")

    return {
        'form': form_str,
        'wins': wins,
        'draws': draws,
        'losses': losses,
        'goals_for': gf,
        'goals_against': ga,
        'source': 'training_data',
        'matches': matches
    }


def _find_team_in_training(team_name, resolved_name, csv_team):
    """
    Verifica se un nome squadra nel CSV di training corrisponde al team cercato.
    Supporta match esatto, parziale e fuzzy.
    """
    t_csv = csv_team.strip().lower()
    t_search = team_name.strip().lower()
    t_resolved = resolved_name.strip().lower()

    # Match esatto
    if t_csv == t_search or t_csv == t_resolved:
        return True

    # Match parziale (per nomi come "Inter" in "FC Internazionale")
    if t_search in t_csv or t_csv in t_search:
        return True
    if t_resolved in t_csv or t_csv in t_resolved:
        return True

    # Fuzzy match
    if fuzz.ratio(t_csv, t_search) > 80 or fuzz.ratio(t_csv, t_resolved) > 80:
        return True

    return False


def _div_to_league(div_code):
    """Converte codice divisione (es: I1, E0) in nome lega leggibile."""
    mapping = {
        'I1': 'Serie A',
        'I2': 'Serie B',
        'E0': 'Premier League',
        'E1': 'Championship',
        'SP1': 'La Liga',
        'SP2': 'La Liga 2',
        'D1': 'Bundesliga',
        'D2': '2. Bundesliga',
        'F1': 'Ligue 1',
        'F2': 'Ligue 2',
    }
    return mapping.get(div_code, div_code)


def get_team_form(team_name: str, use_real_data: bool = True) -> str:
    """Recupera la forma di una squadra (es: 'WWDLW')."""
    if not use_real_data:
        return get_static_team_form(team_name)

    details = get_team_form_with_details(team_name, use_real_data=True)
    return details.get('form', get_static_team_form(team_name))


def get_team_form_with_details(team_name: str, use_real_data: bool = True, competition: str = None) -> Dict[str, Any]:
    """
    Recupera forma dettagliata.
    Priorità: 1. parsed_matches.csv
              1.5. data/*.csv (training data)
              2. API-Football
              3. statico
    """
    # Default: forma statica
    static_form = get_static_team_form(team_name)
    result = {
        'form': static_form,
        'wins': static_form.count('W'),
        'draws': static_form.count('D'),
        'losses': static_form.count('L'),
        'goals_for': 0,
        'goals_against': 0,
        'source': 'static',
        'matches': []
    }

    if not use_real_data:
        return result

    # Check cache
    cache_key = f"form_{team_name.lower().strip()}_{(competition or '').lower()}"
    if cache_key in _form_cache:
        cached_time, cached_data = _form_cache[cache_key]
        if (datetime.now() - cached_time).seconds < _cache_ttl:
            return cached_data

    # Risolvi alias (es: "Bayern München" -> "Bayern Monaco")
    resolved_name = _resolve_alias(team_name)

    # PRIORITÀ 1: parsed_matches.csv (dati live stagione corrente)
    live_form = get_form_from_parsed_matches(team_name, competition=competition) or get_form_from_parsed_matches(resolved_name, competition=competition)
    if live_form:
        _form_cache[cache_key] = (datetime.now(), live_form)
        return live_form

    # PRIORITÀ 1.5: data/*.csv (dati storici reali da football-data.co.uk)
    training_form = get_form_from_training_data(team_name, competition=competition) or get_form_from_training_data(resolved_name, competition=competition)
    if training_form:
        _form_cache[cache_key] = (datetime.now(), training_form)
        return training_form

    # PRIORITÀ 2: API-Football (piano gratuito)
    try:
        apifootball = get_apifootball_engine()
        if apifootball.api_key:
            team_id = apifootball.search_team_id(team_name) or apifootball.search_team_id(resolved_name)
            if team_id:
                matches = apifootball.get_team_last_matches(team_id, last_n=5)
                if matches:
                    form_str = "".join(m['result'] for m in matches)
                    wins = sum(1 for m in matches if m['result'] == 'W')
                    draws = sum(1 for m in matches if m['result'] == 'D')
                    losses = sum(1 for m in matches if m['result'] == 'L')
                    gf = sum(m['goals_for'] for m in matches)
                    ga = sum(m['goals_against'] for m in matches)

                    result = {
                        'form': form_str,
                        'wins': wins, 'draws': draws, 'losses': losses,
                        'goals_for': gf, 'goals_against': ga,
                        'source': 'apifootball',
                        'matches': matches
                    }
                    _form_cache[cache_key] = (datetime.now(), result)
                    logger.info(f"Forma per {team_name}: {form_str} da API-Football")
                    return result

    except Exception as e:
        logger.error(f"Errore API-Football per {team_name}: {e}")

    # PRIORITÀ 3: statico
    _form_cache[cache_key] = (datetime.now(), result)
    return result


_h2h_cache = {}
_h2h_cache_ttl = 3600  # 1 ora (dati storici cambiano raramente)


def get_head_to_head(team1: str, team2: str) -> Optional[Dict[str, Any]]:
    """
    Recupera storico scontri diretti tra due squadre.
    Prima cerca nei dati di training locali, poi via API-Football.
    Ritorna gli ultimi 20 match con cache di 1 ora.
    """
    # Check cache
    cache_key = f"h2h_{sorted([team1.lower().strip(), team2.lower().strip()])}"
    if cache_key in _h2h_cache:
        cached_time, cached_data = _h2h_cache[cache_key]
        if (datetime.now() - cached_time).seconds < _h2h_cache_ttl:
            logger.info(f"H2H {team1} vs {team2}: da cache")
            return cached_data

    # Prima prova con dati di training locali
    h2h_local = _get_h2h_from_training(team1, team2)
    if h2h_local and h2h_local.get('total_matches', 0) > 0:
        _h2h_cache[cache_key] = (datetime.now(), h2h_local)
        logger.info(f"H2H {team1} vs {team2}: {h2h_local['total_matches']} partite da dati locali")
        return h2h_local

    try:
        apifootball = get_apifootball_engine()
        if not apifootball.api_key:
            return h2h_local  # Ritorna dati locali anche se pochi

        # Risolvi nomi e cerca ID
        resolved1 = _resolve_alias(team1)
        resolved2 = _resolve_alias(team2)

        id1 = apifootball.search_team_id(team1) or apifootball.search_team_id(resolved1)
        id2 = apifootball.search_team_id(team2) or apifootball.search_team_id(resolved2)

        if not id1 or not id2:
            logger.warning(f"H2H: ID non trovato per {team1} ({id1}) o {team2} ({id2})")
            return h2h_local

        from src.core.config import HEAD_TO_HEAD_MATCHES
        h2h = apifootball.get_head_to_head(id1, id2, last_n=HEAD_TO_HEAD_MATCHES)

        if h2h:
            _h2h_cache[cache_key] = (datetime.now(), h2h)
            logger.info(f"H2H {team1} vs {team2}: {h2h['total_matches']} partite trovate")

        return h2h

    except Exception as e:
        logger.error(f"Errore H2H {team1} vs {team2}: {e}")
        return h2h_local


def _get_h2h_from_training(team1: str, team2: str) -> Optional[Dict[str, Any]]:
    """Cerca scontri diretti nei dati di training locali."""
    if not os.path.isdir(TRAINING_DATA_DIR):
        return None

    csv_files = glob.glob(os.path.join(TRAINING_DATA_DIR, '*.csv'))
    if not csv_files:
        return None

    resolved1 = _resolve_alias(team1)
    resolved2 = _resolve_alias(team2)

    matches = []

    for csv_file in csv_files:
        try:
            with open(csv_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    home = row.get('HomeTeam', '').strip()
                    away = row.get('AwayTeam', '').strip()

                    if not home or not away:
                        continue

                    t1_is_home = _find_team_in_training(team1, resolved1, home)
                    t1_is_away = _find_team_in_training(team1, resolved1, away)
                    t2_is_home = _find_team_in_training(team2, resolved2, home)
                    t2_is_away = _find_team_in_training(team2, resolved2, away)

                    if (t1_is_home and t2_is_away) or (t1_is_away and t2_is_home):
                        try:
                            fthg = int(row.get('FTHG', 0))
                            ftag = int(row.get('FTAG', 0))
                        except (ValueError, TypeError):
                            continue

                        date_str = row.get('Date', '')
                        parsed_date = ''
                        if date_str:
                            try:
                                parsed_date = datetime.strptime(date_str, '%d/%m/%Y').strftime('%Y-%m-%d')
                            except ValueError:
                                parsed_date = date_str

                        ftr = row.get('FTR', 'D')
                        if ftr == 'H':
                            result_desc = f"Vittoria {home}"
                        elif ftr == 'A':
                            result_desc = f"Vittoria {away}"
                        else:
                            result_desc = "Pareggio"

                        matches.append({
                            'date': parsed_date,
                            'score': f"{fthg}-{ftag}",
                            'result': result_desc,
                            'home': home,
                            'away': away,
                        })
        except Exception:
            continue

    if not matches:
        return None

    matches.sort(key=lambda m: m.get('date', ''), reverse=True)

    team1_wins = 0
    team2_wins = 0
    draws = 0

    for m in matches:
        if "Pareggio" in m['result']:
            draws += 1
        elif any(_find_team_in_training(team1, resolved1, w) for w in [m.get('home', ''), m.get('away', '')] if m['result'].endswith(w)):
            team1_wins += 1
        else:
            team2_wins += 1

    return {
        'total_matches': len(matches),
        'team1_wins': team1_wins,
        'team2_wins': team2_wins,
        'draws': draws,
        'matches': matches[:10],  # Solo ultimi 10
    }


def format_team_form(team_name: str, use_real_data: bool = True) -> str:
    """Formatta la forma squadre per display."""
    details = get_team_form_with_details(team_name, use_real_data)
    form = details['form']
    w, d, l = details['wins'], details['draws'], details['losses']
    gf = details.get('goals_for', 0)
    ga = details.get('goals_against', 0)
    source = details['source']
    if source in ('telegram_live', 'apifootball', 'training_data') and (gf or ga):
        return f"{form} ({w}V-{d}P-{l}S, {gf}GF-{ga}GS)"
    return f"{form} ({w}V-{d}P-{l}S)"


def clear_cache():
    """Pulisce la cache delle forme squadre"""
    global _form_cache
    _form_cache = {}
    logger.info("Team form cache cleared")
