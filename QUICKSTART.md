# ⚡ GUIDA RAPIDA - Istruzioni per Iniziare

## 🎯 I 5 Step per Far Funzionare il Bot

### Step 1️⃣: Installa i Pacchetti Python
```bash
pip install -r requirements.txt
```

**Output atteso:**
```
Successfully installed python-telegram-bot-21.0
Successfully installed rapidfuzz-3.0.0
...
```

---

### Step 2️⃣: Ottieni le API Key

#### A) **API-Football** (per dati statistiche)
1. Vai a [https://api-sports.io](https://api-sports.io)
2. Clicca "Register"
3. Completa la registrazione
4. Vai a Dashboard → Copy API Key
5. **Copia il codice alfanumerico**

#### B) **Token Telegram** (per il bot)
1. Apri Telegram
2. Cerca `BotFather`
3. Digita `/start`
4. Digita `/newbot`
5. Dai un nome (es: "KOZA Bot Predictions")
6. Dai uno username (es: "koza_predictions_bot")
7. **Copia il token** (sarà qualcosa come `123456:ABC-DEF...`)

---

### Step 3️⃣: Configura il Bot

Crea un file `.env` nella cartella del progetto:

```
API_KEY=TUA_API_KEY_MOLTO_LUNGA_QUI
TELEGRAM_TOKEN=TUO_BOT_TOKEN_QUI
```

**⚠️ Importante**: I token sono sensibili! Non condividerli pubblicamente.

---

### Step 4️⃣: Testa il Bot (Opzionale)

```bash
python test_logic.py
```

Questo verifica che tutto funziona **senza Telegram**:
- ✅ Database squadre caricate
- ✅ Fuzzy matching funziona
- ✅ Calcoli statistici corretti
- ✅ Output formattato correttamente

---

### Step 5️⃣: Avvia il Bot!

```bash
python bot_tg.py
```

**Output atteso:**
```
🚀 Avvia KOZA Bot...
📥 Caricamento database squadre...
✅ Database caricato!
🎯 Bot attivo! Polling...
```

Il bot è adesso **ONLINE** e pronto! 🚀

---

## 📝 Test rapido

Apri Telegram e manda al tuo bot:
```
/predici Inter Milan
```

Dovresti ricevere un'analisi completa della partita!

---

## 🆘 Problemi Comuni

### ❌ "API_KEY NON TROVATA"
Controlla che il file `.env` sia nella cartella giusta e che il file sia nominato correttamente (`.env` non `.env.txt`)

### ❌ "TELEGRAM_TOKEN NON TROVATO"
Controlla che il token sia incollato correttamente nel file `.env`

### ❌ "No module named 'telegram'"
Esegui: `pip install python-telegram-bot`

### ❌ "Connessione timeout"
Controlla la connessione internet e che l'API-Football funzioni

---

## 🎉 Fatto!

Sei pronto a usare KOZA Bot! 🚀
