# 📖 TUTORIAL PRATICO - ML da Zero per KOZA Bot

## 🎯 OBIETTIVO
Alla fine di questo tutorial avrai:
1. ✅ Un modello ML che predice 1X2
2. ✅ Integrato con KOZA Bot (affianco a Gemini)
3. ✅ Tracking risultati per migliorarlo nel tempo

---

## 📁 STEP 1: Setup File e Cartelle

### **1.1 Crea la struttura:**

```
KOZA/
├── bot_tg.py              (già esiste)
├── logica_koza.py          (già esiste)
├── ml_predictor.py         (creato ora!)
├── ml_integration.py       (creeremo tra poco)
├── data/                   (nuova cartella)
│   ├── serie_a_2023.csv
│   ├── serie_a_2024.csv
│   └── training_log.csv    (log automatico)
└── models/                 (nuova cartella)
    └── ml_model.pkl        (modello salvato)
```

### **1.2 Crea cartelle:**

```bash
# Nel terminale, dentro cartella KOZA
mkdir data
mkdir models
```

---

## 📥 STEP 2: Scaricare Dati (Gratis)

### **2.1 Vai su football-data.co.uk**

1. Apri browser: https://www.football-data.co.uk/italym.php
2. Clicca su **"Serie A 2023-2024"** → scarica CSV
3. Clicca su **"Serie A 2024-2025"** → scarica CSV
4. Sposta i file in `KOZA/data/`

### **2.2 Oppure scarica con Python:**

Crea file `download_data.py`:

```python
"""Scarica dati Serie A automaticamente."""
import requests
import os

# URL dati Serie A (football-data.co.uk)
URLS = {
    'serie_a_2023.csv': 'https://www.football-data.co.uk/mmz4281/2324/I0.csv',
    'serie_a_2024.csv': 'https://www.football-data.co.uk/mmz4281/2425/I0.csv',
}

os.makedirs('data', exist_ok=True)

for filename, url in URLS.items():
    print(f"Scaricando {filename}...")
    response = requests.get(url)
    
    with open(f'data/{filename}', 'wb') as f:
        f.write(response.content)
    print(f"✅ Salvato in data/{filename}")

print("\n🎉 Dati pronti per training!")
```

**Esegui:**
```bash
python download_data.py
```

---

## 🧠 STEP 3: Primo Training

### **3.1 Crea file `train_model.py`:**

```python
"""Allena il modello ML con dati storici."""
import pandas as pd
from ml_predictor import MLMatchPredictor

print("🚀 Training Modello KOZA ML")
print("=" * 40)

# 1. Carica dati
df_2023 = pd.read_csv('data/serie_a_2023.csv')
df_2024 = pd.read_csv('data/serie_a_2024.csv')

# Unisci tutti i dati
df_all = pd.concat([df_2023, df_2024], ignore_index=True)

print(f"📊 Dati caricati: {len(df_all)} partite")

# 2. Crea e allena modello
predictor = MLMatchPredictor(model_path='models/ml_model.pkl')

accuracy = predictor.train(df_all)

print(f"\n✅ Training completato!")
print(f"🎯 Accuracy: {accuracy:.2%}")
print(f"💾 Modello salvato in: models/ml_model.pkl")
```

### **3.2 Esegui training:**

```bash
python train_model.py
```

**Output atteso:**
```
🚀 Training Modello KOZA ML
========================================
📊 Dati caricati: 570 partite

✅ Modello allenato! Accuracy: 58.32%

🔍 Feature Importance:
       feature  importance
  home_form_5       0.245
  away_form_5       0.198
  home_goals_avg    0.156
  h2h_home_win_pct  0.134
  ...

💾 Modello salvato in: models/ml_model.pkl
```

**📝 Nota**: 58% è normale! Calcio è imprevedibile. Casuale sarebbe 33%.

---

## 🔗 STEP 4: Integrare con KOZA Bot

### **4.1 Crea `ml_integration.py`:**

```python
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
```

---

## 🔧 STEP 5: Modificare KOZA per usare ML

### **5.1 Modifica `logica_koza.py`:**

Aggiungi in cima al file (dopo gli altri import):

```python
# ML Integration
try:
    from ml_integration import get_ml_prediction
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
```

### **5.2 Aggiungi funzione in `logica_koza.py`:**

