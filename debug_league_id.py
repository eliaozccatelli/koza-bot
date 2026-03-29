"""
Debug: Perché cercando per league=32 non trova le partite?
"""
import os
os.environ['APIFOOTBALL_API_KEY'] = 'b2ca0ee4248ced374a8bb454ffb290bf'

from apifootball_engine import get_apifootball_engine

engine = get_apifootball_engine()

print('=== TEST 1: Cerca per DATA (funziona) ===')
result1 = engine._make_request('fixtures', {
    'date': '2026-03-26',
    'timezone': 'Europe/Rome'
})

wc_fixtures = []
for f in result1.get('response', []):
    if f['league']['id'] == 32:
        wc_fixtures.append(f)

print(f'Trovate {len(wc_fixtures)} partite con league.id=32')
for f in wc_fixtures[:2]:
    print(f"  - {f['teams']['home']['name']} vs {f['teams']['away']['name']}")
    print(f"    Season: {f['league'].get('season')}, Round: {f['league'].get('round')}")
print()

print('=== TEST 2: Cerca per LEAGUE + DATA (non funziona) ===')
result2 = engine._make_request('fixtures', {
    'league': 32,
    'date': '2026-03-26',
    'timezone': 'Europe/Rome'
})
print(f'Risultato: {len(result2.get("response", []))} partite')
print()

print('=== TEST 3: Cerca per LEAGUE + SEASON ===')
result3 = engine._make_request('fixtures', {
    'league': 32,
    'season': 2026,
    'date': '2026-03-26',
    'timezone': 'Europe/Rome'
})
print(f'Risultato con season 2026: {len(result3.get("response", []))} partite')
print()

print('=== TEST 4: Cerca solo LEAGUE (senza data) ===')
result4 = engine._make_request('fixtures', {
    'league': 32,
    'season': 2024,
    'timezone': 'Europe/Rome'
})
print(f'Risultato season 2024: {len(result4.get("response", []))} partite')
