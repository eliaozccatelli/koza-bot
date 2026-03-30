"""
SportsDB Engine per KOZA Bot
Gestisce le chiamate all'API TheSportsDB per dati calcistici reali
"""

import os
import json
import logging
import requests
from datetime import datetime, timedelta

from config import LEGHE_PRINCIPALI

logger = logging.getLogger(__name__)

THESPORTSDB_API_KEY = os.getenv("THESPORTSDB_API_KEY", "123")  # Default free key
THESPORTSDB_BASE_URL = "https://www.thesportsdb.com/api/v1/json"

# Carica fallback JSON se esiste
FALLBACK_JSON_PATH = os.path.join(os.path.dirname(__file__), "partite_2026.json")

def _carica_fallback_json():
    """Carica partite dal file JSON locale."""
    try:
        if os.path.exists(FALLBACK_JSON_PATH):
            with open(FALLBACK_JSON_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"Errore caricamento fallback JSON: {e}")
    return {"partite_per_data": {}}

# ID leghe principali in TheSportsDB
LEGA_IDS = {
    "Serie A": "4332",
    "Premier League": "4328",
    "La Liga": "4335",
    "Bundesliga": "4331",
    "Ligue 1": "4334",
    "Champions League": "4480",
    "Europa League": "4481",
    "Conference League": "5007"
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
        MOSTRA SOLO COMPETIZIONI PRINCIPALI (whitelist in config.py)
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
        logger.info(f"TheSportsDB: trovate {len(events)} partite totali")

        # Organizza per competizione (SOLO leghe principali)
        competizioni = {}
        for event in events:
            lega = event.get("strLeague", "Unknown")
            lega_id = event.get("idLeague", "0")
            
            # FILTRO: Mostra solo competizioni in whitelist
            if lega_id not in LEGHE_PRINCIPALI:
                logger.info(f"FILTRO: Partita '{event.get('strEvent', 'N/A')}' scartata - ID lega '{lega_id}' ('{lega}') non in whitelist")
                continue  # Salta leghe minori, femminili, etc.
            
            nome_visualizzato = LEGHE_PRINCIPALI.get(lega_id, lega)

            if lega_id not in competizioni:
                competizioni[lega_id] = {
                    "id": lega_id,
                    "nome": nome_visualizzato,
                    "partite": []
                }

            competizioni[lega_id]["partite"].append({
                "id": event.get("idEvent"),
                "casa": event.get("strHomeTeam"),
                "trasferta": event.get("strAwayTeam"),
                "data": event.get("strTimestamp"),
                "stadio": event.get("strVenue"),
                "round": event.get("intRound")
            })
        
        # NOTA: Mostra SOLO competizioni con partite REALI dall'API
        # Non aggiungiamo fallback automatico per evitare pulsanti vuoti
        
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

    def get_fallback_json_partite(self, data):
        """
        Recupera partite dal JSON fallback (partite_2026.json).
        Metodo pubblico per accesso da logica_koza.py.
        """
        data_str = data.strftime("%Y-%m-%d")
        logger.info(f"Cerco partite JSON fallback per data: {data_str}")
        
        json_data = _carica_fallback_json()
        partite_json = json_data.get("partite_per_data", {}).get(data_str)
        
        if partite_json and partite_json.get("competizioni"):
            # Filtra solo le competizioni in whitelist
            competizioni_filtrate = []
            for comp in partite_json["competizioni"]:
                comp_id = comp.get("id")
                if comp_id in LEGHE_PRINCIPALI:
                    comp["nome"] = LEGHE_PRINCIPALI.get(comp_id, comp.get("nome"))
                    competizioni_filtrate.append(comp)
                    logger.info(f"  - {comp['nome']}: {len(comp.get('partite', []))} partite")
            
            if competizioni_filtrate:
                logger.info(f"✓ JSON fallback: {len(competizioni_filtrate)} competizioni")
                return {"competizioni": competizioni_filtrate}
        
        logger.warning(f"JSON fallback: nessuna partita trovata per {data_str}")
        return {"competizioni": []}

    def _get_fallback_partite(self, data):
        """Fallback con partite statiche se API fallisce.
        
        Priorità:
        1. File JSON partite_2026.json (se esiste per quella data)
        2. Fallback statico generico
        """
        data_str = data.strftime("%Y-%m-%d")
        logger.info(f"Cerco fallback per data: {data_str}")
        
        # Prova prima il JSON
        json_data = _carica_fallback_json()
        partite_json = json_data.get("partite_per_data", {}).get(data_str)
        
        if partite_json and partite_json.get("competizioni"):
            logger.info(f"✓ Trovate {len(partite_json['competizioni'])} competizioni nel JSON fallback")
            # Filtra solo le competizioni in whitelist
            competizioni_filtrate = []
            for comp in partite_json["competizioni"]:
                comp_id = comp.get("id")
                if comp_id in LEGHE_PRINCIPALI:
                    comp["nome"] = LEGHE_PRINCIPALI.get(comp_id, comp.get("nome"))
                    competizioni_filtrate.append(comp)
                    logger.info(f"  - {comp['nome']}: {len(comp.get('partite', []))} partite")
            
            if competizioni_filtrate:
                return {"competizioni": competizioni_filtrate}
            logger.warning("JSON presente ma nessuna competizione in whitelist")
        
        # Fallback statico generico
        logger.warning("Using fallback statico generico")
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
                },
                {
                    "id": "4335",
                    "nome": f"La Liga - {giorno}",
                    "partite": [
                        {"id": "ES1_1", "casa": "Real Madrid", "trasferta": "Barcelona", "stadio": "Santiago Bernabeu"},
                        {"id": "ES1_2", "casa": "Atletico Madrid", "trasferta": "Sevilla", "stadio": "Wanda Metropolitano"}
                    ]
                },
                {
                    "id": "4331",
                    "nome": f"Bundesliga - {giorno}",
                    "partite": [
                        {"id": "DE1_1", "casa": "Bayern Monaco", "trasferta": "Borussia Dortmund", "stadio": "Allianz Arena"},
                        {"id": "DE1_2", "casa": "Bayer Leverkusen", "trasferta": "RB Leipzig", "stadio": "BayArena"}
                    ]
                },
                {
                    "id": "4334",
                    "nome": f"Ligue 1 - {giorno}",
                    "partite": [
                        {"id": "FR1_1", "casa": "Paris Saint-Germain", "trasferta": "Monaco", "stadio": "Parc des Princes"},
                        {"id": "FR1_2", "casa": "Lille", "trasferta": "Marseille", "stadio": "Stade Pierre-Mauroy"}
                    ]
                },
                {
                    "id": "4480",
                    "nome": f"Champions League - {giorno}",
                    "partite": [
                        {"id": "UCL_1", "casa": "Real Madrid", "trasferta": "Manchester City", "stadio": "Santiago Bernabeu"},
                        {"id": "UCL_2", "casa": "Bayern Monaco", "trasferta": "Paris Saint-Germain", "stadio": "Allianz Arena"}
                    ]
                },
                {
                    "id": "4481",
                    "nome": f"Europa League - {giorno}",
                    "partite": [
                        {"id": "UEL_1", "casa": "Manchester United", "trasferta": "Roma", "stadio": "Old Trafford"},
                        {"id": "UEL_2", "casa": "Liverpool", "trasferta": "Ajax", "stadio": "Anfield"}
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
