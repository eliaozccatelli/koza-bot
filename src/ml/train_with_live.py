"""
Training ML con dati live parsati dai messaggi Telegram.
Unisce dati storici (2024-2026) + dati live (parsed_matches.csv)
"""

import pandas as pd
import os
import sys

# Aggiungi root alla path per le importazioni da terminale
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from datetime import datetime
from src.ml.ml_predictor import MLMatchPredictor

def load_parsed_matches(filename='parsed_matches.csv'):
    """Carica partite parsate dai messaggi."""
    if not os.path.exists(filename):
        print(f"⚠️ File {filename} non trovato")
        return None
    
    df = pd.read_csv(filename)
    print(f"📊 Caricate {len(df)} partite da {filename}")
    
    # Rimuovi duplicati (stessa partita con stesso risultato)
    df = df.drop_duplicates(subset=['HomeTeam', 'AwayTeam', 'FTHG', 'FTAG'], keep='first')
    print(f"📊 Dopo rimozione duplicati: {len(df)} partite uniche")
    
    return df


def convert_to_training_format(df_parsed, ml_predictor):
    """
    Converte parsed matches nel formato richiesto per training.
    Aggiunge feature di base (gol fatti/subiti calcolati dal risultato).
    """
    if df_parsed is None or len(df_parsed) == 0:
        return None
    
    training_rows = []
    
    for _, row in df_parsed.iterrows():
        # Crea record base
        match_data = {
            'Date': row['Date'],
            'HomeTeam': row['HomeTeam'],
            'AwayTeam': row['AwayTeam'],
            'FTHG': row['FTHG'],  # Full Time Home Goals
            'FTAG': row['FTAG'],  # Full Time Away Goals
            'FTR': row['FTR'],    # Full Time Result (H/D/A)
            # Feature base calcolate dal risultato
            'HTHG': row['FTHG'] // 2 if row['FTHG'] > 0 else 0,  # Stima gol primo tempo casa
            'HTAG': row['FTAG'] // 2 if row['FTAG'] > 0 else 0,  # Stima gol primo tempo trasferta
            'HTR': 'H' if row['FTHG'] // 2 > row['FTAG'] // 2 else ('A' if row['FTHG'] // 2 < row['FTAG'] // 2 else 'D'),
            # Quote dummy (verranno calcolate dalla distribuzione)
            'B365H': 2.0,  # Default
            'B365D': 3.0,
            'B365A': 3.0,
        }
        training_rows.append(match_data)
    
    return pd.DataFrame(training_rows)


def merge_with_historical(live_df):
    """Unisce dati live con dati storici."""
    # Carica dati storici 2024-2026
    historical_files = []
    for year in [2024, 2025, 2026]:
        filepath = f'data/serie_a_{year}.csv'
        if os.path.exists(filepath):
            historical_files.append(filepath)
    
    if not historical_files:
        print("❌ Nessun dato storico trovato")
        return live_df
    
    # Carica storico
    historical_dfs = []
    for f in historical_files:
        df = pd.read_csv(f)
        historical_dfs.append(df)
        print(f"✅ Caricato: {f} ({len(df)} partite)")
    
    historical = pd.concat(historical_dfs, ignore_index=True)
    print(f"📊 Totale dati storici: {len(historical)} partite")
    
    # Unisci con live data
    if live_df is not None and len(live_df) > 0:
        # Allinea colonne
        common_cols = list(set(historical.columns) & set(live_df.columns))
        historical = historical[common_cols]
        live_df = live_df[common_cols]
        
        combined = pd.concat([historical, live_df], ignore_index=True)
        print(f"📊 Dataset combinato: {len(combined)} partite")
        return combined
    else:
        return historical


def train_with_combined_data():
    """Training completo con dati storici + live."""
    print("🚀 Training Modello KOZA con Dati Live")
    print("=" * 50)
    
    # 1. Carica dati parsati
    live_matches = load_parsed_matches('parsed_matches.csv')
    
    # 2. Converti in formato training
    if live_matches is not None and len(live_matches) > 0:
        ml_pred = MLMatchPredictor()
        live_formatted = convert_to_training_format(live_matches, ml_pred)
        print(f"✅ Formattate {len(live_formatted)} partite live")
    else:
        live_formatted = None
    
    # 3. Unisci con storico
    combined_data = merge_with_historical(live_formatted)
    
    if combined_data is None or len(combined_data) == 0:
        print("❌ Nessun dato disponibile per training")
        return
    
    # 4. Salva dataset combinato temporaneo
    temp_file = 'data/combined_training_data.csv'
    combined_data.to_csv(temp_file, index=False)
    print(f"💾 Dataset salvato in: {temp_file}")
    
    # 5. Addestra modello
    print("\n🎯 Avvio training...")
    ml = MLMatchPredictor()
    
    try:
        accuracy = ml.train(combined_data)
        
        print(f"\n🎯 RISULTATI:")
        print(f"   Accuracy: {accuracy:.2%}")
        print(f"   Dati totali: {len(combined_data)} partite")
        print(f"   - Storiche: ~1050 partite (Serie A 2024-2026)")
        if live_formatted is not None:
            print(f"   - Live parsate: {len(live_formatted)} partite (multi-campionato)")
        
        print(f"\n💾 Modello salvato!")
        print("✅ Training completato!")
        
    except Exception as e:
        print(f"❌ Errore training: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    train_with_combined_data()
