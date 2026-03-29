# ⚽ KOZA Bot 3.0 - Football Analysis Bot

Bot Telegram avanzato per l'analisi delle partite di calcio, integrato con **Google Gemini AI** per analisi predittive e multiple fonti dati per informazioni accurate.

## 📋 Indice

1. [Panoramica](#panoramica)
2. [Architettura](#architettura)
3. [Funzionalità Dettagliate](#funzionalità-dettagliate)
4. [Flusso Utente](#flusso-utente)
5. [Struttura Progetto](#struttura-progetto)
6. [Sistemi di Fallback](#sistemi-di-fallback)
7. [Configurazione](#configurazione)
8. [Installazione](#installazione)
9. [Utilizzo](#utilizzo)
10. [API Integrate](#api-integrate)

## Panoramica

KOZA Bot è un assistente calcistico su Telegram che combina:
- 🤖 **AI Generativa** (Google Gemini 2.0 Flash) per analisi predittive
- 📊 **Dati Reali** da TheSportsDB API
- 🔧 **Sistema di Fallback** JSON per partite non coperte dalle API
- 💬 **Interfaccia Inline** con pulsanti intuitivi

### Perché KOZA Bot?

| Problema | Soluzione KOZA |
|----------|---------------|
| API gratuite limitate | Sistema multi-fonte con fallback automatico |
| Dati incompleti | JSON locale per qualificazioni, Nations League, etc. |
| Analisi superficiali | AI Gemini con contesto calcistico avanzato |
| UX complessa | Pulsanti inline: 3 click per l'analisi |

## Architettura

### Diagramma del Flusso

```
Utente Telegram
    ↓
┌─────────────────────────────────────┐
│         bot_tg.py                   │
│  Interfaccia + Callback Handlers    │
└──────────┬──────────────────────────┘
           ↓
┌─────────────────────────────────────┐
│       logica_koza.py                │
│  Orchestrazione + Business Logic    │
└──────────┬──────────────────────────┘
           ↓
    ┌──────┴──────┬─────────────┐
    ↓             ↓             ↓
┌────────┐  ┌──────────┐  ┌────────────┐
│SportsDB│  │ Gemini   │  │ JSON       │
│ Engine │  │ Engine   │  │ Fallback   │
└────────┘  └──────────┘  └────────────┘
    ↓             ↓             ↓
Partite reali Analisi AI   Partite statiche
(top 5 + CL)  + Stats      (qualificazioni)
```

### Gerarchia delle Fonti Dati

Quando cerchi partite per una data, il bot cerca in ordine:

1. **TheSportsDB API** (gratuita)
   - ✅ Top 5 campionati europei
   - ✅ Champions League, Europa League, Conference League
   - ✅ Partite aggiornate giornalmente
   - ❌ Non copre: qualificazioni mondiali, Nations League (alcune)

2. **API-Football** (piano gratuito limitato)
   - ✅ Copre TUTTO (top 5 + qualificazioni + mondiali)
   - ❌ Limite: solo +3 giorni dalla data corrente
   - ✅ Usata per statistiche live durante le partite

3. **JSON Fallback** (`partite_2026.json`)
   - ✅ Nessun limite di data
   - ✅ Qualificazioni mondiali, Nations League, Asian Cup
   - ✅ Modificabile manualmente per aggiungere partite future
   - ✅ Priorità quando le API non trovano nulla

4. **Fallback Statico** (ultima risorsa)
   - Partite fittizie di esempio (Inter-Milan, etc.)

## Funzionalità Dettagliate

### 1. Sistema di Navigazione a 3 Livelli

```
Livello 1: SELEZIONE DATA
├─ 📅 Oggi (29/03) - Sabato
├─ 📅 Domani (30/03) - Domenica
└─ 📅 Dopodomani (31/03) - Lunedì
         ↓
Livello 2: SELEZIONE COMPETIZIONE
├─ 🏆 Serie A (3 partite)
├─ 🏆 Premier League (5 partite)
├─ 🏆 UEFA Nations League (2 partite)
└─ 🏆 AFC Asian Cup (3 partite)
         ↓
Livello 3: SELEZIONE PARTITA
├─ ⚽ Inter vs Milan
├─ ⚽ Juventus vs Napoli
└─ ⚽ Latvia vs Gibraltar
         ↓
    ANALISI AI
```

### 2. Analisi AI con Google Gemini

Quando clicchi una partita, Gemini analizza e genera:

**JSON Output:**
```json
{
  "pronostico": {
    "risultato_esatto": "2-1",
    "vincitore": "casa",
    "confidence": 75
  },
  "probabilita": {
    "1": 55, "X": 25, "2": 20,
    "over25": 65, "gol": 70
  },
  "analisi": {
    "forma_casa": "WWDLW",
    "forma_trasferta": "LWDLW",
    "assenti_casa": ["Giocatore X"],
    "ultimi_scontri": [...]
  },
  "scommesse_consigliate": [
    {"tipo": "1", "descrizione": "Vittoria casa"},
    {"tipo": "Over 2.5", "descrizione": "Più di 2 gol"}
  ]
}
```

**Messaggio Telegram Formattato:**
```
🤖 **ANALISI KOZA - Powered by Gemini AI**
=============================================

🏟 **LATVIA** vs **GIBRALTAR**

🎯 **PRONOSTICO**: `4-0` 
💡 **Confidence**: 55%
🏆 **Favorito**: casa

📊 **PROBABILITA'**:
   • 1 (Casa): 52.8%
   • X (Pareggio): 13.0%
   • 2 (Trasferta): 34.2%
   • Over 2.5: 46%
   • Gol: 37%

📈 **FORMA**:
   Latvia: WWDLW
   Gibraltar: LWDLW

   ❌ Assenti Latvia: Giocatore X

⚔️ **ULTIMI SCONTRI**:
   15/09/2024: 2-1 (V: casa)

=============================================
💰 **SCOMMESSE CONSIGLIATE**:

1. `1`
   Vittoria Latvia netta
2. `Over 2.5`
   Più di 2 gol attesi

⚠️ _Le previsioni sono generate da AI e non garantiscono risultati._
```

### 3. Persistenza Messaggi

A differenza di molti bot, KOZA **non cancella** i messaggi:

- **Analisi rimane in chat** → Storico consultabile
- **Nuovo messaggio per il menu** → Puoi accumulare analisi multiple
- **Pulsante "Torna indietro"** → Invia nuovo messaggio col menu date

**Vantaggio:** Puoi confrontare analisi diverse senza perdere lo storico.

### 4. Fuzzy Matching Squadre

Se scrivi i nomi delle squadre manualmente:
- "Inter" → ✓ Inter
- "Milan" → ✓ Milan
- "inter milan" → ✓ Inter vs Milan
- "inter-milan" → ✓ Inter vs Milan
- "int mil" → ✓ Inter vs Milan (con similarità 85%+)

Algoritmo: `rapidfuzz` con soglia 82% di similarità.

### 5. Modalità Manuale

Oltre ai pulsanti, puoi scrivere direttamente:
```
/predici Inter Milan
/predici Juventus Napoli
/predici Real Madrid vs Barcelona
```

## Flusso Utente

### Scenario 1: Partita dal Menu

```
1. Utente: /start
   Bot: [Pulsanti: Oggi, Domani, Dopodomani]

2. Utente: Clicca "Dopodomani (31/03)"
   Bot: [Pulsanti: Serie A, Nations League, Asian Cup...]

3. Utente: Clicca "UEFA Nations League"
   Bot: [Pulsanti: Latvia vs Gibraltar, Luxembourg vs Malta]

4. Utente: Clicca "Latvia vs Gibraltar"
   Bot: [Messaggio analisi AI completa + pulsante "Torna indietro"]

5. Utente: Clicca "🔙 Torna indietro"
   Bot: [Nuovo messaggio col menu date]
   (L'analisi Latvia-Gibraltar rimane in chat sopra)
```

### Scenario 2: Partita Manuale

```
Utente: Inter vs Milan
Bot: [Analisi AI diretta]
```

## Struttura Progetto

```
KOZA/
│
├── 📁 FILE PRINCIPALI
│   ├── bot_tg.py              # Entry point, interfaccia Telegram
│   ├── logica_koza.py         # Business logic, orchestrazione
│   └── config.py              # Configurazioni e whitelist
│
├── 📁 MOTORI DATI
│   ├── sportsdb_engine.py     # TheSportsDB API wrapper
│   ├── apifootball_engine.py  # API-Football wrapper
│   ├── gemini_engine.py       # Google Gemini AI wrapper
│   └── rapidapi_engine.py     # RapidAPI (stats avanzate)
│
├── 📁 DATI E FALLBACK
│   ├── teams_fallback.py      # Database statico squadre
│   ├── team_ratings.py        # Rating algoritmici squadre
│   ├── team_form_bridge.py    # Bridge forma reale vs statica
│   └── partite_2026.json      # Fallback JSON partite future
│
├── 📁 ML (Machine Learning)
│   ├── ml_integration.py      # Integrazione ML nel flusso
│   ├── ml_predictor.py        # Modelli ML per predizioni
│   ├── train_model.py         # Training modelli
│   └── train_with_live.py     # Training con dati live
│
├── 📁 TEST E DEBUG
│   ├── test_whitelist.py      # Test whitelist competizioni
│   ├── test_wc_qualifiers.py  # Test qualificazioni mondiali
│   ├── test_gemini.py         # Test connessione Gemini
│   └── debug_league_id.py     # Debug ID leghe
│
├── 📁 DOCUMENTAZIONE
│   ├── README.md              # Questo file
│   ├── ANALISI_PROGETTO.md    # Analisi tecnica dettagliata
│   ├── QUICKSTART.md          # Guida rapida 5 minuti
│   ├── TUTORIAL_ML.md         # Tutorial Machine Learning
│   └── .env.example           # Template variabili d'ambiente
│
└── 📁 CONFIGURAZIONE
    ├── requirements.txt       # Dipendenze Python
    ├── requirements-render.txt # Dipendenze per Render
    ├── render.yaml            # Configurazione Render.com
    └── .gitignore             # File ignorati da Git
```

## Sistemi di Fallback

### Fallback a Cascata

```
Utente cerca partite 31/03/2026
         ↓
┌─────────────────────────────────┐
│ 1. TheSportsDB API              │
│    ❌ Nessuna partita trovata   │
└────────┬────────────────────────┘
         ↓
┌─────────────────────────────────┐
│ 2. API-Football                 │
│    ❌ Limite +3 gg, ritorna 0   │
└────────┬────────────────────────┘
         ↓
┌─────────────────────────────────┐
│ 3. JSON Fallback                │
│    ✅ Trovate 5 partite!        │
│    - Nations League: 2 partite  │
│    - Asian Cup: 3 partite      │
└─────────────────────────────────┘
```

### Come Aggiungere Partite al JSON

Edita `partite_2026.json`:

```json
{
  "partite_per_data": {
    "2026-04-01": {
      "competizioni": [
        {
          "id": "4490",
          "nome": "UEFA Nations League",
          "partite": [
            {
              "id": "NL_0104_1",
              "casa": "Squadra A",
              "trasferta": "Squadra B",
              "stadio": "Stadio X",
              "data": "2026-04-01T20:45:00"
            }
          ]
        }
      ]
    }
  }
}
```

**ID Competizioni Supportati:**
| ID | Competizione |
|----|-------------|
| 4332 | Serie A |
| 4328 | Premier League |
| 4335 | La Liga |
| 4331 | Bundesliga |
| 4334 | Ligue 1 |
| 4480 | Champions League |
| 4481 | Europa League |
| 5007 | Conference League |
| 4490 | UEFA Nations League |
| 4866 | AFC Asian Cup Qualifiers |

## Configurazione

### File .env

Crea `.env` nella root:

```env
# Google Gemini AI (obbligatorio)
GEMINI_API_KEY=AIzaSyC...tua_chiave

# Telegram Bot (obbligatorio)
TELEGRAM_TOKEN=123456789:ABC...tuo_token

# TheSportsDB (opzionale, default: 123)
THESPORTSDB_API_KEY=123

# API-Football (opzionale, per stats live)
APIFOOTBALL_API_KEY=tua_chiave_api_football
```

### Whitelist Competizioni

In `config.py`, modifica `LEGHE_PRINCIPALI`:

```python
LEGHE_PRINCIPALI = {
    "4332": "Serie A",
    "4328": "Premier League",
    "4335": "La Liga",
    "4331": "Bundesliga",
    "4334": "Ligue 1",
    "4480": "Champions League",
    "4481": "Europa League",
    "5007": "Conference League",
    "4490": "UEFA Nations League",
    "4866": "AFC Asian Cup Qualifiers",
}
```

## Installazione

### 1. Clona Repository

```bash
git clone https://github.com/tuo-username/koza-bot.git
cd koza-bot
```

### 2. Crea Ambiente Virtuale

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

### 3. Installa Dipendenze

```bash
pip install -r requirements.txt
```

### 4. Configura API Keys

```bash
cp .env.example .env
# Edita .env con le tue chiavi
```

### 5. Avvia il Bot

```bash
python bot_tg.py
```

**Output Atteso:**
```
🚀 Avvio KOZA Bot 3.0 con Gemini AI...
🔑 GEMINI_API_KEY caricata: AIzaSyC...
🔐 TELEGRAM_TOKEN caricato: 123456...
🤖 Fonte AI: Google Gemini 2.0 Flash

📥 Caricamento database squadre...
✅ Database caricato!
📊 Squadre caricate: 96
🏆 Competizioni: 8

🎯 Bot attivo! Sistema di inline buttons operativo!
```

## Utilizzo

### Comandi Disponibili

| Comando | Descrizione |
|---------|-------------|
| `/start` | Avvia bot, mostra selezione date |
| `/help` | Mostra guida completa |
| `/about` | Info sul bot e tecnologie |
| `/predici` | Modalità manuale |
| `/match` | Alias per /start |

### Flusso Standard

```
1. /start
2. Seleziona data (Oggi/Domani/Dopodomani)
3. Seleziona competizione
4. Clicca partita
5. Leggi analisi AI
6. Clicca "Torna indietro" per altre partite
```

### Modalità Manuale

Scrivi direttamente due squadre:
```
Inter Milan
Juventus Napoli
Real Madrid vs Barcelona
```

## API Integrate

### 1. Google Gemini AI

- **Modello:** Gemini 2.0 Flash
- **Uso:** Analisi partite, generazione pronostici
- **Costo:** Piano gratuito (60 req/min)
- **Fallback:** Analisi statica

### 2. TheSportsDB API

- **Endpoint:** `thesportsdb.com/api/v1/json`
- **Piano:** Gratuito (API key: "123")
- **Dati:** Partite, squadre, competizioni
- **Limitazioni:** Non copre qualificazioni mondiali

### 3. API-Football

- **Piano:** Gratuito (100 req/giorno)
- **Limite:** Solo +3 giorni dalla data corrente
- **Uso:** Statistiche live, forma squadre reali

### 4. Telegram Bot API

- **Framework:** python-telegram-bot v21+
- **Modalità:** Long polling (locale) / Webhook (production)

## Troubleshooting

### Problema: "API_KEY NON TROVATA"

```bash
ls -la .env
cat .env
# Deve essere: GEMINI_API_KEY=AIzaSyC... (senza spazi)
```

### Problema: Bot non trova partite

1. Verifica data in `partite_2026.json`
2. Controlla ID competizione in `LEGHE_PRINCIPALI`
3. Verifica log: `INFO:sportsdb_engine:API-Football: trovate 0 partite`

### Problema: Gemini non risponde

- Rate limit: aspetta 1 minuto
- Chiave invalida: rigenera da Google AI Studio
- Fallback automatico attivo

## Roadmap Futura

- [ ] Database SQLite per storico partite
- [ ] Sistema utenti con abbonamenti (Stripe)
- [ ] Notifiche push pre-partita
- [ ] ML model training
- [ ] Multi-language support
- [ ] Dashboard web admin
- [ ] API pubblica

## Licenza

MIT License

## Autore

**Team KOZA** - Marzo 2026
