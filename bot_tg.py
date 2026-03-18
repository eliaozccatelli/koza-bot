#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import io
from dotenv import load_dotenv

# Carica .env immediatamente
load_dotenv()

# Configura l'encoding UTF-8 per Windows
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import logging
from telegram import Update, ReplyKeyboardRemove
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    ConversationHandler,
)
from logica_koza import KozaEngine
from config import TELEGRAM_TOKEN, LOG_LEVEL

# Configurazione Logging
logging.basicConfig(
    level=LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Istanza globale dell'engine
koza_engine = None


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start - Presenta il bot"""
    messaggio = (
        "⚽ **Benvenuto in KOZA Bot**\n\n"
        "Analizza le partite di calcio e ti do i migliori pronostici!\n\n"
        "📌 **Come usarmi:**\n\n"
        "`/predici Inter Milan`\n"
        "`/predici Juventus Roma 25/03/2026`\n"
        "`/match Liverpool City`\n\n"
        "Puoi scrivere i nomi anche in modo approssimativo:\n"
        "- `inter` invece di `Inter`\n"
        "- `juve` invece di `Juventus`\n"
        "- `ac milan` invece di `AC Milan`\n\n"
        "💡 **Statistiche Complete:**\n"
        "✅ Calcoli da TUTTE le partite della stagione\n"
        "✅ Probabilità 1X2 precise\n"
        "✅ Over/Under\n"
        "✅ BTTS (Gol entrambi)\n"
        "✅ Statistiche cartellini\n"
        "✅ Storico scontri diretti\n"
        "✅ Data della partita (opzionale)\n\n"
        "🔄 Caricamento database squadre..."
    )
    await update.message.reply_text(messaggio, parse_mode='Markdown')


async def predici(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /predici squadra1 squadra2 [data] - Analizza una partita"""
    from datetime import datetime
    
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ Utilizzo: `/predici Inter Milan`\n"
            "         o: `/predici Inter Milan 25/03/2026`\n\n"
            "Inserisci il nome di due squadre separate da spazio.\n"
            "(La data è opzionale formato GG/MM/YYYY)",
            parse_mode='Markdown'
        )
        return

    data_partita = None
    squadra1 = None
    squadra2 = None
    
    full_text = " ".join(context.args)
    
    vs_positions = []
    words = full_text.split()
    for i, word in enumerate(words):
        if word.lower() == "vs" or word.lower() == "vs.":
            vs_positions.append(i)
    
    if vs_positions:
        vs_idx = vs_positions[0]
        squadra1 = " ".join(words[:vs_idx])
        resto = " ".join(words[vs_idx+1:])
        
        ultimo_arg = resto.split()[-1] if resto else ""
        try:
            if '/' in ultimo_arg and len(ultimo_arg) == 10:
                data_partita = datetime.strptime(ultimo_arg, '%d/%m/%Y').date()
                squadra2 = " ".join(resto.split()[:-1])
            else:
                squadra2 = resto
        except:
            squadra2 = resto
    else:
        squadra1 = context.args[0]
        
        ultimo_arg = context.args[-1]
        try:
            if '/' in ultimo_arg and len(ultimo_arg) == 10:
                data_partita = datetime.strptime(ultimo_arg, '%d/%m/%Y').date()
                squadra2 = " ".join(context.args[1:-1])
            else:
                squadra2 = " ".join(context.args[1:])
        except:
            squadra2 = " ".join(context.args[1:])
    
    if not squadra1 or not squadra2 or not squadra1.strip() or not squadra2.strip():
        await update.message.reply_text(
            "⚠️ Utilizzo: `/predici Inter Milan`\n"
            "         o: `/predici Inter vs Milan 25/03/2026`\n\n"
            "Inserisci il nome di due squadre separate da spazio o 'vs'.\n"
            "(La data è opzionale formato GG/MM/YYYY)",
            parse_mode='Markdown'
        )
        return
    
    squadra1 = squadra1.strip()
    squadra2 = squadra2.strip()
    
    await update.message.chat.send_action("typing")
    
    try:
        logger.info(f"📋 Ricerca: {squadra1} vs {squadra2}")
        
        id_casa, nome_casa, comp_casa = koza_engine.trova_squadra(squadra1)
        id_trasf, nome_trasf, comp_trasf = koza_engine.trova_squadra(squadra2)
        
        if not id_casa:
            await update.message.reply_text(
                f"❌ Non trovo la squadra: **{squadra1}**\n\n"
                f"Controlla il nome o prova con una variante.",
                parse_mode='Markdown'
            )
            return
        
        if not id_trasf:
            await update.message.reply_text(
                f"❌ Non trovo la squadra: **{squadra2}**\n\n"
                f"Controlla il nome o prova con una variante.",
                parse_mode='Markdown'
            )
            return
        
        logger.info(f"✅ Trovate: {nome_casa} ({comp_casa}) vs {nome_trasf} ({comp_trasf})")
        
        await update.message.reply_text(
            f"⏳ Sto analizzando **{nome_casa}** vs **{nome_trasf}**...",
            parse_mode='Markdown'
        )
        
        comp_id = koza_engine.team_competitions.get(id_casa)
        
        match_info = koza_engine.trova_prossima_partita(id_casa, id_trasf, data_partita)
        data_messaggio = ""
        
        if match_info.get('found') and match_info.get('data'):
            match_date = match_info['data'].get('date', 'Sconosciuta')
            match_status = match_info['data'].get('status', 'unknown')
            data_messaggio = f"\n📅 **Data**: {match_date}\n📊 **Status**: {match_status}\n"
            
            if match_status in ['FINISHED', 'LIVE']:
                data_messaggio += "⚠️ *Questa partita è già giocata/in corso - Dati precisi*\n"
        else:
            data_messaggio = "\n⚠️ **Partita**: Non trovata fra le prossime in programma\n"
        
        pronostico = koza_engine.calcola_pronostico(
            id_casa, nome_casa,
            id_trasf, nome_trasf,
            comp_id
        )
        
        messaggio = koza_engine.formatta_output(pronostico)
        messaggio = messaggio.replace("🏟 **", data_messaggio + "\n🏟 **", 1)
        await update.message.reply_text(messaggio, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"❌ Errore: {e}")
        import traceback
        traceback.print_exc()
        await update.message.reply_text(
            f"❌ Errore durante l'analisi:\n`{str(e)}`",
            parse_mode='Markdown'
        )


