"""
KOZA Engine - Versione TheSportsDB + Gemini AI
Motore ibrido: dati reali da TheSportsDB, analisi AI da Gemini
"""

import logging
from datetime import datetime
from rapidfuzz import process, utils

from config import (
    GEMINI_API_KEY,
    THESPORTSDB_API_KEY,
    FUZZY_MATCH_THRESHOLD,
    LOG_LEVEL,
    MOSTRA_TOP_SCOMMESSE,
)
from gemini_engine import GeminiEngine, get_gemini_engine
from sportsdb_engine import SportsDBEngine, get_sportsdb_engine
from teams_fallback import SQUADRE_FALLBACK, COMPETIZIONI_FALLBACK

logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)


class KozaEngine:
    """Motore KOZA ibrido: TheSportsDB per dati reali, Gemini per analisi AI."""

    def __init__(self):
        # Inizializza entrambi i motori
        self.gemini = get_gemini_engine(api_keys=GEMINI_API_KEY)
        self.sportsdb = get_sportsdb_engine(api_key=THESPORTSDB_API_KEY)
        
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
        """Ritorna competizioni con partite disponibili usando TheSportsDB."""
        logger.info(f"=== RICERCA COMPETIZIONI === Data: {data}")
        
        partite_data = self.sportsdb.get_partite_del_giorno(data)
        competizioni = partite_data.get("competizioni", [])
        
        result = []
        for comp in competizioni:
            comp_id = comp.get("id")
            comp_name = comp.get("nome", "Unknown")
            if comp_id:
                self.competitions[comp_id] = comp_name
                result.append((comp_id, comp_name))
                logger.info(f"✓ {comp_name}: {len(comp.get('partite', []))} partite")
        
        logger.info(f"Totale competizioni con partite: {len(result)}")
        return result

    def get_partite_campionato(self, comp_id, data=None):
        """Ritorna lista di partite per una competizione usando TheSportsDB."""
        partite = self.sportsdb.get_partite_per_lega(comp_id, data)
        
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

    def formatta_output(self, analisi):
        """Formatta l'output dell'analisi per Telegram."""
        pronostico = analisi.get("pronostico", {})
        probabilita = analisi.get("probabilita", {})
        info_analisi = analisi.get("analisi", {})
        scommesse = analisi.get("scommesse_consigliate", [])
        
        casa = analisi.get("squadra_casa", "Casa")
        trasferta = analisi.get("squadra_trasferta", "Trasferta")
        
        msg = (
            f"🤖 **ANALISI KOZA - Powered by Gemini AI**\n"
            f"{'='*45}\n\n"
            f"🏟 **{casa.upper()}** vs **{trasferta.upper()}**\n\n"
        )
        
        # Pronostico principale
        risultato = pronostico.get("risultato_esatto", "N/A")
        confidence = pronostico.get("confidence", 50)
        vincitore = pronostico.get("vincitore", "incerto")
        
        msg += (
            f"🎯 **PRONOSTICO**: `{risultato}`\n"
            f"💡 **Confidence**: {confidence}%\n"
            f"🏆 **Favorito**: {vincitore}\n\n"
        )
        
        # Probabilità
        msg += f"📊 **PROBABILITA'**:\n"
        msg += f"   • 1 (Casa): {probabilita.get('1', 33)}%\n"
        msg += f"   • X (Pareggio): {probabilita.get('X', 33)}%\n"
        msg += f"   • 2 (Trasferta): {probabilita.get('2', 33)}%\n"
        msg += f"   • Over 2.5: {probabilita.get('over25', 50)}%\n"
        msg += f"   • Gol: {probabilita.get('gol', 50)}%\n\n"
        
        # Analisi dettagliata
        if info_analisi:
            msg += f"📈 **ANALISI**:\n"
            msg += f"   Forza {casa}: {info_analisi.get('forza_casa', 70)}/100\n"
            msg += f"   Forza {trasferta}: {info_analisi.get('forza_trasferta', 70)}/100\n"
            
            forma_casa = info_analisi.get('forma_casa', '')
            forma_trasf = info_analisi.get('forma_trasferta', '')
            if forma_casa:
                msg += f"   Forma {casa}: {forma_casa}\n"
            if forma_trasf:
                msg += f"   Forma {trasferta}: {forma_trasf}\n"
            
            # Assenti
            assenti_casa = info_analisi.get('assenti_casa', [])
            assenti_trasf = info_analisi.get('assenti_trasferta', [])
            if assenti_casa:
                msg += f"   ❌ Assenti {casa}: {', '.join(assenti_casa)}\n"
            if assenti_trasf:
                msg += f"   ❌ Assenti {trasferta}: {', '.join(assenti_trasf)}\n"
            
            # Scontri diretti
            ultimi_scontri = info_analisi.get('ultimi_scontri', [])
            if ultimi_scontri:
                msg += f"\n⚔️ **ULTIMI SCONTRI**:\n"
                for scontro in ultimi_scontri[:3]:
                    data = scontro.get('data', 'N/A')
                    ris = scontro.get('risultato', '?-?')
                    vinc = scontro.get('vincitore', 'pareggio')
                    msg += f"   {data}: {ris} (V: {vinc})\n"
            
            msg += "\n"
        
        # Descrizione
        descrizione = pronostico.get("descrizione", "")
        if descrizione:
            msg += f"📝 **ANALISI AI**:\n{descrizione}\n\n"
        
        # Scommesse consigliate
        if scommesse:
            msg += f"{'='*45}\n💰 **SCOMMESSE CONSIGLIATE**:\n\n"
            for i, sc in enumerate(scommesse[:MOSTRA_TOP_SCOMMESSE], 1):
                tipo = sc.get("tipo", "?")
                quota = sc.get("quota", "1.80")
                desc = sc.get("descrizione", "")
                msg += f"{i}. `{tipo}` @ {quota}\n"
                if desc:
                    msg += f"   _{desc}_\n"
            msg += "\n"
        
        msg += f"⚠️ _Le previsioni sono generate da AI e non garantiscono risultati._"
        
        return msg

    # =========================
    # Schedina
    # =========================

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