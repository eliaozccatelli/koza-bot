"""
Test fix season 2024
"""
import os
os.environ['APIFOOTBALL_API_KEY'] = 'b2ca0ee4248ced374a8bb454ffb290bf'
from src.engines.apifootball_engine import get_apifootball_engine
engine = get_apifootball_engine()

from datetime import date
partite = engine.get_partite_per_lega(32, data=date(2026, 3, 26))

print(f'Trovate {len(partite)} partite per ID 32:')
for p in partite:
    print(f"  - {p['casa']} vs {p['trasferta']}")
