"""
Integrazione ML con KOZA Bot.
Usa modello ML insieme a Gemini (approccio ibrido).
"""
import pandas as pd
import os
from datetime import datetime, timedelta
from src.ml.ml_predictor import MLMatchPredictor
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
        """Carica dati storici per calcolare feature (tutti i CSV disponibili)."""
        try:
            import glob as glob_mod

            dfs = []
            common_cols = ['Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTR',
                           'B365H', 'B365D', 'B365A']

            # Carica tutti i serie_a_YYYY.csv disponibili
            for f in sorted(glob_mod.glob('data/serie_a_*.csv')):
                try:
                    df = pd.read_csv(f, encoding='utf-8-sig')
                    if 'HomeTeam' in df.columns and 'FTR' in df.columns:
                        dfs.append(df)
                        logger.info(f"📊 Caricato {f}: {len(df)} partite")
                except Exception as e:
                    logger.warning(f"Errore lettura {f}: {e}")

            # Carica parsed_matches.csv (dati live da Telegram)
            if os.path.exists('parsed_matches.csv'):
                try:
                    df_live = pd.read_csv('parsed_matches.csv')
                    if 'HomeTeam' in df_live.columns and 'FTR' in df_live.columns:
                        # Filtra righe corrotte
                        df_live = df_live[
                            df_live['HomeTeam'].astype(str).str.len().between(2, 40) &
                            df_live['AwayTeam'].astype(str).str.len().between(2, 40) &
                            ~df_live['HomeTeam'].astype(str).str.contains('\n', na=False) &
                            ~df_live['AwayTeam'].astype(str).str.contains('\n', na=False)
                        ]
                        if len(df_live) > 0:
                            dfs.append(df_live)
                            logger.info(f"📊 Caricato parsed_matches.csv: {len(df_live)} partite")
                except Exception as e:
                    logger.warning(f"Errore lettura parsed_matches.csv: {e}")

            if dfs:
                # Usa solo colonne comuni a tutti i DataFrame
                all_cols = set(dfs[0].columns)
                for df in dfs[1:]:
                    all_cols &= set(df.columns)
                # Assicura almeno le colonne minime
                min_cols = {'Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTR'}
                if min_cols.issubset(all_cols):
                    self.historical_data = pd.concat(
                        [df[list(all_cols)] for df in dfs], ignore_index=True
                    )
                else:
                    # Fallback: usa solo colonne minime
                    self.historical_data = pd.concat(
                        [df[list(min_cols & set(df.columns))] for df in dfs], ignore_index=True
                    )
                logger.info(f"📊 Dati storici totali: {len(self.historical_data)} partite")
                return True

        except Exception as e:
            logger.error(f"Errore caricamento dati: {e}")

        return False
    
    def predict_match(self, home_team, away_team, league='Serie A'):
        """
        Predice risultato partita con ML.
        Integra la predizione base con i rating aggiornati dalla classifica reale.
        """
        if not self.predictor or not self.predictor.is_trained:
            logger.warning("ML non disponibile")
            return None

        if self.historical_data is None:
            self.load_historical_data()

        try:
            # Verifica copertura: le squadre sono nei dati storici?
            home_known = False
            away_known = False
            if self.historical_data is not None:
                all_teams = set(self.historical_data['HomeTeam'].unique()) | set(self.historical_data['AwayTeam'].unique())
                home_known = home_team in all_teams
                away_known = away_team in all_teams

            if not home_known and not away_known:
                logger.info(f"ML skip: ne' {home_team} ne' {away_team} presenti nei dati storici")
                return None

            # Crea DataFrame partita
            match_df = pd.DataFrame([{
                'Date': datetime.now().strftime('%Y-%m-%d'),
                'HomeTeam': home_team,
                'AwayTeam': away_team
            }])

            # Predizione base ML
            result = self.predictor.predict(match_df, self.historical_data)

            prob_1 = result['probabilities']['1']
            prob_x = result['probabilities']['X']
            prob_2 = result['probabilities']['2']

            # Peso ML dinamico in base alla copertura dati
            if home_known and away_known:
                ml_weight = 0.35  # entrambe note: ML piu' affidabile
            else:
                ml_weight = 0.10  # solo una nota: ML poco affidabile
                logger.info(f"ML peso ridotto (10%): solo {'casa' if home_known else 'trasferta'} nei dati")
            rating_weight = 1.0 - ml_weight

            # Correggi con rating attuali dalla classifica reale
            from src.utils.team_ratings import get_team_rating
            rating_home = get_team_rating(home_team)
            rating_away = get_team_rating(away_team)
            diff = rating_home - rating_away  # positivo = casa piu' forte

            rating_prob_1 = 0.33 + (diff / 100.0)
            rating_prob_2 = 0.33 - (diff / 100.0)
            rating_prob_x = 0.34 - abs(diff / 100.0) * 0.3
            # Bonus fattore casa (+5%)
            rating_prob_1 += 0.05
            rating_prob_2 -= 0.02
            rating_prob_x -= 0.03
            # Normalizza rating probs
            rt = rating_prob_1 + rating_prob_x + rating_prob_2
            rating_prob_1, rating_prob_x, rating_prob_2 = rating_prob_1/rt, rating_prob_x/rt, rating_prob_2/rt

            # Blend dinamico ML / classifica attuale
            prob_1 = prob_1 * ml_weight + rating_prob_1 * rating_weight
            prob_x = prob_x * ml_weight + rating_prob_x * rating_weight
            prob_2 = prob_2 * ml_weight + rating_prob_2 * rating_weight

            # Normalizza a 1.0
            total = prob_1 + prob_x + prob_2
            prob_1 = max(0.05, prob_1 / total)
            prob_x = max(0.10, prob_x / total)
            prob_2 = max(0.05, prob_2 / total)
            total = prob_1 + prob_x + prob_2
            prob_1, prob_x, prob_2 = prob_1/total, prob_x/total, prob_2/total

            # Determina predizione
            if prob_1 > prob_2 and prob_1 > prob_x:
                prediction = '1'
                confidence = prob_1
            elif prob_2 > prob_1 and prob_2 > prob_x:
                prediction = '2'
                confidence = prob_2
            else:
                prediction = 'X'
                confidence = prob_x

            return {
                '1': round(prob_1 * 100, 1),
                'X': round(prob_x * 100, 1),
                '2': round(prob_2 * 100, 1),
                'prediction': prediction,
                'confidence': round(confidence * 100, 1)
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
