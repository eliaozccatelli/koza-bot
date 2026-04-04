"""
Test per verificare qualificazioni mondiali 2026
"""
import os
import sys

# Set API key
os.environ['APIFOOTBALL_API_KEY'] = 'b2ca0ee4248ced374a8bb454ffb290bf'

from src.engines.apifootball_engine import get_apifootball_engine
from datetime import datetime

engine = get_apifootball_engine()

print('=== TEST: Ricerca Qualificazioni Mondiali 2026 ===')
print('Data: 2026-03-26')
print()

# Test tutte le confederazioni qualificazioni mondiali
qualifiers = [
    (29, 'World Cup Qualifiers Europe'),
    (32, 'World Cup Qualifiers Africa'),
    (30, 'World Cup Qualifiers Asia'),
    (31, 'World Cup Qualifiers CONCACAF'),
    (28, 'World Cup Qualifiers South America'),
]

found_any = False
for league_id, name in qualifiers:
    print(f'Cerco {name} (ID: {league_id})...')
    result = engine._make_request('fixtures', {
        'date': '2026-03-26',
        'league': league_id,
        'timezone': 'Europe/Rome'
    })
    
    if result and 'response' in result:
        count = len(result['response'])
        if count > 0:
            print(f'  ✓ Trovate {count} partite!')
            found_any = True
            for f in result['response'][:2]:
                home = f['teams']['home']['name']
                away = f['teams']['away']['name']
                print(f'    - {home} vs {away}')
        else:
            print(f'  ✗ Nessuna partita in programma')
    else:
        print(f'  ✗ Errore o nessuna risposta')
    print()

if not found_any:
    print('=' * 50)
    print('NESSUNA QUALIFICAZIONE MONDIALE IN PROGRAMMA OGGI')
    print('=' * 50)
    print()
    print('Possibili motivi:')
    print('1. Le qualificazioni sono già terminate (Mondiali 2026 iniziano a giugno)')
    print('2. Non ci sono partite programmate per oggi in nessuna confederazione')
    print('3. Le ultime qualificazioni sono state giocate nei mesi precedenti')
