"""
Test con whitelist pulita
"""
import os
os.environ['APIFOOTBALL_API_KEY'] = 'b2ca0ee4248ced374a8bb454ffb290bf'
os.environ['THESPORTSDB_API_KEY'] = '123'

# Reset singleton
import apifootball_engine
apifootball_engine._apifootball_engine_instance = None

from apifootball_engine import get_apifootball_engine
from config import LEGHE_PRINCIPALI_APIFOOTBALL

print('=== WHITELIST API-FOOTBALL ===')
for k, v in LEGHE_PRINCIPALI_APIFOOTBALL.items():
    print(f'  {k}: {v}')
print()

engine = get_apifootball_engine()
result = engine.get_partite_del_giorno()

print(f"Competizioni trovate: {len(result['competizioni'])}")
for c in result['competizioni']:
    print(f"  - {c['nome']} (ID: {c['id']}): {len(c['partite'])} partite")
    for p in c['partite'][:3]:
        print(f"      {p['casa']} vs {p['trasferta']}")
