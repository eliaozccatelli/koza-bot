"""
SportsDB Engine per KOZA Bot
Gestisce le chiamate all'API TheSportsDB per dati calcistici reali
"""

import os
import json
import logging
import requests
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

THESPORTSDB_API_KEY = os.getenv("THESPORTSDB_API_KEY", "123")  # Default free key
THESPORTSDB_BASE_URL = "https://www.thesportsdb.com/api/v1/json"

# ID leghe principali in TheSportsDB
LEGA_IDS = {
    "Serie A": "4332",
    "Premier League": "4328",
    "La Liga": "4335",
    "Bundesliga": "4331",
    "Ligue 1": "4334",
    "Champions League": "4480",
    "Europa League": "4481"
}


class SportsDBEngine:
    """Motore per dati calcistici reali da TheSportsDB."""

    def __init__(self, api_key=None):
        self.api_key = api_key or THESPORTSDB_API_KEY
        self.base_url = f"{THESPORTSDB_BASE_URL}/{self.api_key}"
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json"
        })

    def _make_request(self, endpoint, params=None):
        """Effettua una richiesta GET all'API."""
        url = f"{self.base_url}/{endpoint}"
        try:
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Errore richiesta TheSportsDB: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"Errore parsing JSON: {e}")
            return None

    def get_partite_del_giorno(self, data=None, sport="Soccer"):
        """
        Recupera partite del giorno specificato.
        Endpoint: /eventsday.php
        """
        if data is None:
            data = datetime.now().date()

        data_str = data.strftime("%Y-%m-%d")
        logger.info(f"=== THESPORTSDB === Cerco partite per {data_str}")

        result = self._make_request("eventsday.php", {
            "d": data_str,
            "s": sport
        })

        if not result or "events" not in result:
            logger.warning("TheSportsDB: nessuna partita trovata")
            return self._get_fallback_partite(data)

        events = result.get("events", [])
        logger.info(f"TheSportsDB: trovate {len(events)} partite")

        # Organizza per competizione
        competizioni = {}
        for event in events:
            lega = event.get("strLeague", "Unknown")
            lega_id = event.get("idLeague", "0")

            if lega not in competizioni:
                competizioni[lega] = {
                    "id": lega_id,
                    "nome": lega,
                    "partite": []
                }

            competizioni[lega]["partite"].append({
                "id": event.get("idEvent"),
                "casa": event.get("strHomeTeam"),
                "trasferta": event.get("strAwayTeam"),
                "data": event.get("strTimestamp"),
                "stadio": event.get("strVenue"),
                "round": event.get("intRound")
            })

        return {"competizioni": list(competizioni.values())}

    def get_partite_per_lega(self, lega_id, data=None):
        """
        Recupera partite per una specifica lega.
        """
        if data is None:
            data = datetime.now().date()

        data_str = data.strftime("%Y-%m-%d")
        result = self._make_request("eventsday.php", {
            "d": data_str,
            "s": "Soccer"
        })

        if not result or "events" not in result:
            return []

        events = result.get("events", [])
        partite = []

        for event in events:
            if event.get("idLeague") == str(lega_id):
                partite.append({
                    "id": event.get("idEvent"),
                    "casa": event.get("strHomeTeam"),
                    "trasferta": event.get("strAwayTeam"),
                    "data": event.get("strTimestamp"),
                    "stadio": event.get("strVenue"),
                    "round": event.get("intRound")
                })

        return partite

    def get_info_squadra(self, nome_squadra):
        """
        Recupera informazioni su una squadra.
        Endpoint: /searchteams.php
        """
        result = self._make_request("searchteams.php", {"t": nome_squadra})

        if not result or "teams" not in result:
            return None

        teams = result.get("teams", [])
        if not teams:
            return None

        team = teams[0]  # Prendi il primo risultato
        return {
            "id": team.get("idTeam"),
            "nome": team.get("strTeam"),
            "alternativi": team.get("strTeamAlternate", "").split(","),
            "lega": team.get("strLeague"),
            "id_lega": team.get("idLeague"),
            "stadio": team.get("strStadium"),
            "descrizione": team.get("strDescriptionIT") or team.get("strDescriptionEN"),
            "logo": team.get("strBadge"),
            "paese": team.get("strCountry"),
            "fondazione": team.get("intFormedYear")
        }

    def get_dettaglio_partita(self, match_id):
        """
        Recupera dettagli di una partita specifica.
        Endpoint: /lookupevent.php
        """
        result = self._make_request("lookupevent.php", {"id": match_id})

        if not result or "events" not in result:
            return None

        events = result.get("events", [])
        if not events:
            return None

        event = events[0]
        return {
            "id": event.get("idEvent"),
            "casa": event.get("strHomeTeam"),
            "trasferta": event.get("strAwayTeam"),
            "data": event.get("strTimestamp"),
            "stadio": event.get("strVenue"),
            "lega": event.get("strLeague"),
            "round": event.get("intRound"),
            "risultato": f"{event.get('intHomeScore', '-')}:{event.get('intAwayScore', '-')}"
        }

    def _get_fallback_partite(self, data):
        """Fallback con partite statiche se API fallisce."""
        logger.warning("Using fallback partite")
        giorno = data.strftime('%d/%m/%Y')
        return {
            "competizioni": [
                {
                    "id": "4332",
                    "nome": f"Serie A - {giorno}",
                    "partite": [
                        {"id": "IT1_1", "casa": "Inter", "trasferta": "Milan", "stadio": "San Siro"},
                        {"id": "IT1_2", "casa": "Juventus", "trasferta": "Napoli", "stadio": "Allianz Stadium"},
                        {"id": "IT1_3", "casa": "Roma", "trasferta": "Lazio", "stadio": "Olimpico"}
                    ]
                },
                {
                    "id": "4328",
                    "nome": f"Premier League - {giorno}",
                    "partite": [
                        {"id": "EN1_1", "casa": "Manchester City", "trasferta": "Liverpool", "stadio": "Etihad"},
                        {"id": "EN1_2", "casa": "Arsenal", "trasferta": "Chelsea", "stadio": "Emirates"}
                    ]
                }
            ]
        }


# Singleton instance
_sportsdb_engine_instance = None


def get_sportsdb_engine(api_key=None):
    """Ritorna istanza singleton del motore TheSportsDB."""
    global _sportsdb_engine_instance
    if _sportsdb_engine_instance is None:
        _sportsdb_engine_instance = SportsDBEngine(api_key=api_key)
    return _sportsdb_engine_instance
