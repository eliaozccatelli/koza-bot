# ⚽ KOZA Bot 3.0 - Telegram Football Predictor

Bot Telegram intelligente per l'analisi e le previsioni delle partite di calcio, integrato con **Google Gemini AI** per analisi avanzate e **TheSportsDB API** per dati reali delle partite.

## 🎯 Cos'è KOZA Bot

KOZA Bot è un assistente personale per gli appassionati di calcio che fornisce:
- **Analisi AI** delle partite con Google Gemini
- **Dati reali** di partite, squadre e competizioni
- **Pronostici intelligenti** basati su statistica e machine learning
- **Interfaccia conversazionale** via Telegram con pulsanti inline

## 🏗️ Architettura e Come Funziona

### Flusso di Funzionamento

```
Utente Telegram → Bot Telegram → Logica KOZA → Engine AI/API → Risposta formattata
```

1. **Utente seleziona data** → Bot mostra competizioni disponibili
2. **Utente seleziona competizione** → Bot mostra partite del giorno
3. **Utente clicca partita** → Sistema analizza con Gemini AI
4. **Risultato formattato** → Messaggio Telegram con pronostico e scommesse

### Componenti Principali

| File | Funzione |
|------|----------|
| `bot_tg.py` | Interfaccia Telegram, gestione bot e pulsanti inline |
| `logica_koza.py` | Motore principale, orchestrazione tra AI e dati |
| `gemini_engine.py` | Integrazione Google Gemini AI per analisi |
| `sportsdb_engine.py` | Connessione TheSportsDB API per dati reali |
| `team_ratings.py` | Database rating squadre e forma algoritmica |
| `config.py` | Configurazioni globali e API keys |

### Tecnologie Utilizzate

- **Python 3.8+** - Linguaggio principale
- **Google Gemini AI** - Analisi testuale e generazione previsioni
- **TheSportsDB API** - Dati reali partite, squadre, competizioni
- **python-telegram-bot** - Framework bot Telegram
- **Fuzzy Matching** - Riconoscimento nomi squadre approssimativo
- **JSON** - Formato dati per risposte AI

## ✨ Caratteristiche Principali

### 🤖 Analisi AI con Gemini
- Analisi contestuale delle partite
- Generazione probabilità 1X2, Over/Under, Gol
- Scommesse consigliate personalizzate
- Fallback automatico se API non disponibile

### 📊 Dati Reali TheSportsDB
- Partite aggiornate giornalmente
- Competizioni principali (Serie A, Premier League, La Liga, Bundesliga, Ligue 1)
- Informazioni squadre e stadi
- Fallback statico se API fallisce

### 🎯 Pronostici Intelligenti
- **Probabilità calcolate**: 1 (casa), X (pareggio), 2 (trasferta)
- **Over/Under**: 2.5, 3.5 gol
- **Gol/No Gol**: entrambe le squadre segnano
- **Doppie chance**: 1X, X2, 12
- **Multigol**: range gol totali

### 💬 Interfaccia Utente
- **Inline buttons**: selezione intuitiva data → competizione → partita
- **Formattazione pulita**: output compatto e leggibile
- **Forma squadre**: sequenze W/D/L algoritmiche
- **Nessun Markdown pesante**: messaggi leggibili su mobile

### 🔧 Sistema di Fallback
- Se Gemini API fallisce → analisi statica basata su rating squadre
- Se TheSportsDB fallisce → partite statiche predefinite
- Forma squadre algoritmica basata su rating (W/D/L)

## 📁 Struttura del Progetto

```
KOZA/
├── bot_tg.py              # Entry point bot Telegram
├── logica_koza.py         # Business logic e orchestrazione
├── gemini_engine.py       # Wrapper Google Gemini API
├── sportsdb_engine.py     # Wrapper TheSportsDB API
├── team_ratings.py        # Database rating statico squadre
├── config.py              # Configurazioni e environment
├── requirements.txt       # Dipendenze Python
├── .env                   # Variabili d'ambiente (non committare)
└── README.md              # Questo file
```

## 🔧 Come è Implementato

### 1. Singleton Pattern
Tutti gli engine (Gemini, SportsDB, KOZA) usano il pattern Singleton per evitare istanze multiple:
```python
_engine_instance = None
def get_engine():
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = Engine()
    return _engine_instance
```

### 2. Fuzzy Matching Squadre
Riconoscimento nomi squadre anche con errori di battitura usando la libreria `thefuzz`.

### 3. Analisi Gemini
Prompt engineering per ottenere JSON strutturato con pronostici, probabilità e scommesse.

### 4. Forma Squadre Algoritmica
Generazione sequenze W/D/L basate su rating:
- Squadre forti (85+): più W (vittorie)
- Squadre medie (70-84): mix equilibrato
- Squadre deboli (<70): più L (sconfitte)

## 📥 Installazione

### 1. Clona la Repository
```bash
git clone https://github.com/tuo-username/koza-bot.git
cd koza-bot
```

### 2. Installa Dipendenze
```bash
pip install -r requirements.txt
```

### 3. Configura Environment
Crea file `.env`:
```env
GEMINI_API_KEY=AIzaSyC...tua_chiave_gemini
TELEGRAM_TOKEN=123456789:ABC...tuo_token_bot
THESPORTSDB_API_KEY=123  # o la tua chiave pro
```

### 4. Ottieni Credenziali

**Google Gemini API:**
1. Vai su [Google AI Studio](https://aistudio.google.com)
2. Crea API Key gratuita
3. Copia in `GEMINI_API_KEY`

**Token Telegram Bot:**
1. Apri Telegram, cerca `@BotFather`
2. Invia `/newbot`
3. Segui istruzioni e copia token

**TheSportsDB (opzionale):**
- Versione free: usa `123` come API key (dati limitati)
- Versione pro: registrati su [thesportsdb.com](https://thesportsdb.com)

## 🚀 Utilizzo

### Avvia il Bot
```bash
python bot_tg.py
```

### Comandi Telegram

| Comando | Descrizione |
|---------|-------------|
| `/start` | Avvia bot, selezione data |
| `/help` | Mostra guida completa |
| `/about` | Info sul bot |

### Flusso Utente

1. **Start** → Mostra bottoni: Oggi, Domani, Dopodomani
2. **Seleziona data** → Mostra competizioni disponibili
3. **Seleziona competizione** → Mostra partite del giorno
4. **Clicca partita** → Ricevi analisi AI completa

### Esempio Output

```
⚽ **Juventus** vs **Milan**
🎯 Pronostico: `2-1` | Confidenza: 62%

📊 Probabilità:
   1: 48% | X: 26% | 2: 26%
   Over 2.5: 54% | Gol: 51%

🔹 Juventus: WWDLW
🔹 Milan: WLWDW

💰 Scommesse Consigliate:
   • `1` - Vittoria Juventus
   • `Over 2.5` - Più di 2 gol
   • `Gol` - Entrambe segnano

⚠️ Previsioni AI - Gioca responsabilmente
```

## 🔐 Sicurezza

⚠️ **IMPORTANTE**: Non committare mai `.env` su GitHub!

Il file `.gitignore` è configurato per ignorare automaticamente:
- `.env`
- `__pycache__/`
- File temporanei Python

## 📝 Licenza

MIT License - Vedi file `LICENSE` per dettagli

## 👤 Autore

**Team KOZA** - Marzo 2026
