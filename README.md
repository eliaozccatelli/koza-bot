# ⚽ KOZA Bot - Telegram Football Predictor

Bot Telegram intelligente per l'analisi e le previsioni delle partite di calcio con **fuzzy matching**, **expected goals** e **probabilità Poisson**.

## 🌟 Caratteristiche

✅ **Riconoscimento squadre intelligente** - Capisce le squadre anche scritte male
✅ **Analisi real-time** - Dati aggiornati da API-Football  
✅ **Distribuzioni Poisson** - Calcoli probabilistici avanzati  
✅ **Pronostici completi**:
  - Probabilità 1X2
  - Expected Goals (xG)
  - Over/Under 2.5 e 3.5
  - BTTS (Gol di entrambe)
  - Cartellini e statistiche
  - Storico scontri diretti

## 📥 Installazione

### 1. Dipendenze
```bash
pip install -r requirements.txt
```

### 2. Configurazione
Crea un file `.env` nella cartella del progetto:

```
API_KEY=TUA_API_KEY_QUI
TELEGRAM_TOKEN=TUO_BOT_TOKEN
```

### 3. Come ottenere le credenziali

**API-Football:**
1. Vai su [api-sports.io](https://api-sports.io)
2. Registrati e copia la API Key

**Token Telegram:**
1. Apri Telegram
2. Cerca `BotFather`
3. Invia `/start` e `/newbot`
4. Copia il token

## 🚀 Utilizzo

### Avvia il bot
```bash
python bot_tg.py
```

### Comandi disponibili

`/predici Inter Milan` - Analizza la prossima partita
`/predici Inter Milan 25/03/2026` - Analizza partita specifica
`/schedina Bayern vs Atalanta | Inter vs Juve` - Analizza multiple partite
`/help` - Mostra l'aiuto
`/about` - Info sul bot

## 📊 Interpretazione dei risultati

- **1️⃣ Vittoria Casa** = Probabilità che la squadra di casa vinca
- **2️⃣ Vittoria Trasferta** = Probabilità che la squadra in trasferta vinca
- **❌ Pareggio** = Probabilità di pareggio
- **🔥 Over 2.5** = Probabilità di 3+ gol
- **🥅 BTTS** = Probabilità che entrambe le squadre segnino

## 🔐 Sicurezza

⚠️ **IMPORTANTE**: Non committare mai il file `.env` con le credenziali su GitHub!

Il file `.gitignore` è già configurato per bloccare automaticamente `.env`.

## 📝 Licenza

MIT License - Vedi LICENSE per dettagli

## 👤 Autore

Team KOZA - Marzo 2026