async def match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Alias per /predici - Comando alternativo"""
    await predici(update, context)


async def schedina(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /schedina - Analizza multiple partite"""
    from datetime import datetime
    
    if not context.args or len(context.args) < 3:
        await update.message.reply_text(
            "⚠️ Utilizzo: `/schedina Bayern vs Atalanta | Inter vs Juve | Liverpool vs City`\n\n"
            "Separa le partite con `|` (pipe).\n"
            "Ogni partita: `Squadra1 vs Squadra2 [DD/MM/YYYY]`",
            parse_mode='Markdown'
        )
        return
    
    await update.message.chat.send_action("typing")
    
    try:
        full_text = " ".join(context.args)
        partite_text = full_text.split('|')
        
        if len(partite_text) < 2:
            await update.message.reply_text(
                "⚠️ Inserisci almeno 2 partite separate da `|`\n\n"
                "Esempio:\n`/schedina Bayern vs Atalanta | Inter vs Juve`",
                parse_mode='Markdown'
            )
            return
        
        logger.info(f"📋 Analisi schedina con {len(partite_text)} partite")
        
        pronostici = []
        
        for i, partita_str in enumerate(partite_text):
            partita_str = partita_str.strip()
            if not partita_str:
                continue
            
            words = partita_str.split()
            data_partita = None
            squadra1 = None
            squadra2 = None
            
            vs_positions = []
            for j, word in enumerate(words):
                if word.lower() == "vs" or word.lower() == "vs.":
                    vs_positions.append(j)
            
            if vs_positions:
                vs_idx = vs_positions[0]
                squadra1 = " ".join(words[:vs_idx])
                resto = " ".join(words[vs_idx+1:])
                
                ultimo_arg = resto.split()[-1] if resto else ""
                try:
                    if '/' in ultimo_arg and len(ultimo_arg) == 10:
                        data_partita = datetime.strptime(ultimo_arg, '%d/%m/%Y').date()
                        squadra2 = " ".join(resto.split()[:-1])
                    else:
                        squadra2 = resto
                except:
                    squadra2 = resto
            else:
                squadra1 = words[0] if words else None
                resto = " ".join(words[1:]) if len(words) > 1 else ""
                try:
                    if '/' in resto.split()[-1] if resto else "" and len(resto.split()[-1]) == 10:
                        data_partita = datetime.strptime(resto.split()[-1], '%d/%m/%Y').date()
                        squadra2 = " ".join(resto.split()[:-1])
                    else:
                        squadra2 = resto
                except:
                    squadra2 = resto
            
            if not squadra1 or not squadra2:
                await update.message.reply_text(
                    f"❌ Partita {i+1} non valida: `{partita_str}`",
                    parse_mode='Markdown'
                )
                return
            
            id_casa, nome_casa, comp_casa = koza_engine.trova_squadra(squadra1)
            id_trasf, nome_trasf, comp_trasf = koza_engine.trova_squadra(squadra2)
            
            if not id_casa or not id_trasf:
                await update.message.reply_text(
                    f"❌ Squadra non trovata in partita {i+1}: `{partita_str}`",
                    parse_mode='Markdown'
                )
                return
            
            comp_id = koza_engine.team_competitions.get(id_casa)
            
            pronostico = koza_engine.calcola_pronostico(
                id_casa, nome_casa,
                id_trasf, nome_trasf,
                comp_id
            )
            pronostici.append(pronostico)
        
        schedina_result = koza_engine.calcola_schedina(pronostici)
        
        messaggio = koza_engine.formatta_schedina(schedina_result, importo_scommessa=100)
        await update.message.reply_text(messaggio, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"❌ Errore schedina: {e}")
        import traceback
        traceback.print_exc()
        await update.message.reply_text(
            f"❌ Errore durante l'analisi della schedina:\n`{str(e)}`",
            parse_mode='Markdown'
        )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /help - Mostra l'aiuto"""
    messaggio = (
        "📚 **Guida KOZA Bot**\n\n"
        "**Comandi disponibili:**\n\n"
        "`/predici SQUADRA1 SQUADRA2` - Analizza la prossima partita\n"
        "`/predici SQUADRA1 SQUADRA2 DD/MM/YYYY` - Analizza partita specifica\n"
        "`/schedina MATCH1 | MATCH2 | MATCH3` - Analizza schedule con combo\n"
        "`/match SQUADRA1 SQUADRA2` - Alternative a /predici\n"
        "`/help` - Mostra questo messaggio\n"
        "`/about` - Info sul bot\n\n"
        "**Esempi di utilizzo:**\n\n"
        "`/predici inter milan`\n"
        "`/predici Juventus Roma 25/03/2026`\n"
        "`/schedina Bayern vs Atalanta | Inter vs Juve | Liverpool vs City`\n\n"
        "**Note importanti:**\n"
        "• Scrivi i nomi come vuoi (maiuscole, minuscole, abbreviazioni)\n"
        "• Usa gli spazi tra squadra 1 e squadra 2\n"
        "• La data è opzionale (formato: GG/MM/YYYY)\n"
        "• Per schedine, separa le partite con `|` (pipe)\n"
        "• L'analisi potrebbe richiedere qualche secondo"
    )
    await update.message.reply_text(messaggio, parse_mode='Markdown')


