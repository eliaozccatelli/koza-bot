#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import io
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv

load_dotenv()

# Health check server per Daki.cc
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'KOZA Bot is running!')
    
    def log_message(self, format, *args):
        pass  # Silenzia i log del server HTTP

def start_health_server():
    port = int(os.getenv('PORT', 8080))
    server = HTTPServer(('0.0.0.0', port), HealthHandler)
    print(f"🌐 Health check server avviato sulla porta {port}")
    server.serve_forever()

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
from logica_koza import KozaEngine, get_koza_engine
from config import TELEGRAM_TOKEN, LOG_LEVEL, GEMINI_API_KEY
from message_parser import process_message, parse_all_matches_in_message

logging.basicConfig(level=LOG_LEVEL, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

koza_engine = None


def get_date_buttons():
    """Genera i 3 pulsanti per la selezione della data."""
    oggi = datetime.now().date()
    domani = oggi + timedelta(days=1)
    dopodomani = oggi + timedelta(days=2)
    
    giorni_settimana = ['Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'Sabato', 'Domenica']
    
    return [
        InlineKeyboardButton(
            f"📅 Oggi ({oggi.strftime('%d/%m')}) - {giorni_settimana[oggi.weekday()]}",
            callback_data=f"date_{oggi.isoformat()}"
        ),
        InlineKeyboardButton(
            f"📅 Domani ({domani.strftime('%d/%m')}) - {giorni_settimana[domani.weekday()]}",
            callback_data=f"date_{domani.isoformat()}"
        ),
        InlineKeyboardButton(
            f"📅 Dopodomani ({dopodomani.strftime('%d/%m')}) - {giorni_settimana[dopodomani.weekday()]}",
            callback_data=f"date_{dopodomani.isoformat()}"
        ),
    ]


# ==================== INLINE BUTTONS SYSTEM ====================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /start - mostra selezione data"""
    messaggio = (
        "⚽ **KOZA Bot 3.0** 🤖\n\n"
        "Seleziona una data per vedere le partite disponibili:"
    )
    
    try:
        date_buttons = get_date_buttons()
        
        keyboard = [[btn] for btn in date_buttons]
        keyboard.append([
            InlineKeyboardButton("✏️ Scrivi manualmente", callback_data="scrivi_manuale")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.message:
            await update.message.reply_text(messaggio, reply_markup=reply_markup, parse_mode='Markdown')
        elif update.callback_query:
            await update.callback_query.edit_message_text(messaggio, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Errore in start: {e}")
        text = f"❌ Errore: `{str(e)}`"
        if update.message:
            await update.message.reply_text(text, parse_mode='Markdown')
        elif update.callback_query:
            await update.callback_query.edit_message_text(text, parse_mode='Markdown')


async def button_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestisce il click su una data - mostra competizioni"""
    query = update.callback_query
    await query.answer()
    
    try:
        # Estrai data dal callback_data (formato: date_YYYY-MM-DD)
        data_str = query.data.split("_")[1]
        selected_date = datetime.fromisoformat(data_str).date()
        
        # Salva data nel context per usarla nei prossimi step
        context.user_data['selected_date'] = selected_date
        context.user_data['selected_date_str'] = selected_date.strftime('%d/%m/%Y')
        
        # Recupera competizioni per questa data
        campionati = koza_engine.get_competizioni_con_partite(selected_date)
        
        if not campionati:
            keyboard = [[InlineKeyboardButton("◀️ Torna indietro", callback_data="back_date")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"⚠️ **Nessuna partita disponibile** il {selected_date.strftime('%d/%m/%Y')}",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return
        
        messaggio = f"📅 **Data selezionata**: {selected_date.strftime('%d/%m/%Y')}\n\nScegli un campionato:"
        
        keyboard = []
        for comp_id, comp_name in campionati:
            keyboard.append([
                InlineKeyboardButton(f"⚽ {comp_name}", callback_data=f"comp_{comp_id}_{data_str}")
            ])
        
        keyboard.append([
            InlineKeyboardButton("◀️ Torna alle date", callback_data="back_date")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(messaggio, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Errore in button_data: {e}")
        await query.edit_message_text(f"❌ Errore: `{str(e)}`", parse_mode='Markdown')


async def button_campionato(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestisce il click su un campionato - mostra partite"""
    query = update.callback_query
    await query.answer()
    
    try:
        # Estrai comp_id e data dal callback_data (formato: comp_COMPID_YYYY-MM-DD)
        parts = query.data.split("_")
        comp_id = parts[1]  # ID è stringa (es: "IT1", "EN1")
        data_str = parts[2] if len(parts) > 2 else None
        selected_date = datetime.fromisoformat(data_str).date() if data_str else datetime.now().date()
        
        partite = koza_engine.get_partite_campionato(comp_id, selected_date)
        
        if not partite:
            keyboard = [[InlineKeyboardButton("◀️ Indietro", callback_data=f"back_comp_{data_str}" if data_str else "back_date")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"⚠️ Nessuna partita in questo campionato il {selected_date.strftime('%d/%m/%Y')}",
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            return
        
        comp_name = koza_engine.competitions.get(comp_id, "Campionato")
        messaggio = f"⚽ **{comp_name}** ({selected_date.strftime('%d/%m/%Y')})\n\nScegli una partita:\n"
        
        keyboard = []
        for team1, team2, match_id in partite:
            # Salva info partita nel context per recuperarla dopo
            # Converti match_id in stringa per consistenza con callback_data
            match_id_str = str(match_id)
            if 'partite_disponibili' not in context.user_data:
                context.user_data['partite_disponibili'] = {}
            context.user_data['partite_disponibili'][match_id_str] = {
                'casa': team1,
                'trasferta': team2
            }
            keyboard.append([
                InlineKeyboardButton(
                    f"🔥 {team1} vs {team2}",
                    callback_data=f"match_{match_id_str}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton("◀️ Torna ai campionati", callback_data=f"back_comp_{data_str}" if data_str else "back_date")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(messaggio, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Errore in button_campionato: {e}")
        await query.edit_message_text(f"❌ Errore: `{str(e)}`", parse_mode='Markdown')


async def button_scrivi_manuale(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestisce il click su 'Scrivi manualmente'"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "✏️ **Scrivi due squadre separate da spazio:**\n\n"
        "`Inter Milan`\n"
        "`Bayern Atalanta`\n\n"
        "Oppure con 'vs': `Inter vs Milan`",
        parse_mode='Markdown'
    )


async def button_partita(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestisce il click su una partita - usa Gemini AI"""
    query = update.callback_query
    await query.answer("⏳ Analizzo con Gemini AI...")
    
    try:
        # Estrai match_id dal callback_data (formato: match_MATCHID)
        parts = query.data.split("_", 1)
        if len(parts) < 2:
            await query.edit_message_text("❌ Errore nel parsing")
            return
        
        match_id = parts[1]
        
        # Recupera nomi squadre dal context
        partite_cache = context.user_data.get('partite_disponibili', {})
        partita_info = partite_cache.get(match_id, {})
        
        if partita_info:
            squadra1 = partita_info['casa']
            squadra2 = partita_info['trasferta']
        else:
            # Fallback: estrai dal match_id (formato: IT1_1)
            squadra1 = "Casa"
            squadra2 = "Trasferta"
        
        # Salva info per il back button
        context.user_data['last_match_id'] = match_id
        context.user_data['last_squadra1'] = squadra1
        context.user_data['last_squadra2'] = squadra2
        
        # Usa il nuovo sistema live con match_id
        live_data = koza_engine.get_analisi_partita_live(squadra1, squadra2, match_id)
        messaggio = koza_engine.formatta_output_live(live_data)
        
        # Aggiungi pulsante per tornare indietro
        keyboard = [[InlineKeyboardButton("◀️ Torna indietro", callback_data=f"back_match_{match_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Invia senza Markdown per evitare errori di parsing
        await query.edit_message_text(messaggio, reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"Errore in button_partita: {e}")
        await query.edit_message_text(f"❌ Errore: `{str(e)}`", parse_mode='Markdown')


async def button_indietro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestisce i pulsanti indietro (back_date, back_comp_*, back_match_*)"""
    query = update.callback_query
    await query.answer()
    
    try:
        if query.data == "back_date":
            # Torna alla selezione date
            await start(update, context)
        elif query.data.startswith("back_comp_"):
            # Torna alle competizioni di una specifica data
            parts = query.data.split("_")
            if len(parts) >= 3:
                data_str = parts[2]
                # Verifica che la data sia valida
                try:
                    datetime.fromisoformat(data_str).date()
                    # Simula click sulla data
                    query.data = f"date_{data_str}"
                    await button_data(update, context)
                except ValueError:
                    # Data invalida, torna a start
                    await start(update, context)
            else:
                # Formato callback invalido, torna a start
                await start(update, context)
        elif query.data.startswith("back_match_"):
            # Invia NUOVO messaggio con pulsanti date (lascia analisi visibile)
            messaggio = (
                "⚽ **KOZA Bot 3.0** 🤖\n\n"
                "Seleziona una nuova data per vedere altre partite:"
            )
            
            date_buttons = get_date_buttons()
            keyboard = [[btn] for btn in date_buttons]
            keyboard.append([
                InlineKeyboardButton("✏️ Scrivi manualmente", callback_data="scrivi_manuale")
            ])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Invia come NUOVO messaggio (non edit) così l'analisi rimane
            await query.message.reply_text(messaggio, reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Errore in button_indietro: {e}")
        # In caso di errore, torna sempre alla schermata iniziale
        try:
            await start(update, context)
        except:
            await query.edit_message_text(f"❌ Errore: `{str(e)}`", parse_mode='Markdown')


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestisce testo libero per ricerca manuale - usa Gemini AI"""
    # Controllo sicurezza: update.message può essere None
    if not update or not update.message or not update.message.text:
        return
    
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
        # Usa direttamente Gemini AI per analizzare
        analisi = koza_engine.analizza_partita(squadra1, squadra2)
        analisi["squadra_casa"] = squadra1
        analisi["squadra_trasferta"] = squadra2
        messaggio = koza_engine.formatta_output(analisi)
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


async def debug_all_updates(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Debug: logga tutti gli update per capire cosa riceve il bot."""
    try:
        if update.message:
            chat_type = update.message.chat.type if update.message.chat else "unknown"
            chat_title = update.message.chat.title if update.message.chat else "private"
            text = update.message.text or update.message.caption or "[no text]"
            logger.info(f"🔍 DEBUG UPDATE: chat_type={chat_type}, title={chat_title}, text={text[:30]}...")
    except Exception as e:
        logger.error(f"🔍 DEBUG ERROR: {e}")


async def capture_group_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cattura tutti i messaggi dai gruppi/canali per analisi."""
    message = update.message
    # Supporta sia gruppi che canali
    if not message or message.chat.type not in ['group', 'supergroup', 'channel']:
        return
    
    chat_id = message.chat.id
    chat_title = message.chat.title or "Sconosciuto"
    user = message.from_user.username or message.from_user.first_name or "Anonimo" if message.from_user else "Canale"
    text = message.text or message.caption or ""
    
    # Log del messaggio
    logger.info(f"📩 Gruppo/Canale '{chat_title}' | {user}: {text[:50]}...")
    
    # Salva su file per analisi
    timestamp = datetime.now().isoformat()
    with open("group_messages.log", "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {chat_title} | {user}: {text}\n")
    
    # 🆕 PARSING AUTOMATICO: Prova a estrarre TUTTE le partite dal messaggio
    try:
        results = process_message(text)
        if results:
            for result in results:
                logger.info(f"✅ Partita parsata: {result['match_desc']} ({result['result']}) - Conf: {result['confidence']}")
    except Exception as e:
        logger.error(f"Errore parsing messaggio: {e}")


async def capture_group_photos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cattura foto dai gruppi/canali (es. formazioni, quote)."""
    message = update.message
    # Supporta sia gruppi che canali
    if not message or message.chat.type not in ['group', 'supergroup', 'channel']:
        return
    
    if not message.photo:
        return
    
    chat_title = message.chat.title or "Sconosciuto"
    user = message.from_user.username or message.from_user.first_name or "Anonimo"
    
    # Scarica la foto migliore (ultima nella lista = più grande)
    photo = message.photo[-1]
    file_id = photo.file_id
    
    logger.info(f"📸 Foto da '{chat_title}' | {user} | file_id: {file_id}")
    
    # Salva info foto
    timestamp = datetime.now().isoformat()
    caption = message.caption or ""
    with open("group_photos.log", "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] {chat_title} | {user} | caption: {caption} | file_id: {file_id}\n")
    
    # Opzionale: scarica e analizza con Gemini Vision
    if caption and ("formazione" in caption.lower() or "quote" in caption.lower()):
        try:
            file = await photo.get_file()
            # Qui puoi aggiungere analisi Gemini Vision
            logger.info(f"🔍 Foto rilevante scaricata: {file.file_path}")
        except Exception as e:
            logger.error(f"Errore download foto: {e}")


async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /about"""
    messaggio = (
        "🤖 **KOZA Bot 3.0 - Gemini Edition**\n\n"
        "Sistema di analisi calcistica basato su AI\n"
        "Powered by Google Gemini 2.0 Flash\n\n"
        "📊 Funzionalità:\n"
        "✅ Analisi AI in tempo reale\n"
        "✅ Pronostici con confidence score\n"
        "✅ Forma squadre e assenti\n"
        "✅ Scommesse consigliate con quote\n"
        "✅ Pulsanti interattivi\n\n"
        "👤 Team KOZA - 2026"
    )
    await update.message.reply_text(messaggio, parse_mode='Markdown')


def main():
    """Avvia il bot"""
    global koza_engine
    
    # Avvia health check server per Daki.cc (in un thread separato)
    health_thread = threading.Thread(target=start_health_server, daemon=True)
    health_thread.start()
    
    print("🚀 Avvio KOZA Bot 3.0 con Gemini AI...")
    
    from config import GEMINI_API_KEY, TELEGRAM_TOKEN as TOKEN_CHECK
    print(f"🔑 GEMINI_API_KEY caricata: {GEMINI_API_KEY[:20]}..." if GEMINI_API_KEY else "❌ GEMINI_API_KEY NON TROVATA")
    print(f"🔐 TELEGRAM_TOKEN caricato: {TOKEN_CHECK[:10]}..." if TOKEN_CHECK else "❌ TELEGRAM_TOKEN NON TROVATO")
    print("🤖 Fonte AI: Google Gemini 2.0 Flash\n")
    
    koza_engine = get_koza_engine()
    
    print("📥 Caricamento database squadre...")
    if not koza_engine.carica_database_squadre():
        print("⚠️ Impossibile caricare il database squadre.")
        print("   Il bot parte comunque: puoi usare la modalità manuale (scrivi i nomi delle squadre).")
    
    print("✅ Database caricato!")
    print(f"📊 Squadre caricate: {len(koza_engine.teams_cache)}")
    print(f"🏆 Competizioni: {len(koza_engine.competitions)}\n")
    
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # 🆕 DEBUG: Handler per loggare TUTTI gli update (prima di tutti gli altri)
    app.add_handler(MessageHandler(filters.ALL, debug_all_updates), group=-1)
    
    # 🆕 Handler per catturare messaggi dai gruppi/canali (PRIMA di handle_text)
    app.add_handler(MessageHandler(
        (filters.ChatType.GROUPS | filters.ChatType.CHANNEL) & filters.TEXT, 
        capture_group_messages
    ))
    
    # 🆕 Handler per catturare foto dai gruppi/canali
    app.add_handler(MessageHandler(
        (filters.ChatType.GROUPS | filters.ChatType.CHANNEL) & filters.PHOTO, 
        capture_group_photos
    ))
    
    # Command handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("about", about))
    app.add_handler(CommandHandler("predici", predici))
    app.add_handler(CommandHandler("match", match))
    app.add_handler(CommandHandler("schedina", schedina))
    
    # Callback handlers per inline buttons
    app.add_handler(CallbackQueryHandler(button_data, pattern="^date_"))
    app.add_handler(CallbackQueryHandler(button_campionato, pattern="^comp_"))
    app.add_handler(CallbackQueryHandler(button_partita, pattern="^match_"))
    app.add_handler(CallbackQueryHandler(button_indietro, pattern="^back_"))
    app.add_handler(CallbackQueryHandler(button_scrivi_manuale, pattern="^scrivi_manuale$"))
    
    # Message handler per testo libero (DOPO capture_group_messages)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    
    print("🎯 Bot attivo! Sistema di inline buttons operativo!")
    print("Premi CTRL+C per fermare\n")
    
    try:
        app.run_polling()
    except KeyboardInterrupt:
        print("\nBot fermato.")


if __name__ == '__main__':
    main()
