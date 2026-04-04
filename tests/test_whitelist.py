"""
Test per verificare se ID 32 è ora in whitelist
"""
import os
os.environ['APIFOOTBALL_API_KEY'] = 'b2ca0ee4248ced374a8bb454ffb290bf'

from src.engines.apifootball_engine import get_apifootball_engine
from src.core.config import LEGHE_PRINCIPALI_APIFOOTBALL

engine = get_apifootball_engine()

print('Controllo whitelist:')
print('  ID 32 in whitelist?', '32' in LEGHE_PRINCIPALI_APIFOOTBALL)
print('  Nome per ID 32:', LEGHE_PRINCIPALI_APIFOOTBALL.get('32'))
print()

# Forza il motore a cercare
result = engine.get_partite_del_giorno()
print('Competizioni trovate da API-Football:')
print(f"  Totale: {len(result['competizioni'])}")
for c in result['competizioni']:
    print(f"  - {c['nome']} (ID: {c['id']}): {len(c['partite'])} partite")
    for p in c['partite'][:2]:
        print(f"      > {p['casa']} vs {p['trasferta']}")