async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /about - Info sul bot"""
    messaggio = (
        "🤖 **KOZA Bot v1.0**\n\n"
        "Analizzatore intelligente di partite di calcio\n"
        "Powered by API-Football & Poisson Distribution\n\n"
        "📊 Fornisce:\n"
        "• Probabilità 1X2\n"
        "• Expected Goals (xG)\n"
        "• Over/Under\n"
        "• BTTS (Both Teams To Score)\n"
        "• Statistiche cartellini\n"
        "• Storico scontri diretti\n\n"
        "👤 Sviluppato dal Team KOZA\n"
        "📅 Marzo 2026"
    )
    await update.message.reply_text(messaggio, parse_mode='Markdown')


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestisce messaggi di testo libero"""
    if not update.message.text.startswith('/'):
        parti = update.message.text.strip().split()
        
        if len(parti) >= 2:
            context.args = parti
            await predici(update, context)
        else:
            await update.message.reply_text(
                "💬 Scrivi due nomi di squadra separate da spazio, oppure usa:\n\n"
                "`/predici Inter Milan`\n"
                "`/help` - Per l'aiuto",
                parse_mode='Markdown'
            )


def main():
    """Avvia il bot"""
    global koza_engine
    
    print("🚀 Avvio KOZA Bot...")
    
    from config import API_KEY, TELEGRAM_TOKEN as TOKEN_CHECK
    print(f"🔑 API_KEY caricata: {API_KEY[:20]}..." if API_KEY else "❌ API_KEY NON TROVATA")
    print(f"🔐 TELEGRAM_TOKEN caricato: {TOKEN_CHECK[:10]}..." if TOKEN_CHECK else "❌ TELEGRAM_TOKEN NON TROVATO")
    print("📊 Fonte API: football-data.org\n")
    
    koza_engine = KozaEngine()
    
    print("📥 Caricamento database squadre...")
    if not koza_engine.carica_database_squadre():
        print("❌ Errore critico: Impossibile connettersi alle API!")
        print("Verifica:")
        print("  • API_KEY valida in config.py")
        print("  • Connessione internet")
        print("  • Cota API non superata")
        return
    
    print("✅ Database caricato!")
    
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("about", about))
    app.add_handler(CommandHandler("predici", predici))
    app.add_handler(CommandHandler("match", match))
    app.add_handler(CommandHandler("schedina", schedina))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("🎯 Bot attivo! Polling...")
    print("Premi CTRL+C per fermare\n")
    
    try:
        app.run_polling()
    except KeyboardInterrupt:
        print("\n\n⛔ Bot fermato.")


if __name__ == '__main__':
    main()
