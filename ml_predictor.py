"""
ML Predictor per KOZA Bot
Modello: XGBoost Classifier (Opzione B)
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
import pickle
import os
import logging

logger = logging.getLogger(__name__)


class MLMatchPredictor:
    """Predictor ML per risultati partite di calcio."""
    
    def __init__(self, model_path='models/ml_model.pkl'):
        self.model_path = model_path
        self.model = None
        self.is_trained = False
        self.feature_names = [
            'home_form_5', 'away_form_5',
            'home_goals_avg', 'away_goals_avg',
            'h2h_home_win_pct',
            'home_rank', 'away_rank',
            'home_win_rate', 'away_win_rate',
            'home_advantage', 'away_performance',
            'strength_diff',
            'goals_diff_home', 'goals_diff_away',
            # OPZIONE A: Quote bookmaker
            'odds_home', 'odds_draw', 'odds_away',
            'implied_prob_1', 'implied_prob_x', 'implied_prob_2',
            'odds_favorite',
        ]
        
        if os.path.exists(model_path):
            self.load_model()
    
    def calculate_team_form(self, df, team, n_games=5):
        """Calcola forma ultimi N partite (punti)."""
        team_games = df[(df['HomeTeam'] == team) | (df['AwayTeam'] == team)]
        team_games = team_games.sort_values('Date', ascending=False).head(n_games)
        
        points = 0
        for _, game in team_games.iterrows():
            if game['HomeTeam'] == team:
                if game['FTR'] == 'H':
                    points += 3
                elif game['FTR'] == 'D':
                    points += 1
            else:
                if game['FTR'] == 'A':
                    points += 3
                elif game['FTR'] == 'D':
                    points += 1
        
        return points
    
    def calculate_goals_avg(self, df, team, venue='home'):
        """Media gol fatti."""
        if venue == 'home':
            games = df[df['HomeTeam'] == team]
            return games['FTHG'].mean() if len(games) > 0 else 1.0
        else:
            games = df[df['AwayTeam'] == team]
            return games['FTAG'].mean() if len(games) > 0 else 1.0
    
    def calculate_h2h(self, df, home_team, away_team, n_games=5):
        """Scontri diretti - percentuale vittorie casa."""
        h2h = df[
            ((df['HomeTeam'] == home_team) & (df['AwayTeam'] == away_team)) |
            ((df['HomeTeam'] == away_team) & (df['AwayTeam'] == home_team))
        ].sort_values('Date', ascending=False).head(n_games)
        
        if len(h2h) == 0:
            return 0.5
        
        home_wins = len(h2h[(h2h['HomeTeam'] == home_team) & (h2h['FTR'] == 'H')])
        return home_wins / len(h2h)
    
    def calculate_team_strength(self, df, team):
        """
        Calcola forza squadra basata su punti totali nella stagione.
        Ritorna punti totali e posizione stimata.
        """
        team_games = df[(df['HomeTeam'] == team) | (df['AwayTeam'] == team)]
        
        points = 0
        wins = 0
        draws = 0
        losses = 0
        goals_for = 0
        goals_against = 0
        
        for _, game in team_games.iterrows():
            if game['HomeTeam'] == team:
                goals_for += game['FTHG']
                goals_against += game['FTAG']
                if game['FTR'] == 'H':
                    points += 3
                    wins += 1
                elif game['FTR'] == 'D':
                    points += 1
                    draws += 1
                else:
                    losses += 1
            else:
                goals_for += game['FTAG']
                goals_against += game['FTHG']
                if game['FTR'] == 'A':
                    points += 3
                    wins += 1
                elif game['FTR'] == 'D':
                    points += 1
                    draws += 1
                else:
                    losses += 1
        
        games_played = len(team_games)
        if games_played == 0:
            return {'points': 0, 'position': 10, 'win_rate': 0.33}
        
        win_rate = wins / games_played
        # Stima posizione: 20 squadre, distribuzione punti
        # Max punti possibili ~90, min ~20
        position = max(1, min(20, 20 - (points / (games_played * 3)) * 19))
        
        return {
            'points': points,
            'position': position,
            'win_rate': win_rate,
            'goals_diff': goals_for - goals_against
        }
    
    def calculate_home_advantage(self, df, team):
        """Calcola vantaggio campo (percentuale vittorie in casa)."""
        home_games = df[df['HomeTeam'] == team]
        if len(home_games) == 0:
            return 0.5
        
        home_wins = len(home_games[home_games['FTR'] == 'H'])
        return home_wins / len(home_games)
    
    def calculate_away_performance(self, df, team):
        """Calcola performance in trasferta."""
        away_games = df[df['AwayTeam'] == team]
        if len(away_games) == 0:
            return 0.3
        
        away_wins = len(away_games[away_games['FTR'] == 'A'])
        return away_wins / len(away_games)
    
    def create_features(self, df, historical_df=None):
        """Crea feature matrix."""
        if historical_df is None:
            historical_df = df
        
        features = []
        
        for _, match in df.iterrows():
            home_team = match['HomeTeam']
            away_team = match['AwayTeam']
            
            # Calcola forza squadre
            home_strength = self.calculate_team_strength(historical_df, home_team)
            away_strength = self.calculate_team_strength(historical_df, away_team)
            
            # Estrai quote bookmaker (se disponibili)
            b365h = match.get('B365H', np.nan)
            b365d = match.get('B365D', np.nan)
            b365a = match.get('B365A', np.nan)
            
            # Se mancano quote, usa valori neutrali
            if pd.isna(b365h):
                b365h, b365d, b365a = 2.0, 3.5, 2.0
            
            # Calcola implied probability (probabilità implicita)
            margin = (1/b365h + 1/b365d + 1/b365a) - 1
            fair_prob_1 = (1/b365h) / (1 + margin)
            fair_prob_x = (1/b365d) / (1 + margin)
            fair_prob_2 = (1/b365a) / (1 + margin)
            
            feat = {
                'home_form_5': self.calculate_team_form(historical_df, home_team, 5),
                'away_form_5': self.calculate_team_form(historical_df, away_team, 5),
                'home_goals_avg': self.calculate_goals_avg(historical_df, home_team, 'home'),
                'away_goals_avg': self.calculate_goals_avg(historical_df, away_team, 'away'),
                'h2h_home_win_pct': self.calculate_h2h(historical_df, home_team, away_team, 5),
                # Forza squadre
                'home_rank': home_strength['position'],
                'away_rank': away_strength['position'],
                'home_win_rate': home_strength['win_rate'],
                'away_win_rate': away_strength['win_rate'],
                'home_advantage': self.calculate_home_advantage(historical_df, home_team),
                'away_performance': self.calculate_away_performance(historical_df, away_team),
                'strength_diff': home_strength['position'] - away_strength['position'],
                'goals_diff_home': home_strength['goals_diff'],
                'goals_diff_away': away_strength['goals_diff'],
                # OPZIONE A: Quote bookmaker (ESSENZIALE!)
                'odds_home': b365h,
                'odds_draw': b365d,
                'odds_away': b365a,
                'implied_prob_1': fair_prob_1,
                'implied_prob_x': fair_prob_x,
                'implied_prob_2': fair_prob_2,
                'odds_favorite': min(b365h, b365d, b365a),
            }
            features.append(feat)
        
        return pd.DataFrame(features)
    
    def prepare_labels(self, df):
        """Converte risultati in numeri."""
        mapping = {'H': 0, 'D': 1, 'A': 2}
        return df['FTR'].map(mapping).values
    
    def train(self, df):
        """Allena il modello."""
        logger.info(f"Training modello con {len(df)} partite...")
        
        X = self.create_features(df, df)
        y = self.prepare_labels(df)
        
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=y
        )
        
        # Random Forest - più stabile per questi dati
        self.model = RandomForestClassifier(
            n_estimators=150,        # Bilanciato
            max_depth=12,            # Un po' più profondo
            min_samples_split=10,    # Più conservativo
            random_state=42,
            class_weight='balanced'
        )
        
        self.model.fit(X_train, y_train)
        
        y_pred = self.model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        
        logger.info(f"✅ Modello allenato! Accuracy: {accuracy:.2%}")
        
        self.is_trained = True
        self.save_model()
        
        return accuracy
    
    def predict(self, match_data, historical_df=None):
        """Predice risultato partita."""
        if not self.is_trained:
            raise ValueError("Modello non allenato!")
        
        X = self.create_features(match_data, historical_df)
        
        prediction = self.model.predict(X)[0]
        probabilities = self.model.predict_proba(X)[0]
        
        results_map = {0: '1', 1: 'X', 2: '2'}
        
        return {
            'prediction': results_map[prediction],
            'probabilities': {
                '1': probabilities[0],
                'X': probabilities[1],
                '2': probabilities[2]
            },
            'confidence': max(probabilities)
        }
    
    def save_model(self):
        """Salva modello."""
        if self.model:
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
            with open(self.model_path, 'wb') as f:
                pickle.dump(self.model, f)
            logger.info(f"Modello salvato in {self.model_path}")
    
    def load_model(self):
        """Carica modello."""
        with open(self.model_path, 'rb') as f:
            self.model = pickle.load(f)
        self.is_trained = True
        logger.info(f"Modello caricato da {self.model_path}")


if __name__ == "__main__":
    print("✅ ml_predictor.py caricato correttamente")
    print("Esegui train_model.py per allenare il modello")

