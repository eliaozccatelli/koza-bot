"""
RapidAPI Engine - Wrapper per Free API Live Football Data
Recupera dati calcistici reali da RapidAPI
"""

import requests
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from config import RAPIDAPI_KEY, RAPIDAPI_HOST

logger = logging.getLogger(__name__)


class RapidAPIEngine:
    """
    Engine per recuperare dati calcistici reali da RapidAPI.
    Usa l'API "Free API Live Football Data" di Creativesdev.
    """
    
    def __init__(self, api_key: str = None):
        """Inizializza l'engine con la chiave API"""
        self.api_key = api_key or RAPIDAPI_KEY
        self.host = RAPIDAPI_HOST
        self.base_url = f"https://{self.host}"
        
        if not self.api_key:
            logger.warning("RapidAPI key non configurata. L'engine non funzionerà.")
        else:
            logger.info(f"RapidAPI Engine inizializzato con host: {self.host}")
    
    def _get_headers(self) -> Dict[str, str]:
        """Restituisce gli headers per le richieste API"""
        return {
            "X-RapidAPI-Key": self.api_key,
            "X-RapidAPI-Host": self.host
        }
    
    def _make_request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """Effettua una richiesta all'API"""
        if not self.api_key:
            logger.error("Impossibile fare richiesta: API key mancante")
            return None
        
        url = f"{self.base_url}/{endpoint}"
        
        try:
            response = requests.get(
                url,
                headers=self._get_headers(),
                params=params,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 429:
                logger.warning("Rate limit RapidAPI superato")
                return None
            else:
                logger.error(f"Errore API: {response.status_code} - {response.text}")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Errore richiesta HTTP: {e}")
            return None
        except Exception as e:
            logger.error(f"Errore imprevisto: {e}")
            return None
    
    def get_team_form(self, team_id: int, last_n: int = 5) -> Optional[Dict[str, Any]]:
        """
        Recupera la forma reale di una squadra (ultime N partite).
        
        Args:
            team_id: ID della squadra nell'API
            last_n: Numero di partite da recuperare (default 5)
            
        Returns:
            Dict con forma squadra o None se errore
            {
                'team_id': int,
                'team_name': str,
                'form': 'WWDLW',  # sequenza W/D/L
                'matches': [
                    {
                        'date': str,
                        'opponent': str,
                        'result': str,  # 'W', 'D', 'L'
                        'score_home': int,
                        'score_away': int,
                        'venue': str  # 'home' o 'away'
                    }
                ],
                'stats': {
                    'wins': int,
                    'draws': int,
                    'losses': int,
                    'goals_for': int,
                    'goals_against': int
                }
            }
        """
        # Nota: L'endpoint esatto dipende dalla documentazione dell'API
        # Questo è un esempio di implementazione
        
        endpoint = "teams/form"  # Endpoint ipotetico
        params = {
            "team_id": team_id,
            "last": last_n
        }
        
        data = self._make_request(endpoint, params)
        
        if data and 'response' in data:
            return self._parse_team_form(data['response'])
        
        return None
    
    def _parse_team_form(self, response_data: Dict) -> Dict[str, Any]:
        """Parsa la risposta dell'API per estrarre la forma squadra"""
        try:
            team_info = response_data.get('team', {})
            matches = response_data.get('matches', [])
            
            form_sequence = []
            parsed_matches = []
            stats = {'wins': 0, 'draws': 0, 'losses': 0, 'goals_for': 0, 'goals_against': 0}
            
            for match in matches:
                result = match.get('result', '')  # 'W', 'D', 'L'
                form_sequence.append(result)
                
                if result == 'W':
                    stats['wins'] += 1
                elif result == 'D':
                    stats['draws'] += 1
                else:
                    stats['losses'] += 1
                
                stats['goals_for'] += match.get('goals_for', 0)
                stats['goals_against'] += match.get('goals_against', 0)
                
                parsed_matches.append({
                    'date': match.get('date'),
                    'opponent': match.get('opponent', {}).get('name', 'Unknown'),
                    'result': result,
                    'score_home': match.get('score', {}).get('home', 0),
                    'score_away': match.get('score', {}).get('away', 0),
                    'venue': match.get('venue', 'unknown')
                })
            
            return {
                'team_id': team_info.get('id'),
                'team_name': team_info.get('name'),
                'form': ''.join(form_sequence),
                'matches': parsed_matches,
                'stats': stats
            }
            
        except Exception as e:
            logger.error(f"Errore parsing forma squadra: {e}")
            return None
    
    def get_live_fixtures(self, date: str = None, league_id: int = None) -> List[Dict]:
        """
        Recupera le partite del giorno.
        
        Args:
            date: Data in formato YYYY-MM-DD (default: oggi)
            league_id: ID della lega (opzionale)
            
        Returns:
            Lista di partite
        """
        if not date:
            date = datetime.now().strftime('%Y-%m-%d')
        
        endpoint = "fixtures"
        params = {"date": date}
        if league_id:
            params["league_id"] = league_id
        
        data = self._make_request(endpoint, params)
        
        if data and 'response' in data:
            return data['response']
        
        return []
    
    def get_head_to_head(self, team1_id: int, team2_id: int, last_n: int = 5) -> Optional[Dict]:
        """
        Recupera lo storico degli scontri diretti tra due squadre.
        
        Args:
            team1_id: ID prima squadra
            team2_id: ID seconda squadra
            last_n: Numero di incontri da recuperare
            
        Returns:
            Dict con storico scontri diretti
        """
        endpoint = "headtohead"
        params = {
            "teams": f"{team1_id},{team2_id}",
            "last": last_n
        }
        
        data = self._make_request(endpoint, params)
        
        if data and 'response' in data:
            return self._parse_head_to_head(data['response'])
        
        return None
    
    def _parse_head_to_head(self, response_data: Dict) -> Dict[str, Any]:
        """Parsa la risposta degli scontri diretti"""
        try:
            matches = response_data.get('matches', [])
            
            team1_name = response_data.get('team1', {}).get('name', 'Team 1')
            team2_name = response_data.get('team2', {}).get('name', 'Team 2')
            
            team1_wins = 0
            team2_wins = 0
            draws = 0
            parsed_matches = []
            
            for match in matches:
                home_team = match.get('home', {}).get('name', '')
                away_team = match.get('away', {}).get('name', '')
                home_score = match.get('score', {}).get('home', 0)
                away_score = match.get('score', {}).get('away', 0)
                
                if home_score > away_score:
                    if home_team == team1_name:
                        team1_wins += 1
                    else:
                        team2_wins += 1
                elif home_score < away_score:
                    if away_team == team1_name:
                        team1_wins += 1
                    else:
                        team2_wins += 1
                else:
                    draws += 1
                
                parsed_matches.append({
                    'date': match.get('date'),
                    'home_team': home_team,
                    'away_team': away_team,
                    'home_score': home_score,
                    'away_score': away_score,
                    'competition': match.get('competition', {}).get('name', '')
                })
            
            return {
                'team1_name': team1_name,
                'team2_name': team2_name,
                'team1_wins': team1_wins,
                'team2_wins': team2_wins,
                'draws': draws,
                'total_matches': len(matches),
                'matches': parsed_matches
            }
            
        except Exception as e:
            logger.error(f"Errore parsing H2H: {e}")
            return None
    
    def get_team_standings(self, league_id: int, season: int = None) -> List[Dict]:
        """
        Recupera la classifica di una lega.
        
        Args:
            league_id: ID della lega
            season: Stagione (default: corrente)
            
        Returns:
            Lista di posizioni in classifica
        """
        if not season:
            season = datetime.now().year
        
        endpoint = "standings"
        params = {
            "league_id": league_id,
            "season": season
        }
        
        data = self._make_request(endpoint, params)
        
        if data and 'response' in data:
            return data['response']
        
        return []
    
    def search_team(self, team_name: str) -> Optional[Dict]:
        """
        Cerca una squadra per nome.
        
        Args:
            team_name: Nome della squadra
            
        Returns:
            Info squadra o None
        """
        endpoint = "teams/search"
        params = {"name": team_name}
        
        data = self._make_request(endpoint, params)
        
        if data and 'response' in data and len(data['response']) > 0:
            return data['response'][0]
        
        return None
    
    def get_team_stats(self, team_id: int, league_id: int = None, season: int = None) -> Optional[Dict]:
        """
        Recupera le statistiche di una squadra.
        
        Args:
            team_id: ID della squadra
            league_id: ID della lega (opzionale)
            season: Stagione (default: corrente)
            
        Returns:
            Dict con statistiche
        """
        if not season:
            season = datetime.now().year
        
        endpoint = "teams/statistics"
        params = {
            "team_id": team_id,
            "season": season
        }
        if league_id:
            params["league_id"] = league_id
        
        data = self._make_request(endpoint, params)
        
        if data and 'response' in data:
            return data['response']
        
        return None
    
    def is_available(self) -> bool:
        """Verifica se l'engine è disponibile (ha una API key valida)"""
        return bool(self.api_key)


# Singleton instance
_rapidapi_engine = None


def get_rapidapi_engine() -> RapidAPIEngine:
    """Restituisce l'istanza singleton di RapidAPIEngine"""
    global _rapidapi_engine
    if _rapidapi_engine is None:
        _rapidapi_engine = RapidAPIEngine()
    return _rapidapi_engine
