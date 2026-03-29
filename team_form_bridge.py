"""
Team Form Bridge - Integra RapidAPI con forma squadre
Usa dati reali quando disponibili, fallback a dati statici
"""

import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from rapidapi_engine import get_rapidapi_engine
from team_ratings import get_team_form as get_static_team_form, TEAM_RATINGS

logger = logging.getLogger(__name__)

# Cache per evitare chiamate API ripetute
_form_cache = {}
_cache_ttl = 3600  # 1 ora


def get_team_form(team_name: str, use_real_data: bool = True) -> str:
    """
    Recupera la forma di una squadra.
    
    Args:
        team_name: Nome della squadra
        use_real_data: Se True, prova a usare RapidAPI per dati reali
        
    Returns:
        Stringa con forma (es: "WWDLW") o fallback statico
    """
    rapidapi = get_rapidapi_engine()
    
    # Se RapidAPI non è disponibile o disabilitato, usa statico
    if not use_real_data or not rapidapi.is_available():
        logger.debug(f"Using static form for {team_name}")
        return get_static_team_form(team_name)
    
    # Cerca nella cache
    cache_key = f"form_{team_name}"
    if cache_key in _form_cache:
        cached_time, cached_data = _form_cache[cache_key]
        if (datetime.now() - cached_time).seconds < _cache_ttl:
            logger.debug(f"Using cached form for {team_name}")
            return cached_data
    
    # Prova a recuperare dati reali da RapidAPI
    try:
        # Cerca team ID
        team_info = rapidapi.search_team(team_name)
        
        if team_info and 'id' in team_info:
            team_id = team_info['id']
            
            # Recupera forma reale
            form_data = rapidapi.get_team_form(team_id, last_n=5)
            
            if form_data and 'form' in form_data:
                real_form = form_data['form']
                
                # Cache e ritorna
                _form_cache[cache_key] = (datetime.now(), real_form)
                
                logger.info(f"Real form for {team_name}: {real_form}")
                return real_form
        
        # Fallback a statico se non trovato
        logger.debug(f"Team {team_name} not found in RapidAPI, using static")
        return get_static_team_form(team_name)
        
    except Exception as e:
        logger.error(f"Error fetching real form for {team_name}: {e}")
        return get_static_team_form(team_name)


def get_team_form_with_details(team_name: str, use_real_data: bool = True) -> Dict[str, Any]:
    """
    Recupera forma dettagliata con statistiche.
    
    Returns:
        {
            'form': 'WWDLW',
            'wins': 3,
            'draws': 1,
            'losses': 1,
            'goals_for': 8,
            'goals_against': 4,
            'source': 'rapidapi' | 'static',
            'matches': [...]  # solo se da RapidAPI
        }
    """
    rapidapi = get_rapidapi_engine()
    
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
    
    if not use_real_data or not rapidapi.is_available():
        return result
    
    # Prova dati reali
    try:
        team_info = rapidapi.search_team(team_name)
        
        if team_info and 'id' in team_info:
            form_data = rapidapi.get_team_form(team_info['id'], last_n=5)
            
            if form_data:
                stats = form_data.get('stats', {})
                result.update({
                    'form': form_data.get('form', static_form),
                    'wins': stats.get('wins', 0),
                    'draws': stats.get('draws', 0),
                    'losses': stats.get('losses', 0),
                    'goals_for': stats.get('goals_for', 0),
                    'goals_against': stats.get('goals_against', 0),
                    'source': 'rapidapi',
                    'matches': form_data.get('matches', [])
                })
                
    except Exception as e:
        logger.error(f"Error fetching detailed form: {e}")
    
    return result


def get_head_to_head(team1: str, team2: str) -> Optional[Dict[str, Any]]:
    """
    Recupera storico scontri diretti.
    
    Returns:
        {
            'team1_wins': int,
            'team2_wins': int,
            'draws': int,
            'total_matches': int,
            'matches': [...],
            'source': 'rapidapi' | None
        }
    """
    rapidapi = get_rapidapi_engine()
    
    if not rapidapi.is_available():
        return None
    
    try:
        # Cerca entrambi i team
        team1_info = rapidapi.search_team(team1)
        team2_info = rapidapi.search_team(team2)
        
        if team1_info and team2_info:
            h2h_data = rapidapi.get_head_to_head(
                team1_info['id'], 
                team2_info['id'],
                last_n=5
            )
            
            if h2h_data:
                h2h_data['source'] = 'rapidapi'
                return h2h_data
                
    except Exception as e:
        logger.error(f"Error fetching H2H: {e}")
    
    return None


def format_team_form(team_name: str, use_real_data: bool = True) -> str:
    """
    Formatta la forma squadre per display nel bot.
    
    Args:
        team_name: Nome della squadra
        use_real_data: Usa dati reali se disponibili
        
    Returns:
        Stringa formattata es: "WWDLW (3V-1P-1S, 8GF-4GS)"
    """
    details = get_team_form_with_details(team_name, use_real_data)
    
    form = details['form']
    wins = details['wins']
    draws = details['draws']
    losses = details['losses']
    
    if details['source'] == 'rapidapi':
        gf = details.get('goals_for', 0)
        ga = details.get('goals_against', 0)
        return f"{form} ({wins}V-{draws}P-{losses}S, {gf}GF-{ga}GS) 📊"
    else:
        return f"{form} ({wins}V-{draws}P-{losses}S)"


def clear_cache():
    """Pulisce la cache delle forme squadre"""
    global _form_cache
    _form_cache = {}
    logger.info("Team form cache cleared")
