"""
Verifica tutte le partite playoff mondiali 2026
"""
import os
os.environ['APIFOOTBALL_API_KEY'] = 'b2ca0ee4248ced374a8bb454ffb290bf'

from apifootball_engine import get_apifootball_engine

engine = get_apifootball_engine()

# Cerca TUTTE le partite di oggi
result = engine._make_request('fixtures', {
    'date': '2026-03-26',
    'timezone': 'Europe/Rome'
})

print('=== TUTTE LE PARTITE OGGI ===')
if result and 'response' in result:
    fixtures = result['response']
    print(f'Totale partite API: {len(fixtures)}')
    print()
    
    # Lista completa playoff attesi
    expected = [
        ('Turkey', 'Türkiye', 'Romania'),
        ('Wales', 'Galles', 'Bosnia', 'Bosnia ed Erzegovina'),
        ('Ukraine', 'Ucraina', 'Sweden', 'Svezia'),
        ('Poland', 'Polonia', 'Albania'),
        ('Slovakia', 'Slovacchia', 'Kosovo'),
        ('Denmark', 'Danimarca', 'Macedonia'),
        ('Czech Republic', 'Repubblica Ceca', 'Ireland', 'Irlanda'),
        ('Italy', 'Italia', 'Northern Ireland', 'Irlanda del Nord')
    ]
    
    print('Partite trovate:')
    for f in fixtures:
        home = f['teams']['home']['name']
        away = f['teams']['away']['name']
        league = f['league']['name']
        league_id = f['league']['id']
        time = f['fixture']['date'][11:16]
        
        # Mostra solo se è playoff mondiale
        if 'World Cup' in league or league_id == 32:
            print(f"  {time} - {home} vs {away}")
            print(f"    ({league} - ID: {league_id})")
