"""Allena il modello ML con dati storici - FACILE."""
import pandas as pd
import os
from src.ml.ml_predictor import MLMatchPredictor

print("🚀 Training Modello KOZA ML - Ibrido")
print("=" * 40)

# Crea cartelle se non esistono
os.makedirs('data', exist_ok=True)
os.makedirs('models', exist_ok=True)

# Cerca file dati
data_files = []
for f in os.listdir('data') if os.path.exists('data') else []:
    if f.endswith('.csv'):
        data_files.append(f'data/{f}')

if not data_files:
    print("⚠️ Nessun file CSV trovato in data/")
    print("📥 Scarica dati da: https://www.football-data.co.uk/italym.php")
    print("   1. Vai al sito")
    print("   2. Scarica Serie A 2023-24 e 2024-25")
    print("   3. Metti i file CSV in cartella data/")
    exit(1)

# Carica tutti i dati
dfs = []
for f in data_files:
    try:
        df = pd.read_csv(f)
        dfs.append(df)
        print(f"✅ Caricato: {f} ({len(df)} partite)")
    except Exception as e:
        print(f"❌ Errore {f}: {e}")

if not dfs:
    print("❌ Nessun dato valido trovato")
    exit(1)

df_all = pd.concat(dfs, ignore_index=True)
print(f"\n📊 Totale partite: {len(df_all)}")

# Allena modello
predictor = MLMatchPredictor(model_path='models/ml_model.pkl')
accuracy = predictor.train(df_all)

print(f"\n{'='*40}")
print(f"🎯 Accuracy: {accuracy:.2%}")
print(f"💾 Modello salvato in: models/ml_model.pkl")
print(f"\n✅ Pronto per usare con KOZA Bot!")
