"""
API-Football Engine per KOZA Bot
Gestisce le chiamate all'API Football (api-sports.io) per dati calcistici reali
"""

import os
import json
import logging
import requests
from datetime import datetime, timedelta
from rapidfuzz import fuzz

from src.core.config import LEGHE_PRINCIPALI_APIFOOTBALL

logger = logging.getLogger(__name__)

APIFOOTBALL_BASE_URL = "https://v3.football.api-sports.io"

# Mappatura ID leghe API-Football
LEGA_IDS_APIFOOTBALL = {
    "Serie A": 135,
    "Premier League": 39,
    "La Liga": 140,
    "Bundesliga": 78,
    "Ligue 1": 61,
    "Champions League": 2,
    "Europa League": 3,
    "Conference League": 848,
    "World Cup": 1,
    "World Cup Qualifiers Europe": 29,
    "World Cup Qualifiers Africa": 32,
    "World Cup Qualifiers Asia": 30,
    "World Cup Qualifiers CONCACAF": 31,
    "World Cup Qualifiers South America": 28,
    "Euro Championship": 4,
    "Euro Qualifiers": 960,
    "UEFA Nations League": 5,
    "AFC Asian Cup": 16,
    "Copa America": 9,
    "Africa Cup of Nations": 6,
}


class APIFootballEngine:
    """Motore per dati calcistici reali da API-Football."""

    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("APIFOOTBALL_API_KEY", "")
        self.base_url = APIFOOTBALL_BASE_URL
        self.session = requests.Session()
        self.session.headers.update({
            "x-rapidapi-key": self.api_key,
            "x-rapidapi-host": "v3.football.api-sports.io"
        })

    def _make_request(self, endpoint, params=None):
        """Effettua una richiesta GET all'API."""
        url = f"{self.base_url}/{endpoint}"
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            # Log rate limit info se disponibile
            if "x-ratelimit-requests-remaining" in response.headers:
                remaining = response.headers.get("x-ratelimit-requests-remaining")
                logger.info(f"API-Football rate limit remaining: {remaining}")
            
            return data
        except requests.exceptions.RequestException as e:
            logger.error(f"Errore richiesta API-Football: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Errore parsing JSON: {e}")
            return None

    def get_partite_del_giorno(self, data=None, timezone="Europe/Rome"):
        """
        Recupera partite del giorno specificato.
        Endpoint: /fixtures
        """
        if data is None:
            data = datetime.now().date()

        data_str = data.strftime("%Y-%m-%d")
        logger.info(f"=== API-FOOTBALL === Cerco partite per {data_str}")
        logger.info(f"API Key presente: {bool(self.api_key)} (lunghezza: {len(self.api_key)})")

        result = self._make_request("fixtures", {
            "date": data_str,
            "timezone": timezone
        })

        if not result:
            logger.error("API-Football: risultato None - possibile errore di connessione o API key")
            return {"competizioni": []}
            
        if "response" not in result:
            logger.error(f"API-Football: campo 'response' mancante. Risultato: {result}")
            return {"competizioni": []}
        
        # Log risposta completa per debug
        logger.info(f"API-Football: risposta ricevuta, tipo: {type(result)}")
        logger.info(f"API-Football: chiavi nella risposta: {list(result.keys())}")
        if result.get("errors"):
            logger.error(f"API-Football errori: {result.get('errors')}")

        fixtures = result.get("response", [])
        logger.info(f"API-Football: trovate {len(fixtures)} partite totali")
        
        # Log prima partita per debug (se presente)
        if fixtures:
            sample = fixtures[0]
            lega_info = sample.get("league", {})
            teams_info = sample.get("teams", {})
            logger.info(f"Esempio partita: {teams_info.get('home',{}).get('name')} vs {teams_info.get('away',{}).get('name')} - Lega ID: {lega_info.get('id')} ({lega_info.get('name')})")

        # Organizza per competizione (SOLO leghe principali)
        competizioni = {}
        scartate = 0
        for fixture in fixtures:
            lega = fixture.get("league", {})
            lega_id = str(lega.get("id", 0))
            lega_nome = lega.get("name", "Unknown")
            
            teams = fixture.get("teams", {})
            home = teams.get("home", {}).get("name", "?")
            away = teams.get("away", {}).get("name", "?")
            
            # FILTRO: Mostra solo competizioni in whitelist
            if lega_id not in LEGHE_PRINCIPALI_APIFOOTBALL:
                logger.info(f"FILTRO API-Football: Partita '{home} vs {away}' scartata - ID lega '{lega_id}' ('{lega_nome}') non in whitelist")
                scartate += 1
                continue
            
            nome_visualizzato = LEGHE_PRINCIPALI_APIFOOTBALL.get(lega_id, lega_nome)

            if lega_id not in competizioni:
                competizioni[lega_id] = {
                    "id": lega_id,
                    "nome": nome_visualizzato,
                    "partite": []
                }

            teams = fixture.get("teams", {})
            fixture_data = {
                "id": fixture.get("fixture", {}).get("id"),
                "casa": teams.get("home", {}).get("name"),
                "trasferta": teams.get("away", {}).get("name"),
                "data": fixture.get("fixture", {}).get("date"),
                "stadio": fixture.get("fixture", {}).get("venue", {}).get("name"),
                "round": fixture.get("league", {}).get("round"),
                "api_source": "apifootball"  # Tag per deduplica
            }
            
            competizioni[lega_id]["partite"].append(fixture_data)
        
        # Log competizioni trovate
        for comp_id, comp_data in competizioni.items():
            logger.info(f"✓ API-Football - {comp_data['nome']}: {len(comp_data['partite'])} partite")
        
        return {"competizioni": list(competizioni.values())}

    def get_partite_per_lega(self, lega_id, data=None, season=None, timezone="Europe/Rome"):
        """
        Recupera partite per una specifica lega.
        """
        if data is None:
            data = datetime.now().date()

        data_str = data.strftime("%Y-%m-%d")
        
        # API-Football usa ID numerici
        api_lega_id = self._convert_lega_id_to_api(lega_id)
        
        # Per date specifiche, non usare filtro season (causa problemi con playoff)
        # I playoff mondiali 2026 usano season 2024
        params = {
            "league": api_lega_id,
            "date": data_str,
            "timezone": timezone
        }
        
        # Se è World Cup Qualifiers (ID 32), usa season 2024
        if api_lega_id == 32:
            params["season"] = 2024
        
        result = self._make_request("fixtures", params)

        if not result or "response" not in result:
            return []

        fixtures = result.get("response", [])
        partite = []

        for fixture in fixtures:
            teams = fixture.get("teams", {})
            partite.append({
                "id": fixture.get("fixture", {}).get("id"),
                "casa": teams.get("home", {}).get("name"),
                "trasferta": teams.get("away", {}).get("name"),
                "data": fixture.get("fixture", {}).get("date"),
                "stadio": fixture.get("fixture", {}).get("venue", {}).get("name"),
                "round": fixture.get("league", {}).get("round"),
                "api_source": "apifootball"
            })

        logger.info(f"API-Football - Lega {lega_id}: {len(partite)} partite trovate")
        return partite

    def _convert_lega_id_to_api(self, lega_id):
        """Converte ID lega generico in ID API-Football numerico."""
        # Se è già numerico, usa diretto
        if isinstance(lega_id, int) or (isinstance(lega_id, str) and lega_id.isdigit()):
            return int(lega_id)
        
        # Mappa da nome a ID
        return LEGA_IDS_APIFOOTBALL.get(lega_id, 0)

    def get_info_squadra(self, nome_squadra):
        """
        Recupera informazioni su una squadra.
        Endpoint: /teams
        """
        result = self._make_request("teams", {"search": nome_squadra})

        if not result or "response" not in result:
            return None

        teams = result.get("response", [])
        if not teams:
            return None

        team = teams[0]  # Prendi il primo risultato
        team_data = team.get("team", {})
        venue_data = team.get("venue", {})
        
        return {
            "id": team_data.get("id"),
            "nome": team_data.get("name"),
            "alternativi": [],  # API-Football non fornisce nomi alternativi
            "paese": team_data.get("country"),
            "fondazione": team_data.get("founded"),
            "logo": team_data.get("logo"),
            "stadio": venue_data.get("name"),
            "città": venue_data.get("city")
        }

    def get_dettaglio_partita(self, match_id):
        """
        Recupera dettagli di una partita specifica.
        Endpoint: /fixtures?id={match_id}
        """
        result = self._make_request("fixtures", {"id": match_id})

        if not result or "response" not in result or not result["response"]:
            return None

        fixture = result["response"][0]
        teams = fixture.get("teams", {})
        goals = fixture.get("goals", {})
        league = fixture.get("league", {})
        
        return {
            "id": fixture.get("fixture", {}).get("id"),
            "casa": teams.get("home", {}).get("name"),
            "trasferta": teams.get("away", {}).get("name"),
            "data": fixture.get("fixture", {}).get("date"),
            "stadio": fixture.get("fixture", {}).get("venue", {}).get("name"),
            "lega": league.get("name"),
            "round": league.get("round"),
            "risultato": f"{goals.get('home', '-')}-{goals.get('away', '-')}",
            "api_source": "apifootball"
        }

    def get_live_fixtures(self, timezone="Europe/Rome"):
        """
        Recupera partite live.
        Endpoint: /fixtures?live=all
        """
        result = self._make_request("fixtures", {
            "live": "all",
            "timezone": timezone
        })

        if not result or "response" not in result:
            return []

        fixtures = result.get("response", [])
        partite = []

        for fixture in fixtures:
            teams = fixture.get("teams", {})
            goals = fixture.get("goals", {})
            league = fixture.get("league", {})
            
            lega_id = str(league.get("id", 0))
            if lega_id not in LEGHE_PRINCIPALI_APIFOOTBALL:
                continue
            
            partite.append({
                "id": fixture.get("fixture", {}).get("id"),
                "casa": teams.get("home", {}).get("name"),
                "trasferta": teams.get("away", {}).get("name"),
                "risultato": f"{goals.get('home', 0)}-{goals.get('away', 0)}",
                "tempo": fixture.get("fixture", {}).get("status", {}).get("elapsed"),
                "lega": league.get("name"),
                "api_source": "apifootball"
            })

        return partite

    def get_match_status(self, match_id):
        """
        Recupera lo stato attuale di una partita.
        Ritorna: dict con status, risultato, tempo, etc.
        """
        result = self._make_request("fixtures", {"id": match_id})
        
        if not result or "response" not in result or not result["response"]:
            return None
        
        fixture = result["response"][0]
        fixture_data = fixture.get("fixture", {})
        status = fixture_data.get("status", {})
        teams = fixture.get("teams", {})
        goals = fixture.get("goals", {})
        
        return {
            "id": match_id,
            "casa": teams.get("home", {}).get("name"),
            "trasferta": teams.get("away", {}).get("name"),
            "status_short": status.get("short"),  # FT, AET, PEN, LIVE, 1H, 2H, HT, NS
            "status_long": status.get("long"),   # Finished, Live, First Half, etc.
            "tempo": status.get("elapsed"),       # Minuto corrente
            "risultato": f"{goals.get('home', 0)}-{goals.get('away', 0)}",
            "timestamp": fixture_data.get("timestamp")
        }
    
    def get_live_statistics(self, match_id):
        """
        Recupera statistiche live di una partita.
        Endpoint: /fixtures/statistics?fixture={match_id}
        """
        result = self._make_request("fixtures/statistics", {"fixture": match_id})
        
        if not result or "response" not in result:
            return None
        
        stats = result.get("response", [])
        if not stats:
            return None
        
        # Organizza statistiche per squadra
        stats_dict = {}
        for team_stats in stats:
            team = team_stats.get("team", {})
            team_name = team.get("name", "Squadra")
            team_id = team.get("id")
            
            statistics = {}
            for stat in team_stats.get("statistics", []):
                stat_type = stat.get("type")
                stat_value = stat.get("value")
                if stat_type:
                    statistics[stat_type] = stat_value
            
            stats_dict[team_name] = {
                "id": team_id,
                "stats": statistics
            }
        
        return stats_dict
    
    def is_match_finished(self, match_id):
        """Controlla se una partita è terminata."""
        status = self.get_match_status(match_id)
        if not status:
            return None
        return status.get("status_short") in ["FT", "AET", "PEN", "AWD", "WO"]
    
    def is_match_live(self, match_id):
        """Controlla se una partita è in corso."""
        status = self.get_match_status(match_id)
        if not status:
            return None
        return status.get("status_short") in ["LIVE", "1H", "2H", "HT", "ET", "PEN_LIVE", "INT"]

    def cerca_partita_per_squadre(self, squadra_casa, squadra_trasferta, data=None):
        """
        Cerca una partita su API-Football per nome squadre.
        Ritorna il fixture completo con id, status, risultato, etc.
        Utile quando il match_id originale non e' di API-Football.
        """
        if data is None:
            data = datetime.now().date()

        data_str = data.strftime("%Y-%m-%d")
        result = self._make_request("fixtures", {
            "date": data_str,
            "timezone": "Europe/Rome"
        })

        if not result or "response" not in result:
            return None

        fixtures = result.get("response", [])
        casa_lower = squadra_casa.lower()
        trasf_lower = squadra_trasferta.lower()

        best_match = None
        best_score = 0

        for fixture in fixtures:
            teams = fixture.get("teams", {})
            home_name = teams.get("home", {}).get("name", "")
            away_name = teams.get("away", {}).get("name", "")

            # Match fuzzy sui nomi squadra
            score_home = fuzz.ratio(casa_lower, home_name.lower())
            score_away = fuzz.ratio(trasf_lower, away_name.lower())

            # Prova anche match parziale
            score_home = max(score_home, fuzz.partial_ratio(casa_lower, home_name.lower()))
            score_away = max(score_away, fuzz.partial_ratio(trasf_lower, away_name.lower()))

            combined = (score_home + score_away) / 2

            if combined > best_score and combined >= 80:
                best_score = combined
                best_match = fixture

        if not best_match:
            logger.info(f"API-Football: nessun match trovato per {squadra_casa} vs {squadra_trasferta}")
            return None

        fixture_data = best_match.get("fixture", {})
        status = fixture_data.get("status", {})
        teams = best_match.get("teams", {})
        goals = best_match.get("goals", {})

        logger.info(f"API-Football: trovato match {teams.get('home',{}).get('name')} vs {teams.get('away',{}).get('name')} (score={best_score:.0f})")

        return {
            "fixture_id": fixture_data.get("id"),
            "casa": teams.get("home", {}).get("name"),
            "trasferta": teams.get("away", {}).get("name"),
            "status_short": status.get("short"),
            "status_long": status.get("long"),
            "tempo": status.get("elapsed"),
            "risultato": f"{goals.get('home', 0)}-{goals.get('away', 0)}",
            "timestamp": fixture_data.get("timestamp"),
        }

    def get_standings(self, league_id, season=None):
        """
        Recupera la classifica di una lega.
        Ritorna lista di dict con 'team' e 'rank'.
        """
        if not season:
            season = datetime.now().year

        data = self._make_request("standings", params={
            "league": league_id,
            "season": season,
        })

        if not data or "response" not in data:
            # Prova con anno precedente (stagione a cavallo)
            if not season or season == datetime.now().year:
                data = self._make_request("standings", params={
                    "league": league_id,
                    "season": datetime.now().year - 1,
                })

        if not data or "response" not in data:
            return None

        results = []
        for resp in data["response"]:
            league_data = resp.get("league", {})
            standings_groups = league_data.get("standings", [])
            for group in standings_groups:
                for entry in group:
                    results.append({
                        "team": {
                            "name": entry.get("team", {}).get("name", ""),
                            "id": entry.get("team", {}).get("id"),
                        },
                        "rank": entry.get("rank", 0),
                        "points": entry.get("points", 0),
                        "played": entry.get("all", {}).get("played", 0),
                    })

        return results if results else None

    # Mapping nomi comuni -> ID API-Football (evita problemi di ricerca)
    TEAM_ID_MAP = {
        # Serie A
        "inter": 505, "inter milan": 505, "internazionale": 505,
        "milan": 489, "ac milan": 489,
        "juventus": 496, "juve": 496,
        "napoli": 492, "ssc napoli": 492,
        "roma": 497, "as roma": 497,
        "lazio": 487, "ss lazio": 487,
        "fiorentina": 502, "acf fiorentina": 502,
        "atalanta": 499,
        "bologna": 500, "bologna fc": 500,
        "torino": 503, "torino fc": 503,
        "monza": 1579, "ac monza": 1579,
        "genoa": 495, "genoa cfc": 495,
        "udinese": 494,
        "empoli": 511,
        "lecce": 867, "us lecce": 867,
        "cagliari": 490,
        "verona": 504, "hellas verona": 504,
        "como": 895, "como 1907": 895,
        "parma": 498, "parma calcio": 498,
        "venezia": 517, "venezia fc": 517,
        "cremonese": 515, "us cremonese": 515,
        # Premier League
        "manchester city": 50, "man city": 50,
        "manchester united": 33, "man utd": 33, "man united": 33,
        "liverpool": 40,
        "arsenal": 42,
        "chelsea": 49,
        "tottenham": 47, "spurs": 47,
        "newcastle": 34, "newcastle united": 34,
        "aston villa": 66,
        "brighton": 51,
        "west ham": 48,
        # La Liga
        "real madrid": 541,
        "barcelona": 529, "barca": 529,
        "atletico madrid": 530, "atletico": 530,
        "sevilla": 536,
        "real sociedad": 548,
        "villarreal": 533,
        "real betis": 543, "betis": 543,
        "athletic bilbao": 531, "athletic club": 531,
        "valencia": 532,
        # Bundesliga
        "bayern munich": 157, "bayern": 157, "bayern monaco": 157,
        "borussia dortmund": 165, "dortmund": 165,
        "rb leipzig": 173, "leipzig": 173,
        "bayer leverkusen": 168, "leverkusen": 168,
        # Ligue 1
        "psg": 85, "paris saint-germain": 85, "paris sg": 85,
        "marseille": 81, "olympique marsiglia": 81,
        "lyon": 80, "olympique lione": 80,
        "monaco": 91, "as monaco": 91,
        # Portoghesi
        "sporting cp": 228, "sporting": 228, "sporting lisbon": 228, "sporting lisbona": 228,
        "benfica": 211, "sl benfica": 211,
        "porto": 212, "fc porto": 212,
        "braga": 217, "sc braga": 217,
        # Olandesi
        "ajax": 194,
        "psv": 197, "psv eindhoven": 197,
        "feyenoord": 215,
        # Altre europee
        "celtic": 247,
        "rangers": 257,
        "galatasaray": 645,
        "fenerbahce": 611,
        "besiktas": 549,
    }

    def search_team_id(self, team_name):
        """
        Cerca l'ID di una squadra su API-Football.
        Prima controlla mapping locale, poi cerca via API con filtro paese.
        """
        # 1. Check mapping locale (veloce, no API call)
        key = team_name.strip().lower()
        if key in self.TEAM_ID_MAP:
            team_id = self.TEAM_ID_MAP[key]
            logger.info(f"Team '{team_name}' trovato in mapping locale: ID {team_id}")
            return team_id

        # 2. Cerca via API
        data = self._make_request("teams", params={"search": team_name})
        if not data or "response" not in data:
            return None

        results = data["response"]
        if not results:
            return None

        # Preferisci squadre di paesi europei principali (non donne, non giovani)
        preferred_countries = {"Italy", "England", "Spain", "Germany", "France",
                               "Portugal", "Netherlands", "Belgium", "Turkey"}

        for team_data in results:
            team = team_data.get("team", {})
            country = team_data.get("team", {}).get("country", "")
            name = team.get("name", "")
            # Salta squadre femminili e giovanili
            if any(tag in name for tag in ["W", "Women", "U19", "U21", "U23", "II"]):
                continue
            if country in preferred_countries:
                logger.info(f"Team '{team_name}' trovato via API: {name} (ID {team['id']}, {country})")
                return team["id"]

        # Fallback: primo risultato non-femminile
        for team_data in results:
            team = team_data.get("team", {})
            name = team.get("name", "")
            if not any(tag in name for tag in ["W", "Women", "U19", "U21", "U23"]):
                logger.info(f"Team '{team_name}' fallback: {name} (ID {team['id']})")
                return team["id"]

        return None

    def get_team_last_matches(self, team_id, last_n=5):
        """
        Recupera le ultime N partite finite di una squadra.
        Usa season=2024 (free plan) e filtra partite finite.
        """
        # Calcola la stagione attuale (inizia indicativamente ad agosto)
        current_year = datetime.now().year
        season = current_year if datetime.now().month >= 8 else current_year - 1

        data = self._make_request("fixtures", params={
            "team": team_id,
            "season": season,
            "status": "FT",  # Solo partite finite
        })

        if not data or "response" not in data:
            return None

        fixtures = data["response"]
        if not fixtures:
            return None

        # Ordina per data decrescente e prendi ultime N
        fixtures.sort(key=lambda f: f.get("fixture", {}).get("date", ""), reverse=True)
        fixtures = fixtures[:last_n]

        matches = []
        for fixture in fixtures:
            teams = fixture.get("teams", {})
            goals = fixture.get("goals", {})
            fixture_info = fixture.get("fixture", {})

            home_name = teams.get("home", {}).get("name", "")
            away_name = teams.get("away", {}).get("name", "")
            home_goals = goals.get("home", 0) or 0
            away_goals = goals.get("away", 0) or 0
            home_id = teams.get("home", {}).get("id")

            is_home = (home_id == team_id)
            if is_home:
                opponent = away_name
                gf, ga = home_goals, away_goals
            else:
                opponent = home_name
                gf, ga = away_goals, home_goals

            if gf > ga:
                result = "W"
            elif gf < ga:
                result = "L"
            else:
                result = "D"

            matches.append({
                "date": fixture_info.get("date", "")[:10],
                "opponent": opponent,
                "result": result,
                "goals_for": gf,
                "goals_against": ga,
                "score": f"{home_goals}-{away_goals}",
                "venue": "home" if is_home else "away",
            })

        return matches if matches else None

    def get_head_to_head(self, team1_id, team2_id, last_n=20):
        """
        Recupera scontri diretti tra due squadre (H2H).
        Endpoint: /fixtures/headtohead?h2h={id1}-{id2}&last={n}
        """
        if not self.api_key:
            return None

        data = self._make_request("fixtures/headtohead", params={
            "h2h": f"{team1_id}-{team2_id}",
            "last": last_n,
        })

        if not data or "response" not in data:
            return None

        fixtures = data["response"]
        if not fixtures:
            return None

        team1_wins = 0
        team2_wins = 0
        draws = 0
        matches = []

        # Determina i nomi dalle prime fixture
        team1_name = ""
        team2_name = ""

        for fixture in fixtures:
            teams = fixture.get("teams", {})
            goals = fixture.get("goals", {})
            fixture_info = fixture.get("fixture", {})
            league = fixture.get("league", {})

            home = teams.get("home", {})
            away = teams.get("away", {})
            home_goals = goals.get("home")
            away_goals = goals.get("away")

            # Salta partite senza risultato
            if home_goals is None or away_goals is None:
                continue

            # Identifica team1 e team2
            if home.get("id") == team1_id:
                if not team1_name:
                    team1_name = home.get("name", "")
                if not team2_name:
                    team2_name = away.get("name", "")
            elif away.get("id") == team1_id:
                if not team1_name:
                    team1_name = away.get("name", "")
                if not team2_name:
                    team2_name = home.get("name", "")

            # Determina vincitore
            if home_goals > away_goals:
                winner_id = home.get("id")
            elif away_goals > home_goals:
                winner_id = away.get("id")
            else:
                winner_id = None

            if winner_id == team1_id:
                team1_wins += 1
                result = "team1"
            elif winner_id == team2_id:
                team2_wins += 1
                result = "team2"
            else:
                draws += 1
                result = "draw"

            matches.append({
                "date": fixture_info.get("date", "")[:10],
                "home_team": home.get("name", ""),
                "away_team": away.get("name", ""),
                "home_score": home_goals,
                "away_score": away_goals,
                "score": f"{home_goals}-{away_goals}",
                "result": result,
                "competition": league.get("name", ""),
            })

        if not matches:
            return None

        return {
            "team1_name": team1_name,
            "team2_name": team2_name,
            "team1_wins": team1_wins,
            "team2_wins": team2_wins,
            "draws": draws,
            "total_matches": len(matches),
            "matches": matches,
        }


# Singleton instance
_apifootball_engine_instance = None


def get_apifootball_engine(api_key=None):
    """Ritorna istanza singleton del motore API-Football."""
    global _apifootball_engine_instance
    if _apifootball_engine_instance is None:
        _apifootball_engine_instance = APIFootballEngine(api_key=api_key)
    return _apifootball_engine_instance
