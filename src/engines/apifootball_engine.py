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

# Singleton instance
_apifootball_engine_instance = None


def get_apifootball_engine(api_key=None):
    """Ritorna istanza singleton del motore API-Football."""
    global _apifootball_engine_instance
    if _apifootball_engine_instance is None:
        _apifootball_engine_instance = APIFootballEngine(api_key=api_key)
    return _apifootball_engine_instance
