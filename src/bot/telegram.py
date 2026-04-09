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
import os
import subprocess
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import BadRequest
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from src.core.logica_koza import KozaEngine, get_koza_engine
from src.core.config import TELEGRAM_TOKEN, LOG_LEVEL, GEMINI_API_KEY

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
        "👑 **KOZA Bot** ⚽\n\n"
        "Seleziona una data per vedere le partite disponibili:\n\n"
        "✨ _L'intelligenza artificiale al servizio dello sport_"
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
        
    except BadRequest as e:
        if "Message is not modified" in str(e):
            return
        logger.error(f"Errore in button_data: {e}")
        await query.edit_message_text(f"❌ Errore: `{str(e)}`", parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Errore in button_data: {e}")
        await query.edit_message_text(f"❌ Errore: `{str(e)}`", parse_mode='Markdown')


async def button_campionato(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestisce il click su un campionato - mostra partite"""
    query = update.callback_query
    await query.answer()
    
    try:
        # Estrai comp_id e data dal callback_data (formato: comp_COMPID_YYYY-MM-DD)
        # ATTENZIONE: comp_id può contenere underscore (es: WCQ_EUR)
        parts = query.data.split("_")
        # Format: comp_[COMP_ID]_[DATE] dove DATE è YYYY-MM-DD
        # Quindi prendiamo tutto tra "comp_" e l'ultimo underscore (la data)
        data_str = parts[-1] if len(parts) >= 3 else None
        comp_id = "_".join(parts[1:-1])  # Tutto tra comp_ e la data
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
        for team1, team2, match_id, api_source in partite:
            match_id = str(match_id)  # Normalizza a stringa per coerenza con callback_data
            # Salva info partita nel context per recuperarla dopo
            if 'partite_disponibili' not in context.user_data:
                context.user_data['partite_disponibili'] = {}
            context.user_data['partite_disponibili'][match_id] = {
                'casa': team1,
                'trasferta': team2,
                'api_source': api_source,
            }
            keyboard.append([
                InlineKeyboardButton(
                    f"🔥 {team1} vs {team2}",
                    callback_data=f"match_{match_id}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton("◀️ Torna ai campionati", callback_data=f"back_comp_{data_str}" if data_str else "back_date")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(messaggio, reply_markup=reply_markup, parse_mode='Markdown')
        
    except BadRequest as e:
        if "Message is not modified" in str(e):
            return  # Ignora: il messaggio è già aggiornato
        logger.error(f"Errore in button_campionato: {e}")
        await query.edit_message_text(f"❌ Errore: `{str(e)}`", parse_mode='Markdown')
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
        # Recupera data selezionata se disponibile
        selected_date = context.user_data.get('selected_date')
        
        # Analisi smart: rileva automaticamente se live/finita/programmata
        analisi = koza_engine.analizza_partita_smart(squadra1, squadra2, match_id=match_id, data=selected_date)
        analisi["squadra_casa"] = squadra1
        analisi["squadra_trasferta"] = squadra2
        messaggio = koza_engine.formatta_output(analisi)
        
        # Aggiungi pulsante "Torna indietro"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Torna indietro", callback_data="back_date")]
        ])
        
        # Invia come nuovo messaggio (l'analisi rimane in chat)
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text=messaggio,
            reply_markup=keyboard,
            parse_mode='Markdown'
        )
        
        # Rispondi alla callback query per rimuovere il "loading"
        await query.answer()
        
    except Exception as e:
        import traceback
        logger.error(f"Errore in button_partita: {e}\n{traceback.format_exc()}")
        await query.edit_message_text(f"❌ Errore: `{str(e)}`", parse_mode='Markdown')


async def button_indietro(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestisce i pulsanti indietro (back_date, back_comp_*)."""
    query = update.callback_query
    await query.answer()
    
    logger.info(f"button_indietro chiamato con data: {query.data}")
    
    try:
        if query.data == "back_date":
            logger.info("Torno al menu date (back_date)")
            # Invia nuovo messaggio con menu date (lascia l'analisi in chat)
            messaggio = (
                "👑 **KOZA Bot** ⚽\n\n"
                "Seleziona una data per vedere le partite disponibili:\n\n"
                "✨ _L'intelligenza artificiale al servizio dello sport_"
            )
            
            date_buttons = get_date_buttons()
            keyboard = [[btn] for btn in date_buttons]
            keyboard.append([
                InlineKeyboardButton("✏️ Scrivi manualmente", callback_data="scrivi_manuale")
            ])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await context.bot.send_message(
                chat_id=query.message.chat_id,
                text=messaggio,
                reply_markup=reply_markup,
                parse_mode='Markdown'
            )
            logger.info("Menu date inviato con successo")
            
        elif query.data.startswith("back_comp_"):
            logger.info(f"Torno alle competizioni: {query.data}")
            # Torna alle competizioni di una specifica data
            data_str = query.data.replace("back_comp_", "")
            selected_date = datetime.fromisoformat(data_str).date()

            context.user_data['selected_date'] = selected_date
            context.user_data['selected_date_str'] = selected_date.strftime('%d/%m/%Y')

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
            
    except BadRequest as e:
        if "Message is not modified" in str(e):
            return
        logger.error(f"Errore in button_indietro: {e}", exc_info=True)
        try:
            await query.edit_message_text(f"❌ Errore: `{str(e)}`", parse_mode='Markdown')
        except:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"❌ Errore: `{str(e)}`",
                parse_mode='Markdown'
            )
    except Exception as e:
        logger.error(f"Errore in button_indietro: {e}", exc_info=True)
        try:
            await query.edit_message_text(f"❌ Errore: `{str(e)}`", parse_mode='Markdown')
        except:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=f"❌ Errore: `{str(e)}`",
                parse_mode='Markdown'
            )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Gestisce testo libero: parsa risultati partite O ricerca manuale."""
    text = update.message.text.strip()

    # Prova a parsare risultati partite (es: "Inter-Roma 2-1", "Napoli vs Milan 0-0")
    from src.utils.message_parser import process_message
    parsed = process_message(text)
    if parsed:
        # Risultati trovati e salvati in parsed_matches.csv
        lines = []
        for m in parsed['all_results']:
            lines.append(f"  {m['home_team']} {m['home_goals']}-{m['away_goals']} {m['away_team']} ({m['result']})")
        saved = parsed['saved_count']
        skipped = parsed['skipped']
        total = len(parsed['all_results'])
        msg = f"✅ **{total} risultat{'o' if total==1 else 'i'} trovat{'o' if total==1 else 'i'}**:\n" + "\n".join(lines)
        if saved > 0:
            msg += f"\n\n_💾 {saved} salvat{'o' if saved==1 else 'i'} per ML e forma squadre._"
        if skipped > 0:
            msg += f"\n_⏭️ {skipped} duplicat{'o' if skipped==1 else 'i'} ignorat{'o' if skipped==1 else 'i'}._"
        await update.message.reply_text(msg, parse_mode='Markdown')
        # Pulisci cache forma cosi' i nuovi dati vengono usati subito
        from src.utils.team_form_bridge import clear_cache
        clear_cache()
        return

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
    
    print("🚀 Avvio KOZA Bot 3.0 con Gemini AI...")

    # --- AUTO-UPDATE STARTUP ---
    # Controlla se parsed_matches.csv è vecchio (più di 12 ore) e aggiorna
    try:
        csv_path = 'parsed_matches.csv'
        run_scraper = False
        if not os.path.exists(csv_path):
            run_scraper = True
        else:
            mtime = os.path.getmtime(csv_path)
            last_update = datetime.fromtimestamp(mtime)
            if datetime.now() - last_update > timedelta(hours=12):
                run_scraper = True

        if run_scraper:
            print("📅 Dati risultati non aggiornati. Avvio scraper automatico (ultimi 30 giorni)...")
            subprocess.run([sys.executable, "scripts/scrape_results.py", "--days", "30"], capture_output=True)
            print("✅ Risultati aggiornati all'avvio!")
        else:
            print("📅 Dati risultati aggiornati (meno di 12 ore fa)")
    except Exception as e:
        print(f"⚠️ Errore scraper all'avvio: {e}")
    # ---------------------------

    from src.core.config import GEMINI_API_KEY, TELEGRAM_TOKEN as TOKEN_CHECK
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
