#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import io
from dotenv import load_dotenv

load_dotenv()

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import logging
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from logica_koza import KozaEngine
from config import TELEGRAM_TOKEN, LOG_LEVEL

logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

koza_engine = None


# ==================== INLINE BUTTONS SYSTEM ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start con inline buttons per campionati"""
    messaggio = (
        "⚽ **KOZA Bot 2.0** 🚀\n\n"
        "Scegli un campionato per analizzare le partite di oggi.\n\n"
        "📅 **Data**: " + datetime.now().strftime('%d/%m/%Y')
    )
    
    try:
        campionati = koza_engine.get_competizioni_con_partite()
        
        if not campionati:
            await update.message.reply_text("⚠️ **Nessuna partita oggi**", parse_mode='Markdown')
            return
        
        keyboard = []
        for comp_id, comp_name in campionati:
            keyboard.append([
                InlineKeyboardButton(f"⚽ {comp_name}", callback_data=f"comp_{comp_id}")
            ])
        
        keyboard.append([
            InlineKeyboardButton("✏️ Scrivi manualmente", callback_data="scrivi_manuale")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(messaggio, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Errore in start: {e}")
        await update.message.reply_text(f"❌ Errore: `{str(e)}`", parse_mode='Markdown')


async def button_campionato(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestisce il click su un campionato"""
    query = update.callback_query
    await query.answer()
    
    try:
        if query.data == "scrivi_manuale":
            await query.edit_message_text(
                "✏️ **Scrivi due squadre separate da spazio:**\n\n"
                "`Inter Milan`\n"
                "`Bayern Atalanta`\n\n"
                "Oppure con 'vs': `Inter vs Milan`",
                parse_mode='Markdown'
            )
            return
        
        comp_id = int(query.data.split("_")[1])
        partite = koza_engine.get_partite_campionato(comp_id)
        
        if not partite:
            await query.edit_message_text("⚠️ Nessuna partita in questo campionato oggi")
            return
        
        comp_name = koza_engine.competitions.get(comp_id, "Campionato")
        messaggio = f"⚽ **{comp_name}** ({datetime.now().strftime('%d/%m/%Y')})\n\nScegli una partita:\n"
        
        keyboard = []
        for team1, team2, match_id in partite:
            keyboard.append([
                InlineKeyboardButton(
                    f"🔥 {team1} vs {team2}",
                    callback_data=f"match_{match_id}_{team1}_{team2}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton("◀️ Indietro", callback_data="back_campionati")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(messaggio, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Errore in button_campionato: {e}")
        await query.edit_message_text(f"❌ Errore: `{str(e)}`", parse_mode='Markdown')


async def button_partita(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestisce il click su una partita"""
    query = update.callback_query
    await query.answer("⏳ Analizzando...")
    
    try:
        parts = query.data.split("_", 3)
        if len(parts) < 4:
            await query.edit_message_text("❌ Errore nel parsing")
            return
        
        squadra1 = parts[2]
        squadra2 = parts[3]
        
        id_casa, nome_casa, comp_casa = koza_engine.trova_squadra(squadra1)
        id_trasf, nome_trasf, comp_trasf = koza_engine.trova_squadra(squadra2)
        
        if not id_casa or not id_trasf:
            await query.edit_message_text(
                f"❌ **SQUADRA NON TROVATA**\n\n"
                f"Verifica i nomi e riprova.",
                parse_mode='Markdown'
            )
            return
        
        comp_id = koza_engine.team_competitions.get(id_casa)
        
        match_info = koza_engine.trova_prossima_partita(id_casa, id_trasf)
        if not match_info.get('found'):
            await query.edit_message_text(
                f"❌ **PARTITA NON TROVATA**\n\n"
                f"La partita {nome_casa} vs {nome_trasf} non è in programma.",
                parse_mode='Markdown'
            )
            return
        
        pronostico = koza_engine.calcola_pronostico(id_casa, nome_casa, id_trasf, nome_trasf, comp_id)
        messaggio = koza_engine.formatta_output(pronostico)
        
        await query.edit_message_text(messaggio, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Errore in button_partita: {e}")
        await query.edit_message_text(f"❌ Errore: `{str(e)}`", parse_mode='Markdown')


async def button_indietro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Torna ai campionati"""
    query = update.callback_query
    await query.answer()
    
    await start(update, context)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestisce testo libero per ricerca manuale"""
    text = update.message.text.strip()
    parti = text.split()
    
    if len(parti) < 2:
        await update.message.reply_text(
            "💬 Scrivi due squadre separate da spazio:\n`Inter Milan`",
            parse_mode='Markdown'
        )
        return
    
    squadra1 = None
    squadra2 = None
    
    vs_positions = [i for i, w in enumerate(parti) if w.lower() in ["vs", "vs."]]
    
    if vs_positions:
        vs_idx = vs_positions[0]
        squadra1 = " ".join(parti[:vs_idx])
        squadra2 = " ".join(parti[vs_idx+1:])
    else:
        squadra1 = parti[0]
        squadra2 = " ".join(parti[1:])
    
    if not squadra1 or not squadra2:
        await update.message.reply_text("❌ Formato errato", parse_mode='Markdown')
        return
    
    await update.message.chat.send_action("typing")
    
    try:
        id_casa, nome_casa, comp_casa = koza_engine.trova_squadra(squadra1)
        id_trasf, nome_trasf, comp_trasf = koza_engine.trova_squadra(squadra2)
        
        if not id_casa:
            await update.message.reply_text(
                f"❌ **SQUADRA NON TROVATA**\n\n{squadra1}",
                parse_mode='Markdown'
            )
            return
        
        if not id_trasf:
            await update.message.reply_text(
                f"❌ **SQUADRA NON TROVATA**\n\n{squadra2}",
                parse_mode='Markdown'
            )
            return
        
        comp_id = koza_engine.team_competitions.get(id_casa)
        
        match_info = koza_engine.trova_prossima_partita(id_casa, id_trasf)
        if not match_info.get('found'):
            await update.message.reply_text(
                f"❌ **PARTITA NON TROVATA**\n\n"
                f"La partita {nome_casa} vs {nome_trasf} non è in programma.",
                parse_mode='Markdown'
            )
            return
        
        pronostico = koza_engine.calcola_pronostico(id_casa, nome_casa, id_trasf, nome_trasf, comp_id)
        messaggio = koza_engine.formatta_output(pronostico)
        await update.message.reply_text(messaggio, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Errore: {e}")
        await update.message.reply_text(f"❌ Errore:\n`{str(e)}`", parse_mode='Markdown')


async def predici(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /predici - DEPRECATED (usa /start)"""
    await update.message.reply_text(
        "⚠️ Usa `/start` per il menu interattivo con pulsanti!",
        parse_mode='Markdown'
    )


async def match(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Alias per /start"""
    await start(update, context)


async def schedina(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /schedina - Placeholder"""
    await update.message.reply_text(
        "📋 Schedina: Usa `/start` per ora.\n\nSchedula verrà aggiornata!",
        parse_mode='Markdown'
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /help"""
    messaggio = (
        "📚 **Guida KOZA Bot 2.0**\n\n"
        "**Modalità Interattiva:**\n"
        "`/start` - Menu campionati con pulsanti\n\n"
        "**Modalità Manual:**\n"
        "`Inter Milan` - Scrivi due squadre\n\n"
        "**Comandi:**\n"
        "`/help` - Questo messaggio\n"
        "`/about` - Info sul bot"
    )
    await update.message.reply_text(messaggio, parse_mode='Markdown')


async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /about"""
    messaggio = (
        "🤖 **KOZA Bot 2.0**\n\n"
        "Sistema intelligente con inline buttons\n"
        "Analisi calcistica avanzata\n\n"
        "📊 Funzionalità:\n"
        "✅ Pulsanti interattivi\n"
        "✅ Partite LIVE\n"
        "✅ Poisson Distribution\n"
        "✅ Expected Goals\n\n"
        "👤 Team KOZA - Marzo 2026"
    )
    await update.message.reply_text(messaggio, parse_mode='Markdown')


def main():
    """Avvia il bot"""
    global koza_engine
    
    print("🚀 Avvio KOZA Bot 2.0 con Inline Buttons...")
    
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
    print(f"📊 Squadre caricate: {len(koza_engine.teams_cache)}")
    print(f"🏆 Competizioni: {len(koza_engine.competitions)}\n")
    
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("about", about))
    app.add_handler(CommandHandler("predici", predici))
    app.add_handler(CommandHandler("match", match))
    app.add_handler(CommandHandler("schedina", schedina))
    
    # Callback handlers per inline buttons
    app.add_handler(CallbackQueryHandler(button_campionato, pattern="^comp_"))
    app.add_handler(CallbackQueryHandler(button_partita, pattern="^match_"))
    app.add_handler(CallbackQueryHandler(button_indietro, pattern="^back_campionati$"))
    app.add_handler(CallbackQueryHandler(lambda u, c: button_campionato(u, c), pattern="^scrivi_manuale$"))
    
    # Message handler per testo libero
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("🎯 Bot attivo! Sistema di inline buttons operativo!")
    print("Premi CTRL+C per fermare\n")
    
    try:
        app.run_polling()
    except KeyboardInterrupt:
        print("\nBot fermato.")


if __name__ == '__main__':
    main()
