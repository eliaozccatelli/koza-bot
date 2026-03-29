"""
Integrazione ML con KOZA Bot.
Usa modello ML insieme a Gemini (approccio ibrido).
"""
import pandas as pd
import os
from datetime import datetime, timedelta
from ml_predictor import MLMatchPredictor
import logging

logger = logging.getLogger(__name__)


class MLBridge:
    """
    Ponte tra ML e logica KOZA esistente.
    Carica modello e fa predizioni su partite reali.
    """
    
    def __init__(self):
        self.predictor = None
        self.historical_data = None
        self.load_model()
    
    def load_model(self):
        """Carica modello se esiste."""
        model_path = 'models/ml_model.pkl'
        
        if os.path.exists(model_path):
            self.predictor = MLMatchPredictor(model_path)
            logger.info("✅ Modello ML caricato")
            return True
        else:
            logger.warning("⚠️ Modello ML non trovato. Esegui train_model.py")
            return False
    
    def load_historical_data(self):
        """Carica dati storici per calcolare feature."""
        try:
            data_files = [
                'data/serie_a_2023.csv',
                'data/serie_a_2024.csv'
            ]
            
            dfs = []
            for f in data_files:
                if os.path.exists(f):
                    dfs.append(pd.read_csv(f))
            
            if dfs:
                self.historical_data = pd.concat(dfs, ignore_index=True)
                logger.info(f"📊 Dati storici caricati: {len(self.historical_data)} partite")
                return True
            
        except Exception as e:
            logger.error(f"Errore caricamento dati: {e}")
        
        return False
    
    def predict_match(self, home_team, away_team, league='Serie A'):
        """
        Predice risultato partita con ML.
        
        Args:
            home_team: Nome squadra casa
            away_team: Nome squadra trasferta
            league: Campionato
        
        Returns:
            dict con predizione ML o None se errore
        """
        if not self.predictor or not self.predictor.is_trained:
            logger.warning("ML non disponibile")
            return None
        
        if self.historical_data is None:
            self.load_historical_data()
        
        try:
            # Crea DataFrame partita
            match_df = pd.DataFrame([{
                'Date': datetime.now().strftime('%Y-%m-%d'),
                'HomeTeam': home_team,
                'AwayTeam': away_team
            }])
            
            # Predizione
            result = self.predictor.predict(match_df, self.historical_data)
            
            return {
                '1': round(result['probabilities']['1'] * 100, 1),
                'X': round(result['probabilities']['X'] * 100, 1),
                '2': round(result['probabilities']['2'] * 100, 1),
                'prediction': result['prediction'],
                'confidence': round(result['confidence'] * 100, 1)
            }
            
        except Exception as e:
            logger.error(f"Errore predizione ML: {e}")
            return None


# Singleton instance
_ml_bridge = None

def get_ml_bridge():
    """Ritorna istanza singleton MLBridge."""
    global _ml_bridge
    if _ml_bridge is None:
        _ml_bridge = MLBridge()
    return _ml_bridge


def get_ml_prediction(home_team, away_team, league='Serie A'):
    """Funzione helper semplice."""
    bridge = get_ml_bridge()
    return bridge.predict_match(home_team, away_team, league)


# ═════════════════════════════════════════════════════════════════
# TEST
# ═════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("🧪 Test ML Integration")
    print("=" * 40)
    
    # Test predizione
    result = get_ml_prediction("Inter", "Milan")
    
    if result:
        print(f"\n🎯 ML Prediction: Inter vs Milan")
        print(f"   1: {result['1']}%")
        print(f"   X: {result['X']}%")
        print(f"   2: {result['2']}%")
        print(f"   Predizione: {result['prediction']} (conf: {result['confidence']}%)")
    else:
        print("\n⚠️ ML non disponibile. Esegui prima train_model.py")