```python
def get_enhanced_analysis(casa, trasferta, info_analisi):
    """
    Combina analisi Gemini + Predizione ML.
    
    Returns:
        dict con entrambe le analisi
    """
    result = {
        'gemini_analysis': None,
        'ml_prediction': None,
        'combined': None
    }
    
    # 1. Analisi Gemini (già esistente)
    gemini = get_gemini_engine()
    if gemini.is_configured():
        result['gemini_analysis'] = gemini.analyze_match(
            f"{casa} vs {trasferta}",
            f"Partita {casa} vs {trasferta}",
            info_analisi
        )
    
    # 2. Predizione ML (nuova!)
    if ML_AVAILABLE:
        ml_result = get_ml_prediction(casa, trasferta)
        if ml_result:
            result['ml_prediction'] = ml_result
    
    # 3. Combined (se entrambe disponibili)
    if result['gemini_analysis'] and result['ml_prediction']:
        # Media pesata: Gemini 60%, ML 40% (oppure 50/50)
        gemini_probs = result['gemini_analysis'].get('probabilita', {})
        ml_probs = result['ml_prediction']
        
        result['combined'] = {
            '1': round(gemini_probs.get('1', 33) * 0.6 + ml_probs['1'] * 0.4, 1),
            'X': round(gemini_probs.get('X', 33) * 0.6 + ml_probs['X'] * 0.4, 1),
            '2': round(gemini_probs.get('2', 33) * 0.6 + ml_probs['2'] * 0.4, 1),
        }
    
    return result
```

### **5.3 Modifica `formatta_output` per mostrare ML:**

Nel file `logica_koza.py`, aggiungi sezione ML nell'output:

```python
def formatta_output(self, info_analisi):
    # ... codice esistente ...
    
    # Aggiungi sezione ML (se disponibile)
    if ML_AVAILABLE:
        ml_result = get_ml_prediction(casa, trasferta)
        if ml_result:
            msg += f"\n🤖 **Predizione ML**\n"
            msg += f"🧠 1: {ml_result['1']}% | X: {ml_result['X']}% | 2: {ml_result['2']}%\n"
            msg += f"🎯 Predizione: {ml_result['prediction']} (conf: {ml_result['confidence']}%)\n\n"
    
    # ... resto codice esistente ...
```

---

## 🧪 STEP 6: Test Completo

### **6.1 Esegui test:**

```bash
# 1. Training
python train_model.py

# 2. Test ML integration
python ml_integration.py

# 3. Avvia bot
python bot_tg.py
```

### **6.2 Verifica nel bot:**

Ora quando analizzi una partita vedrai:

```
🤖 **Predizione ML**
🧠 1: 62.5% | X: 22.3% | 2: 15.2%
🎯 Predizione: 1 (conf: 62.5%)

🧠 **Analisi Gemini**
... resto analisi ...
```

---

## 📊 STEP 7: Migliorare nel Tempo (Tracking)

### **7.1 Salva predizioni e confronta con realtà:**

Aggiungi in `ml_integration.py`:

```python
def log_prediction(self, match_id, home, away, ml_pred, actual_result):
    """
    Salva predizione e risultato reale per valutare accuracy nel tempo.
    """
    import csv
    from datetime import datetime
    
    log_file = 'data/prediction_log.csv'
    
    # Scrivi header se file nuovo
    file_exists = os.path.exists(log_file)
    
    with open(log_file, 'a', newline='') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['date', 'match_id', 'home', 'away', 
                           'ml_pred', 'ml_conf', 'actual', 'correct'])
        
        correct = (ml_pred == actual_result)
        writer.writerow([
            datetime.now().isoformat(),
            match_id, home, away,
            ml_pred, ml_probs, actual_result,
            correct
        ])
```

---

## 🎓 RISPOSTE FAQ

### **"Quanto è accurato il modello?"**
- Tipicamente **55-60%** sul 1X2
- Casuale = 33%, quindi è **significativamente meglio** del caso
- Non garantisce vincite scommesse (margini bookmaker ~5-8%)

### **"Posso usarlo per scommesse?"**
- Tecnicamente sì, ma **attenzione**: 
- L'accuracy del 58% = piccolo edge
- Value betting richiede confronto con odds bookmaker
- **Disclaimer**: Usa a scopo informativo

### **"Come migliorarlo?"**
1. Più dati storici (10+ stagioni)
2. Feature avanzate (xG, tiri in porta, possesso palla)
3. Altri algoritmi (XGBoost, Neural Networks)
4. Ensemble di più modelli

### **"ML sostituisce Gemini?"**
- **No**, li usiamo insieme! (Hybrid)
- Gemini = analisi contestuale (news, assenze)
- ML = pattern storici (statistica)
- Combined = più forte di entrambi

---

## ✅ CHECKLIST RIASSUNTIVA

- [ ] Installare librerie: `pip install scikit-learn pandas numpy`
- [ ] Creare cartelle `data/` e `models/`
- [ ] Scaricare dati da football-data.co.uk
- [ ] Eseguire `train_model.py`
- [ ] Verificare modello salvato in `models/`
- [ ] Testare con `python ml_integration.py`
- [ ] Modificare `logica_koza.py` per mostrare ML
- [ ] Testare nel bot Telegram
- [ ] Iniziare tracking predizioni vs risultati

---

## 🚀 PROSSIMI PASSI

1. **Aggiungere più leghe**: scarica Premier, La Liga, Bundesliga
2. **Feature avanzate**: integrare RapidAPI per xG reali
3. **Modello ensemble**: combinare Random Forest + XGBoost
4. **Dashboard web**: Flask app per visualizzare performance ML

**Domande? Chiedi pure!** 🤖⚽
