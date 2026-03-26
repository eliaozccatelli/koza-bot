"""
KOZA Engine - Versione TheSportsDB + Gemini AI + ML
Motore ibrido: dati reali da TheSportsDB, analisi AI da Gemini + ML
"""

import logging
from datetime import datetime
from rapidfuzz import process, utils

from config import (
    GEMINI_API_KEY,
    THESPORTSDB_API_KEY,
    APIFOOTBALL_API_KEY,
    FUZZY_MATCH_THRESHOLD,
    LOG_LEVEL,
    MOSTRA_TOP_SCOMMESSE,
)
from gemini_engine import GeminiEngine, get_gemini_engine
from sportsdb_engine import SportsDBEngine, get_sportsdb_engine
from apifootball_engine import APIFootballEngine, get_apifootball_engine
from team_form_bridge import get_team_form, format_team_form
from teams_fallback import SQUADRE_FALLBACK, COMPETIZIONI_FALLBACK

# Setup logging PRIMA di usarlo
logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)

# ML Integration
try:
    from ml_integration import get_ml_prediction
    ML_AVAILABLE = True
    logger.info("✅ ML Integration disponibile")
except ImportError as e:
    ML_AVAILABLE = False
    logger.warning(f"⚠️ ML non disponibile: {e}")


class KozaEngine:
    """Motore KOZA ibrido: TheSportsDB + API-Football per dati reali, Gemini + ML per analisi."""

    def __init__(self):
        # Inizializza tutti i motori
        self.gemini = get_gemini_engine(api_keys=GEMINI_API_KEY)
        self.sportsdb = get_sportsdb_engine(api_key=THESPORTSDB_API_KEY)
        self.apifootball = get_apifootball_engine(api_key=APIFOOTBALL_API_KEY)
        
        # Cache squadre per fuzzy matching
        self.teams_cache = {}
        self.competitions = {}
        
        # Carica squadre dal fallback statico
        self._carica_fallback()
        
        # Inizializza competizioni da SportsDB
        self._init_competizioni()

    def _carica_fallback(self):
        """Carica squadre dal fallback statico."""
        logger.info("Caricamento squadre da fallback statico...")
        for name, data in SQUADRE_FALLBACK.items():
            self.teams_cache[name] = data
        logger.info(f"✓ Fallback caricato: {len(self.teams_cache)} squadre")
        return len(self.teams_cache)

    def _init_competizioni(self):
        """Inizializza competizioni da Gemini."""
        comps = self.gemini.get_competizioni()
        for comp in comps:
            self.competitions[comp["id"]] = comp["nome"]
        logger.info(f"✓ Competizioni caricate: {len(self.competitions)}")

    def carica_database_squadre(self):
        """Il database è già caricato dal fallback."""
        logger.info(f"Database: {len(self.teams_cache)} squadre disponibili")
        return len(self.teams_cache) > 0

    # =========================
    # Team lookup
    # =========================

    def trova_squadra(self, query):
        """Fuzzy matching - trova squadra dalla cache."""
        if not query or not self.teams_cache:
            return None, None, None

        nomi = list(self.teams_cache.keys())
        match = process.extractOne(query, nomi, processor=utils.default_process)
        
        if not match:
            logger.warning(f"Nessun match fuzzy per '{query}'")
            return None, None, None

        logger.info(f"Fuzzy match per '{query}': '{match[0]}' score={match[1]:.0f}%")

        if match[1] >= FUZZY_MATCH_THRESHOLD:
            nome_vero = match[0]
            team_data = self.teams_cache[nome_vero]
            comp_id = team_data.get("comp_id", "unknown")
            comp_name = COMPETIZIONI_FALLBACK.get(comp_id, "Unknown")
            return team_data.get("id", 0), nome_vero, comp_name

        logger.warning(f"Score troppo basso per '{query}': {match[1]:.0f}%")
        return None, None, None

    # =========================
    # Competizioni e Partite
    # =========================

    def get_competizioni_con_partite(self, data=None):
        """Ritorna competizioni con partite disponibili usando TheSportsDB + API-Football."""
        logger.info(f"=== RICERCA COMPETIZIONI DUAL-API === Data: {data}")
        
        # Recupera dati da entrambe le API
        sportsdb_data = self.sportsdb.get_partite_del_giorno(data)
        apifootball_data = self.apifootball.get_partite_del_giorno(data)
        
        # Merge e deduplica competizioni
        competizioni_unite = self._merge_competizioni(
            sportsdb_data.get("competizioni", []),
            apifootball_data.get("competizioni", [])
        )
        
        result = []
        for comp in competizioni_unite:
            comp_id = comp.get("id")
            comp_name = comp.get("nome", "Unknown")
            if comp_id:
                self.competitions[comp_id] = comp_name
                result.append((comp_id, comp_name))
                logger.info(f"✓ {comp_name}: {len(comp.get('partite', []))} partite")
        
        logger.info(f"Totale competizioni con partite (merge): {len(result)}")
        return result

    def _merge_competizioni(self, sportsdb_comps, apifootball_comps):
        """
        Merge competizioni da entrambe le API con deduplica partite.
        Priorità: TheSportsDB (no limiti) > API-Football (limiti richieste)
        """
        competizioni_dict = {}
        
        # Helper per creare key deduplica
        def make_match_key(partita):
            casa = partita.get("casa", "").lower().strip()
            trasferta = partita.get("trasferta", "").lower().strip()
            return f"{casa}_vs_{trasferta}"
        
        # Processa prima API-Football (come base, ma verrà sovrascritto da SportsDB se duplicato)
        for comp in apifootball_comps:
            comp_id = comp.get("id")
            comp_name = comp.get("nome", "Unknown")
            
            if comp_id not in competizioni_dict:
                competizioni_dict[comp_id] = {
                    "id": comp_id,
                    "nome": comp_name,
                    "partite": [],
                    "partite_keys": set()  # Per tracciare duplicati
                }
            
            for partita in comp.get("partite", []):
                key = make_match_key(partita)
                if key not in competizioni_dict[comp_id]["partite_keys"]:
                    competizioni_dict[comp_id]["partite"].append(partita)
                    competizioni_dict[comp_id]["partite_keys"].add(key)
        
        # Processa TheSportsDB (prioritaria - sovrascrive se esiste, aggiunge se nuova)
        for comp in sportsdb_comps:
            comp_id = comp.get("id")
            comp_name = comp.get("nome", "Unknown")
            
            if comp_id not in competizioni_dict:
                competizioni_dict[comp_id] = {
                    "id": comp_id,
                    "nome": comp_name,
                    "partite": [],
                    "partite_keys": set()
                }
            
            for partita in comp.get("partite", []):
                key = make_match_key(partita)
                # TheSportsDB ha priorità: se esiste già, sovrascrivi
                if key in competizioni_dict[comp_id]["partite_keys"]:
                    # Rimuovi vecchia partita
                    competizioni_dict[comp_id]["partite"] = [
                        p for p in competizioni_dict[comp_id]["partite"]
                        if make_match_key(p) != key
                    ]
                # Aggiungi partita da TheSportsDB
                competizioni_dict[comp_id]["partite"].append(partita)
                competizioni_dict[comp_id]["partite_keys"].add(key)
        
        # Rimuovi set temporaneo e ritorna lista
        for comp in competizioni_dict.values():
            del comp["partite_keys"]
        
        return list(competizioni_dict.values())

    def get_partite_campionato(self, comp_id, data=None):
        """Ritorna lista di partite per una competizione usando TheSportsDB (con fallback API-Football)."""
        # Prova prima TheSportsDB (no limiti richieste)
        partite = self.sportsdb.get_partite_per_lega(comp_id, data)
        
        # Se non trova nulla, fallback a API-Football
        if not partite:
            logger.info(f"TheSportsDB: nessuna partita per {comp_id}, provo API-Football")
            partite = self.apifootball.get_partite_per_lega(comp_id, data)
        
        result = []
        for p in partite:
            match_id = p.get("id", f"{p.get('casa', '')}_{p.get('trasferta', '')}")
            casa = p.get("casa", "Unknown")
            trasferta = p.get("trasferta", "Unknown")
            result.append((casa, trasferta, match_id))
        
        logger.info(f"Comp {comp_id}: {len(result)} partite trovate")
        return result

    # =========================
    # Analisi Partita
    # =========================

    def analizza_partita(self, squadra_casa, squadra_trasferta, competizione=None, data=None):
        """Analizza una partita usando Gemini AI."""
        logger.info(f"Analisi partita: {squadra_casa} vs {squadra_trasferta}")
        
        return self.gemini.analizza_partita(
            squadra_casa, 
            squadra_trasferta, 
            competizione=competizione, 
            data=data
        )

    def formatta_output(self, analisi, ml_data=None):
        """Formatta output con Gemini + ML combinati."""
        pronostico = analisi.get("pronostico", {})
        probabilita = analisi.get("probabilita", {})
        info_analisi = analisi.get("analisi", {})
        scommesse = analisi.get("scommesse_consigliate", [])
        
        casa = analisi.get("squadra_casa", "Casa")
        trasferta = analisi.get("squadra_trasferta", "Trasferta")
        
        # Usa probabilità combinate se disponibili
        if ml_data and "combined" in ml_data:
            probabilita = ml_data["combined"]
        
        # Header con emoji e nomi squadre
        msg = f"⚽ **{casa}** vs **{trasferta}**"
        if ml_data and ml_data.get("is_nazionale"):
            msg += " 🌍 *(Nazionale - Solo AI)*"
        msg += "\n"
        
        # Pronostico principale in riga singola
        risultato = pronostico.get("risultato_esatto", "N/A")
        confidence = pronostico.get("confidence", 50)
        msg += f"🎯 Pronostico: `{risultato}` | Confidenza: {confidence}%\n\n"
        
        # Sezione ML (se disponibile)
        if ml_data and ml_data.get("ml"):
            ml = ml_data["ml"]
            msg += "🧠 **Analisi ML**\n"
            msg += f"   1: {ml['1']}% | X: {ml['X']}% | 2: {ml['2']}%\n"
            msg += f"   Predizione: `{ml['prediction']}` (conf: {ml['confidence']}%)\n\n"
        
        # Probabilità combinate (o solo Gemini)
        msg += "📊 Probabilità Finali:\n"
        msg += f"   1: {probabilita.get('1', 33):.0f}% | X: {probabilita.get('X', 33):.0f}% | 2: {probabilita.get('2', 33):.0f}%\n"
        msg += f"   Over 2.5: {probabilita.get('over25', 50)}% | Gol: {probabilita.get('gol', 50)}%\n\n"
        
        # Forza e forma squadre (con dati reali se disponibili)
        if info_analisi:
            msg += f"🔹 {casa}: {format_team_form(casa)}\n"
            msg += f"🔹 {trasferta}: {format_team_form(trasferta)}\n\n"
        
        # Scommesse consigliate (top 3, senza quote)
        if scommesse:
            msg += "💰 Scommesse Consigliate:\n"
            for sc in scommesse[:3]:
                tipo = sc.get("tipo", "?")
                desc = sc.get("descrizione", "")
                msg += f"   • `{tipo}` - {desc}\n"
        
        # Nota disclaimer breve
        msg += "\n⚠️ Previsioni AI - Gioca responsabilmente"
        
        return msg

    def formatta_output_live(self, live_data):
        """Formatta output per partita con stato live."""
        stato = live_data.get("stato", "unknown")
        analisi = live_data.get("analisi", {})
        is_nazionale = live_data.get("is_nazionale", False)
        
        # Estrai dati analisi
        gemini_analisi = analisi.get("gemini", {})
        pronostico = gemini_analisi.get("pronostico", {})
        probabilita = gemini_analisi.get("probabilita", {})
        scommesse = gemini_analisi.get("scommesse_consigliate", [])
        
        casa = gemini_analisi.get("squadra_casa", "Casa")
        trasferta = gemini_analisi.get("squadra_trasferta", "Trasferta")
        
        # Header base
        msg = f"⚽ **{casa}** vs **{trasferta}**"
        if is_nazionale:
            msg += " 🌍 *(Nazionale - Solo AI)*"
        msg += "\n"
        
        # Stato partita
        if stato == "finished":
            risultato_finale = live_data.get("risultato_live", "?-?")
            msg += f"🏁 **PARTITA TERMINATA**: `{risultato_finale}`\n"
            msg += "⚠️ La partita è già finita. Analisi pre-partita per riferimento:\n\n"
            
        elif stato == "live":
            risultato_live = live_data.get("risultato_live")
            tempo = live_data.get("tempo")
            
            # Se i dati live sono None, tratta come partita non iniziata
            if not risultato_live or risultato_live == "None" or tempo is None:
                msg += "⏳ **Partita in corso** (dati live non disponibili)\n\n"
            else:
                msg += f"🔴 **LIVE** {tempo}' - Risultato: `{risultato_live}`\n\n"
                
                # Statistiche live se disponibili
                stats = live_data.get("statistiche_live")
                if stats:
                    msg += "📊 **Statistiche Live**:\n"
                    for team_name, team_data in stats.items():
                        msg += f"   {team_name}:\n"
                        stats_dict = team_data.get("stats", {})
                        # Mostra le statistiche principali
                        poss = stats_dict.get("Ball Possession", "N/A")
                        tiri = stats_dict.get("Total Shots", stats_dict.get("Shots on Goal", "N/A"))
                        tiri_porta = stats_dict.get("Shots on Goal", stats_dict.get("Shots on target", "N/A"))
                        corner = stats_dict.get("Corner Kicks", stats_dict.get("Corners", "N/A"))
                        msg += f"     - Possesso: {poss} | Tiri: {tiri} ({tiri_porta} in porta) | Corner: {corner}\n"
                    msg += "\n"
                
                # Consigli live
                consigli_live = live_data.get("consigli_live", [])
                if consigli_live:
                    msg += "💡 **Consigli Live**:\n"
                    for cons in consigli_live:
                        msg += f"   • `{cons['tipo']}` - {cons['descrizione']}\n"
                    msg += "\n"
                
                # 🆕 Analisi AI dinamica basata sulle statistiche live
                analisi_ai = live_data.get("analisi_ai_live")
                logger.info(f"🔍 Verifica analisi_ai_live: {analisi_ai is not None}")
                if analisi_ai:
                    msg += "🤖 **Analisi AI in Tempo Reale**:\n"
                    
                    # Analisi testuale
                    analisi_txt = analisi_ai.get("analisi_testuale", "")
                    if analisi_txt:
                        # Tronca se troppo lunga
                        if len(analisi_txt) > 200:
                            analisi_txt = analisi_txt[:197] + "..."
                        msg += f"   _{analisi_txt}_\n\n"
                    
                    # Probabilità AI aggiornate
                    prob_ai = analisi_ai.get("probabilita_aggiornate", {})
                    if prob_ai:
                        msg += "   📊 Probabilità AI aggiornate:\n"
                        msg += f"      1: {prob_ai.get('1', 33)}% | X: {prob_ai.get('X', 33)}% | 2: {prob_ai.get('2', 33)}%\n"
                        
                        # Pronostico finale AI
                        pron_finale = analisi_ai.get("pronostico_finale", "")
                        conf_ai = analisi_ai.get("confidence", 50)
                        if pron_finale:
                            msg += f"      🎯 Pronostico finale: `{pron_finale}` ({conf_ai}% confidence)\n"
                    
                    # Fattori chiave
                    fattori = analisi_ai.get("fattori_chiave", [])
                    if fattori:
                        msg += "\n   🔑 Fattori chiave:\n"
                        for f in fattori[:3]:
                            msg += f"      • {f}\n"
                    
                    # Consigli AI live
                    consigli_ai = analisi_ai.get("consigli_live", [])
                    if consigli_ai:
                        msg += "\n   💡 Consigli AI Live:\n"
                        for c in consigli_ai[:2]:
                            msg += f"      • `{c.get('tipo', '?')}` - {c.get('descrizione', '')}\n"
                    
                    msg += "\n"
                
                # Separatore
                msg += "📈 **Analisi Pre-partita** (per confronto):\n"
            
        else:
            # Partita non iniziata - analisi normale
            pass
        
        # Pronostico originale
        risultato = pronostico.get("risultato_esatto", "N/A")
        confidence = pronostico.get("confidence", 50)
        msg += f"🎯 Pronostico: `{risultato}` | Confidenza: {confidence}%\n\n"
        
        # Probabilità: se c'è AI live, usa quelle aggiornate
        analisi_ai = live_data.get("analisi_ai_live")
        if analisi_ai and analisi_ai.get("probabilita_aggiornate"):
            prob_ai = analisi_ai.get("probabilita_aggiornate", {})
            msg += "📊 **Probabilità Finali (AI Aggiornate)**:\n"
            msg += f"   1: {prob_ai.get('1', 33):.0f}% | X: {prob_ai.get('X', 33):.0f}% | 2: {prob_ai.get('2', 33):.0f}%\n"
            # Calcola Over/Gol approssimati basati sul pronostico AI
            pron_ai = analisi_ai.get("pronostico_finale", risultato)
            try:
                g_c, g_t = map(int, pron_ai.split('-'))
                tot = g_c + g_t
                over25_ai = 70 if tot >= 3 else (50 if tot == 2 else 30)
                gol_ai = 70 if g_c > 0 and g_t > 0 else (50 if tot > 0 else 20)
            except:
                over25_ai = probabilita.get('over25', 50)
                gol_ai = probabilita.get('gol', 50)
            msg += f"   Over 2.5: {over25_ai}% | Gol: {gol_ai}%\n\n"
        else:
            # Probabilità pre-partita (statiche)
            msg += "📊 Probabilità Finali:\n"
            msg += f"   1: {probabilita.get('1', 33):.0f}% | X: {probabilita.get('X', 33):.0f}% | 2: {probabilita.get('2', 33):.0f}%\n"
            msg += f"   Over 2.5: {probabilita.get('over25', 50)}% | Gol: {probabilita.get('gol', 50)}%\n\n"
        
        # Scommesse: se live con AI, usa consigli AI, altrimenti scommesse originali
        if stato == "live":
            analisi_ai = live_data.get("analisi_ai_live")
            if analisi_ai:
                # Usa consigli AI live
                consigli_ai = analisi_ai.get("consigli_live", [])
                if consigli_ai:
                    msg += "💰 **Scommesse Consigliate (Aggiornate Live)**:\n"
                    for c in consigli_ai[:3]:
                        msg += f"   • `{c.get('tipo', '?')}` - {c.get('descrizione', '')}\n"
                else:
                    msg += "💰 Scommesse: _Nessun consiglio AI disponibile_\n"
            else:
                # Fallback a consigli programmatici live
                consigli_live = live_data.get("consigli_live", [])
                if consigli_live:
                    msg += "💰 **Scommesse Consigliate (Basate su Risultato)**:\n"
                    for cons in consigli_live[:3]:
                        msg += f"   • `{cons['tipo']}` - {cons['descrizione']}\n"
        elif scommesse:
            # Partita non iniziata o finita - usa scommesse pre-partita
            msg += "💰 Scommesse Consigliate:\n"
            for sc in scommesse[:3]:
                tipo = sc.get("tipo", "?")
                desc = sc.get("descrizione", "")
                msg += f"   • `{tipo}` - {desc}\n"
        
        msg += "\n⚠️ Previsioni AI - Gioca responsabilmente"
        
        return msg

    # =========================
    # Analisi Ibrida ML + Gemini
    # =========================

    def _is_nazionale(self, nome_squadra):
        """
        Rileva se una squadra è una nazionale.
        Le nazionali non sono nel database ML (che ha solo club di Serie A).
        """
        nazionali_keywords = [
            # Europeo
            "italia", "italy", "francia", "france", "germania", "germany", 
            "spagna", "spain", "inghilterra", "england", "portogallo", "portugal",
            "olanda", "netherlands", "belgio", "belgium", "croazia", "croatia",
            "danimarca", "denmark", "svezia", "sweden", "norvegia", "norway",
            "polonia", "poland", "ucraina", "ukraine", "romania", "romania",
            "repubblica ceca", "czech republic", "czechia", "svizzera", "switzerland",
            "austria", "austria", "ungheria", "hungary", "serbia", "serbia",
            "slovacchia", "slovakia", "slovenia", "slovenia", "bosnia", "bosnia",
            "albania", "albania", "finlandia", "finland", "irlanda", "ireland",
            "irlanda del nord", "northern ireland", "scozia", "scotland", "galles", "wales",
            "islanda", "iceland", "grecia", "greece", "turchia", "turkey", "turkiye",
            
            # Sud America
            "argentina", "brasile", "brazil", "uruguay", "colombia", "cile", "chile",
            "peru", "paraguay", "bolivia", "ecuador", "venezuela",
            
            # Altri
            "usa", "stati uniti", "united states", "messico", "mexico",
            "giappone", "japan", "corea", "korea", "australia", "canada"
        ]
        
        nome_lower = nome_squadra.lower()
        for keyword in nazionali_keywords:
            if keyword in nome_lower:
                return True
        return False

    def get_analisi_ibrida(self, squadra_casa, squadra_trasferta, competizione=None):
        """
        Combina analisi Gemini + ML per risultato migliore.
        Formula: 60% Gemini + 40% ML (SOLO per club, NON per nazionali)
        """
        # Rileva nazionali - se una delle due è nazionale, salta ML
        is_nazionale_casa = self._is_nazionale(squadra_casa)
        is_nazionale_trasferta = self._is_nazionale(squadra_trasferta)
        
        if is_nazionale_casa or is_nazionale_trasferta:
            logger.info(f"🌍 Nazionale rilevata: {squadra_casa} vs {squadra_trasferta} - ML DISABILITATO")
            # Solo Gemini per nazionali
            gemini_analisi = self.analizza_partita(squadra_casa, squadra_trasferta, competizione)
            return {
                "gemini": gemini_analisi,
                "ml": None,
                "combined": gemini_analisi.get("probabilita", {}),
                "is_nazionale": True
            }
        
        # Analisi Gemini per club
        gemini_analisi = self.analizza_partita(squadra_casa, squadra_trasferta, competizione)
        gemini_probs = gemini_analisi.get("probabilita", {})
        
        result = {
            "gemini": gemini_analisi,
            "ml": None,
            "combined": gemini_probs,  # Default solo Gemini se ML non disp
        }
        
        # Analisi ML
        if ML_AVAILABLE:
            try:
                ml_result = get_ml_prediction(squadra_casa, squadra_trasferta, competizione)
                if ml_result:
                    result["ml"] = ml_result
                    
                    # Formula combinata: 60% Gemini + 40% ML
                    result["combined"] = {
                        "1": round(gemini_probs.get("1", 33) * 0.6 + ml_result["1"] * 0.4, 1),
                        "X": round(gemini_probs.get("X", 33) * 0.6 + ml_result["X"] * 0.4, 1),
                        "2": round(gemini_probs.get("2", 33) * 0.6 + ml_result["2"] * 0.4, 1),
                        "over25": gemini_probs.get("over25", 50),
                        "gol": gemini_probs.get("gol", 50),
                        "ml_prediction": ml_result["prediction"],
                        "ml_confidence": ml_result["confidence"],
                    }
                    logger.info(f"✅ Analisi ibrida: Gemini + ML per {squadra_casa} vs {squadra_trasferta}")
            except Exception as e:
                logger.error(f"Errore ML prediction: {e}")
        
        return result

    def get_analisi_partita_live(self, squadra_casa, squadra_trasferta, match_id=None, competizione=None):
        """
        Analizza una partita considerando lo stato live se disponibile.
        Ritorna: dict con stato, risultato live, statistiche, e analisi adattata.
        """
        result = {
            "stato": "unknown",
            "risultato_live": None,
            "tempo": None,
            "statistiche_live": None,
            "analisi": None,
            "is_nazionale": False
        }
        
        # Se abbiamo match_id, controlla stato live
        if match_id:
            try:
                # Controlla se partita è finita
                is_finished = self.apifootball.is_match_finished(match_id)
                is_live = self.apifootball.is_match_live(match_id)
                
                if is_finished:
                    result["stato"] = "finished"
                    status_data = self.apifootball.get_match_status(match_id)
                    if status_data:
                        result["risultato_live"] = status_data.get("risultato")
                    
                elif is_live:
                    result["stato"] = "live"
                    status_data = self.apifootball.get_match_status(match_id)
                    if status_data:
                        result["risultato_live"] = status_data.get("risultato")
                        result["tempo"] = status_data.get("tempo")
                    
                    # Recupera statistiche live
                    live_stats = self.apifootball.get_live_statistics(match_id)
                    if live_stats:
                        result["statistiche_live"] = live_stats
                    
                else:
                    result["stato"] = "not_started"
                    
            except Exception as e:
                logger.warning(f"Errore recupero stato live: {e}")
                result["stato"] = "unknown"
        
        # Analisi base (Gemini/ML)
        ml_data = self.get_analisi_ibrida(squadra_casa, squadra_trasferta, competizione)
        result["analisi"] = ml_data
        result["is_nazionale"] = ml_data.get("is_nazionale", False)
        
        # Se live, adatta consigli basati sul risultato attuale
        if result["stato"] == "live" and result["risultato_live"]:
            result["consigli_live"] = self._genera_consigli_live(
                result["risultato_live"], 
                result["tempo"],
                squadra_casa, 
                squadra_trasferta
            )
            
            # 🆕 Analisi AI dinamica basata sulle statistiche live
            if result["statistiche_live"]:
                logger.info(f"🤖 Chiamata analisi AI live per {squadra_casa} vs {squadra_trasferta}")
                try:
                    prob_pre = ml_data.get("combined", {}) or ml_data.get("gemini", {}).get("probabilita", {})
                    logger.info(f"📊 Probabilità pre-partita passate all'AI: {prob_pre}")
                    
                    analisi_ai_live = self.gemini.analisi_live(
                        squadra_casa, 
                        squadra_trasferta,
                        result["risultato_live"],
                        result["tempo"],
                        result["statistiche_live"],
                        prob_pre
                    )
                    if analisi_ai_live:
                        result["analisi_ai_live"] = analisi_ai_live
                        logger.info(f"✅ Analisi AI live completata per {squadra_casa} vs {squadra_trasferta}")
                        logger.info(f"📝 Risultato AI: {analisi_ai_live}")
                    else:
                        logger.warning(f"⚠️ Analisi AI live ritornata vuota, uso fallback programmatico")
                        # 🆕 Fallback: calcola probabilità live con algoritmo
                        prob_pre = ml_data.get("combined", {}) or ml_data.get("gemini", {}).get("probabilita", {})
                        prob_fallback = self._calcola_probabilita_live(
                            result["statistiche_live"],
                            squadra_casa,
                            squadra_trasferta,
                            prob_pre.get('1', 33),
                            prob_pre.get('X', 33),
                            prob_pre.get('2', 33)
                        )
                        # Genera consigli basati sul risultato live
                        consigli_fallback = self._genera_consigli_live_intelligenti(
                            result["risultato_live"],
                            result["tempo"],
                            squadra_casa,
                            squadra_trasferta,
                            result["statistiche_live"]
                        )
                        result["analisi_ai_live"] = {
                            "analisi_testuale": prob_fallback.get('commento', 'Analisi basata su statistiche live'),
                            "probabilita_aggiornate": {
                                "1": round(prob_fallback['1']),
                                "X": round(prob_fallback['X']),
                                "2": round(prob_fallback['2'])
                            },
                            "pronostico_finale": self._predici_risultato_finale(
                                result["risultato_live"],
                                result["tempo"],
                                prob_fallback
                            ),
                            "confidence": 60,
                            "fattori_chiave": [prob_fallback.get('commento', 'Dati live')],
                            "consigli_live": consigli_fallback
                        }
                        logger.info(f"✅ Fallback programmatico completato: {result['analisi_ai_live']}")
                except Exception as e:
                    logger.error(f"❌ Errore analisi AI live: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
        
        return result
    
    def _genera_consigli_live_intelligenti(self, risultato_live, tempo, casa, trasferta, stats):
        """Genera consigli live intelligenti basati anche sulle statistiche."""
        try:
            gol_casa, gol_trasf = map(int, risultato_live.split('-'))
            tempo = tempo or 0
            totale_gol = gol_casa + gol_trasf
            
            consigli = []
            
            # Estrai statistiche
            casa_data = stats.get(casa, {})
            trasf_data = stats.get(trasferta, {})
            casa_stats = casa_data.get("stats", {})
            trasf_stats = trasf_data.get("stats", {})
            
            possesso_casa = casa_stats.get("Ball Possession", 50)
            tiri_porta_casa = casa_stats.get("Shots on Goal", casa_stats.get("Shots on target", 0)) or 0
            tiri_porta_trasf = trasf_stats.get("Shots on Goal", trasf_stats.get("Shots on target", 0)) or 0
            
            # Consigli basati su risultato + tempo + statistiche
            if tempo > 75:
                if gol_casa > gol_trasf:
                    consigli.append({"tipo": "Under 4.5", "descrizione": f"Partita chiusa ({tempo}')"})
                    if possesso_casa > 60:
                        consigli.append({"tipo": "1", "descrizione": f"{casa} controlla il gioco"})
                elif gol_trasf > gol_casa:
                    consigli.append({"tipo": "2", "descrizione": f"{trasferta} in vantaggio"})
                else:
                    consigli.append({"tipo": "X", "descrizione": f"Pareggio stabile al {tempo}'"})
            
            # Consigli basati su tiri in porta
            if tiri_porta_casa > tiri_porta_trasf + 1 and gol_casa <= gol_trasf:
                consigli.append({"tipo": "1", "descrizione": f"{casa} più pericolosa, può ribaltare"})
            elif tiri_porta_trasf > tiri_porta_casa + 1 and gol_trasf <= gol_casa:
                consigli.append({"tipo": "2", "descrizione": f"{trasferta} più pericolosa, può ribaltare"})
            
            # Consigli Over/Under basati su gol
            if totale_gol >= 3:
                consigli.append({"tipo": "Over 2.5", "descrizione": f"Già {totale_gol} gol segnati"})
            elif totale_gol == 0 and tempo > 70:
                consigli.append({"tipo": "Under 2.5", "descrizione": f"0-0 al {tempo}', partita chiusa"})
            
            # Consigli Gol/No Gol
            if gol_casa > 0 and gol_trasf > 0:
                consigli.append({"tipo": "Gol", "descrizione": "Entrambe hanno già segnato"})
            elif tempo > 80 and totale_gol == 0:
                consigli.append({"tipo": "No Gol", "descrizione": "Partita senza gol"})
            
            return consigli[:3]
        except:
            return []
    
    def _predici_risultato_finale(self, risultato_live, tempo, probabilita):
        """Predice il risultato finale basato sulle probabilità live."""
        try:
            gol_casa, gol_trasf = map(int, risultato_live.split('-'))
            tempo_rimanente = 90 - tempo
            
            p1 = probabilita.get('1', 33)
            pX = probabilita.get('X', 33)
            p2 = probabilita.get('2', 33)
            
            # Stima gol aggiuntivi basato sul tempo rimanente e probabilità
            if p1 > pX and p1 > p2:
                # Casa favorita
                gol_add_casa = max(0, int((p1 / 100) * (tempo_rimanente / 30)))
                gol_add_trasf = max(0, int((p2 / 100) * (tempo_rimanente / 45)))
            elif p2 > p1 and p2 > pX:
                # Trasferta favorita
                gol_add_casa = max(0, int((p1 / 100) * (tempo_rimanente / 45)))
                gol_add_trasf = max(0, int((p2 / 100) * (tempo_rimanente / 30)))
            else:
                # Equilibrato
                gol_add_casa = max(0, int((p1 / 100) * (tempo_rimanente / 40)))
                gol_add_trasf = max(0, int((p2 / 100) * (tempo_rimanente / 40)))
            
            finale_casa = gol_casa + gol_add_casa
            finale_trasf = gol_trasf + gol_add_trasf
            
            return f"{finale_casa}-{finale_trasf}"
        except:
            return risultato_live
    
    def _genera_consigli_live(self, risultato_live, tempo, casa, trasferta):
        """
        Genera consigli per scommesse live basati sul risultato attuale e tempo.
        """
        try:
            gol_casa, gol_trasf = map(int, risultato_live.split('-'))
            tempo = tempo or 0
            
            consigli = []
            
            # Analisi secondo tempo
            if tempo > 75:  # Ultimi 15 minuti
                if gol_casa > gol_trasf:
                    consigli.append({
                        "tipo": "Under 4.5",
                        "descrizione": f"Partita chiusa ({tempo}') - proteggi risultato"
                    })
                elif gol_casa == gol_trasf:
                    consigli.append({
                        "tipo": "Over 1.5",
                        "descrizione": f"Tensione finale ({tempo}') - possibile gol"
                    })
            
            # Analisi gol
            totale_gol = gol_casa + gol_trasf
            if totale_gol >= 3:
                consigli.append({
                    "tipo": "Over 2.5",
                    "descrizione": f"Già {totale_gol} gol segnati"
                })
                if tempo < 70:
                    consigli.append({
                        "tipo": "Over 3.5",
                        "descrizione": f"Partita aperta - ancora tempo per altri gol"
                    })
            elif totale_gol == 0 and tempo > 60:
                consigli.append({
                    "tipo": "Under 2.5",
                    "descrizione": f"0-0 al {tempo}' - partita chiusa"
                })
            
            # Analisi esito
            if gol_casa > gol_trasf + 1:
                consigli.append({
                    "tipo": "1",
                    "descrizione": f"{casa} in vantaggio ({risultato_live})"
                })
            elif gol_trasf > gol_casa + 1:
                consigli.append({
                    "tipo": "2",
                    "descrizione": f"{trasferta} in vantaggio ({risultato_live})"
                })
            elif gol_casa == gol_trasf and tempo > 70:
                consigli.append({
                    "tipo": "X",
                    "descrizione": f"Pareggio ({risultato_live}) al {tempo}' - potrebbe finire così"
                })
            
            # Gol/No Gol basato sul risultato
            if gol_casa > 0 and gol_trasf > 0:
                consigli.append({
                    "tipo": "Gol",
                    "descrizione": "Entrambe hanno già segnato"
                })
            elif gol_casa > 0 and gol_trasf == 0 and tempo > 75:
                consigli.append({
                    "tipo": "No Gol",
                    "descrizione": f"{trasferta} in difficoltà offensiva"
                })
            
            return consigli[:3]  # Max 3 consigli live
            
        except (ValueError, IndexError):
            return []

    def _calcola_probabilita_live(self, stats, casa, trasferta, prob1_pre, probX_pre, prob2_pre):
        """
        Ricalcola le probabilità basandosi sulle statistiche live.
        Aggiusta le prob pre-partita in base a possesso, tiri, corner, etc.
        """
        # Estrai dati statistiche
        casa_data = stats.get(casa, {})
        trasf_data = stats.get(trasferta, {})
        
        casa_stats = casa_data.get("stats", {})
        trasf_stats = trasf_data.get("stats", {})
        
        # Estrai valori numerici (gestisce None)
        def get_val(stats_dict, key, default=0):
            val = stats_dict.get(key, default)
            return val if val is not None else default
        
        possesso_casa = get_val(casa_stats, "Ball Possession", 50)
        possesso_trasf = get_val(trasf_stats, "Ball Possession", 50)
        
        tiri_casa = get_val(casa_stats, "Total Shots", 0)
        tiri_trasf = get_val(trasf_stats, "Total Shots", 0)
        
        tiri_porta_casa = get_val(casa_stats, "Shots on Goal", get_val(casa_stats, "Shots on target", 0))
        tiri_porta_trasf = get_val(trasf_stats, "Shots on Goal", get_val(trasf_stats, "Shots on target", 0))
        
        corner_casa = get_val(casa_stats, "Corner Kicks", get_val(casa_stats, "Corners", 0))
        corner_trasf = get_val(trasf_stats, "Corner Kicks", get_val(trasf_stats, "Corners", 0))
        
        # Fattori di aggiustamento (base 1.0 = neutrale)
        fattore_casa = 1.0
        fattore_trasf = 1.0
        commenti = []
        
        # 1. Possesso palla (range 0-100)
        diff_possesso = possesso_casa - possesso_trasf
        if diff_possesso > 20:  # Netta supremazia possesso
            fattore_casa += 0.25
            fattore_trasf -= 0.15
            commenti.append(f"{casa} domina il possesso ({possesso_casa}%)")
        elif diff_possesso > 10:  # Moderata supremazia
            fattore_casa += 0.15
            fattore_trasf -= 0.10
        elif diff_possesso < -20:  # Trasferta domina
            fattore_trasf += 0.25
            fattore_casa -= 0.15
            commenti.append(f"{trasferta} domina il possesso ({possesso_trasf}%)")
        elif diff_possesso < -10:
            fattore_trasf += 0.15
            fattore_casa -= 0.10
        
        # 2. Tiri totali e in porta
        tiri_totali_casa = tiri_casa + tiri_porta_casa  # Peso doppio per tiri in porta
        tiri_totali_trasf = tiri_trasf + tiri_porta_trasf
        
        if tiri_porta_casa > tiri_porta_trasf + 2:  # Molti più tiri in porta
            fattore_casa += 0.20
            fattore_trasf -= 0.10
            commenti.append(f"{casa} più pericolosa ({tiri_porta_casa} tiri in porta)")
        elif tiri_casa > tiri_trasf + 3:  # Più tiri totali
            fattore_casa += 0.10
        
        if tiri_porta_trasf > tiri_porta_casa + 2:
            fattore_trasf += 0.20
            fattore_casa -= 0.10
            commenti.append(f"{trasferta} più pericolosa ({tiri_porta_trasf} tiri in porta)")
        elif tiri_trasf > tiri_casa + 3:
            fattore_trasf += 0.10
        
        # 3. Corner (indicatore di pressione offensiva)
        if corner_casa > corner_trasf + 2:
            fattore_casa += 0.10
            if not commenti:
                commenti.append(f"{casa} spinge di più ({corner_casa} corner)")
        elif corner_trasf > corner_casa + 2:
            fattore_trasf += 0.10
            if not commenti:
                commenti.append(f"{trasferta} spinge di più ({corner_trasf} corner)")
        
        # Calcola nuove probabilità
        # Converti da percentuali a "quote" (100/prob) per ponderare
        quota1_pre = 100 / prob1_pre if prob1_pre > 0 else 3.0
        quotaX_pre = 100 / probX_pre if probX_pre > 0 else 3.0
        quota2_pre = 100 / prob2_pre if prob2_pre > 0 else 3.0
        
        # Applica fattori
        quota1_live = quota1_pre / fattore_casa
        quotaX_live = quotaX_pre  # Pareggio rimane più stabile
        quota2_live = quota2_pre / fattore_trasf
        
        # Riconverti in probabilità (normalizzate a 100%)
        prob1_raw = 100 / quota1_live
        probX_raw = 100 / quotaX_live
        prob2_raw = 100 / quota2_live
        
        total = prob1_raw + probX_raw + prob2_raw
        
        prob1_live = (prob1_raw / total) * 100
        probX_live = (probX_raw / total) * 100
        prob2_live = (prob2_raw / total) * 100
        
        # Limita range 5%-85%
        prob1_live = max(5, min(85, prob1_live))
        probX_live = max(5, min(85, probX_live))
        prob2_live = max(5, min(85, prob2_live))
        
        # Rinormalizza dopo i limiti
        total = prob1_live + probX_live + prob2_live
        prob1_live = (prob1_live / total) * 100
        probX_live = (probX_live / total) * 100
        prob2_live = (prob2_live / total) * 100
        
        # Commento finale
        if commenti:
            commento = " • ".join(commenti[:2])  # Max 2 commenti
        else:
            commento = "Partita equilibrata finora"
        
        return {
            "1": prob1_live,
            "X": probX_live,
            "2": prob2_live,
            "commento": commento
        }

    def calcola_schedina(self, pronostici_list):
        """Calcola una schedina multipla."""
        partite_input = []
        for p in pronostici_list:
            partite_input.append({
                "casa": p.get("nome_casa", "Casa"),
                "trasferta": p.get("nome_trasf", "Trasferta")
            })
        
        return self.gemini.calcola_schedina(partite_input)

    def formatta_schedina(self, schedina_data, importo_scommessa=100):
        """Formatta la schedina per l'output."""
        if not schedina_data:
            return "❌ Nessuna schedina disponibile"

        schedina = schedina_data.get("schedina", [])
        combo = schedina_data.get("combo_principale", {})
        analisi = schedina_data.get("analisi_complessiva", "")

        msg = (
            "🎯 **SCHEDINA AI GENERATA**\n"
            f"{'='*45}\n\n"
        )
        
        for i, s in enumerate(schedina, 1):
            partita = s.get("partita", "? vs ?")
            consiglio = s.get("consiglio", "?")
            quota = s.get("quota", "1.80")
            prob = s.get("probabilita", 50)
            msg += f"{i}. **{partita}**\n"
            msg += f"   Scelta: `{consiglio}` @ {quota} ({prob}%)\n\n"
        
        if combo:
            msg += f"{'='*45}\n🏆 **COMBO PRINCIPALE**:\n"
            esiti = combo.get("esiti", [])
            quota_tot = combo.get("quota_totale", "10.00")
            prob_tot = combo.get("probabilita", 10)
            msg += f"   Esiti: {' - '.join(esiti)}\n"
            msg += f"   Quota totale: {quota_tot}x\n"
            msg += f"   Probabilità: {prob_tot}%\n"
            payout = importo_scommessa * float(quota_tot.replace(",", "."))
            msg += f"   💰 Payout potenziale: €{payout:.2f}\n\n"
        
        if analisi:
            msg += f"📝 **Analisi**: {analisi}\n\n"
        
        msg += "⚠️ _Gioca responsabilmente_"
        
        return msg

    # =========================
    # Metodi Legacy per compatibilità
    # =========================

    def get_stats(self, team_id, comp_id):
        """Metodo legacy - non più usato con Gemini."""
        return {
            "media_segni": 1.5,
            "media_subiti": 1.2,
            "partite": 10,
            "gialli": 2.5,
            "rossi": 0.1,
            "tiri_in_porta": 4.5,
            "possesso": 50,
        }

    def get_h2h_stats(self, team_id_1, team_id_2, comp_id):
        """Metodo legacy - non più usato con Gemini."""
        return {"vittorie_1": 0, "pareggi": 0, "vittorie_2": 0, "scontri": 0, "matches": []}

    def trova_prossima_partita(self, team_id_1, team_id_2, data_partita=None):
        """Metodo legacy - semplificato per Gemini."""
        return {"found": True, "data": {"date": datetime.now().isoformat()}}

    def calcola_pronostico(self, id_casa, nome_casa, id_trasf, nome_trasf, comp_id):
        """Metodo legacy - usa analizza_partita."""
        # Trova nome competizione
        comp_name = self.competitions.get(comp_id, "Unknown")
        
        # Usa Gemini per l'analisi
        analisi = self.analizza_partita(nome_casa, nome_trasf, comp_name)
        
        # Aggiungi campi legacy per compatibilità
        pronostico = analisi.get("pronostico", {})
        probabilita = analisi.get("probabilita", {})
        
        return {
            "nome_casa": nome_casa,
            "nome_trasf": nome_trasf,
            "xg_casa": 1.5,
            "xg_trasf": 1.2,
            "p1": probabilita.get("1", 33) / 100,
            "px": probabilita.get("X", 33) / 100,
            "p2": probabilita.get("2", 33) / 100,
            "over25": probabilita.get("over25", 50) / 100,
            "over35": probabilita.get("over35", 30) / 100,
            "btts": probabilita.get("gol", 50) / 100,
            "cart_media": 2.5,
            "cart_over4": probabilita.get("cartellini_over45", 50) / 100,
            "risultati_esatti": [(1, 1, 20), (2, 1, 15), (1, 0, 12)],
            "verdetto": pronostico.get("risultato_esatto", "1-1"),
            "h2h": analisi.get("analisi", {}).get("ultimi_scontri", []),
            "stats_casa": self.get_stats(id_casa, comp_id),
            "stats_trasf": self.get_stats(id_trasf, comp_id),
            # Campi aggiuntivi per formattazione Gemini
            "_analisi_completa": analisi,
        }


# Singleton
gemini_engine_instance = None

def get_koza_engine():
    """Ritorna l'istanza singleton del motore KOZA."""
    global gemini_engine_instance
    if gemini_engine_instance is None:
        gemini_engine_instance = KozaEngine()
    return gemini_engine_instance