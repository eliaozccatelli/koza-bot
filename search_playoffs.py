"""
Cerca le partite playoff mondiali 2026
"""
import os
os.environ['APIFOOTBALL_API_KEY'] = 'b2ca0ee4248ced374a8bb454ffb290bf'

from apifootball_engine import get_apifootball_engine

engine = get_apifootball_engine()

# Cerca TUTTE le partite di oggi senza filtro
print('=== TUTTE LE PARTITE OGGI (senza filtro) ===')
result = engine._make_request('fixtures', {
    'date': '2026-03-26',
    'timezone': 'Europe/Rome'
})

if result and 'response' in result:
    fixtures = result['response']
    print(f'Totale partite API: {len(fixtures)}')
    print()
    
    # Cerca partite con Italy, Turkey, etc.
    keywords = ['Italy', 'Italia', 'Turkey', 'Turchia', 'Romania', 'Ireland', 'Irlanda', 'Northern Ireland']
    found = []
    
    for f in fixtures:
        home = f['teams']['home']['name']
        away = f['teams']['away']['name']
        league = f['league']['name']
        league_id = f['league']['id']
        
        for kw in keywords:
            if kw.lower() in home.lower() or kw.lower() in away.lower():
                found.append({
                    'home': home, 'away': away, 'league': league, 
                    'league_id': league_id, 'date': f['fixture']['date']
                })
                break
    
    if found:
        print('✅ PARTITE PLAYOFF TROVATE:')
        for m in found:
            print(f"  - {m['home']} vs {m['away']}")
            print(f"    Lega: {m['league']} (ID: {m['league_id']})")
            print()
    else:
        print('❌ NESSUNA partita trovata con keywords Italia/Turchia/Romania/Irlanda')
        print()
        print('Prime 10 partite disponibili:')
        for f in fixtures[:10]:
            home = f['teams']['home']['name']
            away = f['teams']['away']['name']
            league = f['league']['name']
            print(f"  - {home} vs {away} ({league})")
else:
    print('Errore nella risposta API')
