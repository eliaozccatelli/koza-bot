"""
KOZA Engine - Multi-Engine AI + Dati Reali
Motore ibrido: dati reali da TheSportsDB/API-Football, analisi AI da Groq/Gemini
"""

import logging
from datetime import datetime
from rapidfuzz import process, utils

from src.core.config import (
    GEMINI_API_KEY,
    THESPORTSDB_API_KEY,
    APIFOOTBALL_API_KEY,
    FUZZY_MATCH_THRESHOLD,
    LOG_LEVEL,
    MOSTRA_TOP_SCOMMESSE,
    APIFOOTBALL_TO_SPORTSDB,
)
from src.engines.multi_engine import MultiEngine, get_multi_engine
from src.engines.sportsdb_engine import SportsDBEngine, get_sportsdb_engine
from src.engines.apifootball_engine import APIFootballEngine, get_apifootball_engine
from src.utils.teams_fallback import SQUADRE_FALLBACK, COMPETIZIONI_FALLBACK
from src.utils.team_form_bridge import get_team_form_with_details, get_head_to_head
from src.utils.team_ratings import get_team_rating, rating_from_standings_position, SERIE_A_STANDINGS

logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)


class KozaEngine:
    """Motore KOZA ibrido: dati reali + AI multi-engine (Groq/Gemini)."""

    def __init__(self):
        # Inizializza motore AI multi-engine (Groq -> Gemini -> Default)
        self.ai = get_multi_engine()
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
        comps = self.ai.get_competizioni()
        for comp in comps:
            self.competitions[comp["id"]] = comp["nome"]
        logger.info(f"✓ Competizioni caricate: {len(self.competitions)}")

    # Mappa nome competizione → league_id per API-Football standings
    COMP_TO_LEAGUE_ID = {
        "Serie A": 135, "SA": 135,
        "Premier League": 39, "PL": 39,
        "La Liga": 140, "LL": 140,
        "Bundesliga": 78, "BL": 78,
        "Ligue 1": 61, "L1": 61,
        "Champions League": 2, "CL": 2,
    }

    _standings_cache = {}

    def _get_standings_ratings(self, competizione):
        """
        Recupera classifica reale dalla API e ritorna dict {team_name: posizione}.
        Usa cache per evitare chiamate ripetute.
        """
        if not competizione:
            return None

        league_id = None
        for key, lid in self.COMP_TO_LEAGUE_ID.items():
            if key.lower() in competizione.lower() or competizione.lower() in key.lower():
                league_id = lid
                break

        if not league_id:
            return None

        if league_id in self._standings_cache:
            return self._standings_cache[league_id]

        try:
            standings_data = self.apifootball.get_standings(league_id)
            if not standings_data:
                return None

            team_positions = {}
            for entry in standings_data:
                team_name = entry.get("team", {}).get("name", "")
                position = entry.get("rank", 0)
                if team_name and position:
                    team_positions[team_name] = position

            if team_positions:
                self._standings_cache[league_id] = team_positions
                logger.info(f"Standings API caricate per league {league_id}: {len(team_positions)} squadre")
                return team_positions
        except Exception as e:
            logger.warning(f"Errore standings API per league {league_id}: {e}")

        return None

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
        """Ritorna competizioni con partite disponibili.
        
        Strategia: Unisce risultati da TUTTE le fonti disponibili:
        1. TheSportsDB API (dati reali principali)
        2. API-Football (qualificazioni mondiali, +3gg)
        3. JSON Fallback (partite statiche manuali)
        
        Non si ferma alla prima fonte che trova partite!
        """
        logger.info(f"=== RICERCA COMPETIZIONI === Data: {data}")
        
        # Dizionario per accumulare tutte le competizioni (evita duplicati)
        tutte_competizioni = {}
        sources_found = []
        
        # 1. Prova con TheSportsDB
        logger.info("1. Cerco con TheSportsDB...")
        partite_data = self.sportsdb.get_partite_del_giorno(data)
        competizioni = partite_data.get("competizioni", [])
        if competizioni:
            sources_found.append("TheSportsDB")
            for comp in competizioni:
                comp_id = comp.get("id")
                if comp_id:
                    tutte_competizioni[comp_id] = comp
                    logger.info(f"  ✓ [TheSportsDB] {comp.get('nome')}: {len(comp.get('partite', []))} partite")
        else:
            logger.info("  → TheSportsDB: nessuna partita")
        
        # 2. Prova con API-Football (sempre, anche se TheSportsDB ha trovato)
        logger.info("2. Cerco con API-Football...")
        partite_data = self.apifootball.get_partite_del_giorno(data)
        competizioni = partite_data.get("competizioni", [])
        if competizioni:
            sources_found.append("API-Football")
            for comp in competizioni:
                comp_id = comp.get("id")
                if not comp_id:
                    continue
                # Normalizza ID: se esiste in TheSportsDB, usa quello per evitare duplicati
                canonical_id = APIFOOTBALL_TO_SPORTSDB.get(str(comp_id), comp_id)
                if canonical_id != comp_id:
                    logger.info(f"  Mapping API-Football {comp_id} -> TheSportsDB {canonical_id}")
                if canonical_id not in tutte_competizioni:
                    comp["id"] = canonical_id  # aggiorna ID nel comp
                    tutte_competizioni[canonical_id] = comp
                    logger.info(f"  ✓ [API-Football] {comp.get('nome')}: {len(comp.get('partite', []))} partite")
                else:
                    # Competizione gia' presente da TheSportsDB - NON aggiungere partite duplicate
                    logger.info(f"  ⏭ [API-Football] {comp.get('nome')}: gia' presente da altra fonte, skip")
        else:
            logger.info("  → API-Football: nessuna partita")
        
        # 3. Prova con JSON Fallback (sempre, per coprire date lontane)
        logger.info("3. Cerco con JSON Fallback...")
        partite_data = self.sportsdb.get_fallback_json_partite(data)
        competizioni = partite_data.get("competizioni", [])
        if competizioni:
            sources_found.append("JSON-Fallback")
            for comp in competizioni:
                comp_id = comp.get("id")
                if comp_id and comp_id not in tutte_competizioni:
                    tutte_competizioni[comp_id] = comp
                    logger.info(f"  ✓ [JSON] {comp.get('nome')}: {len(comp.get('partite', []))} partite")
                elif comp_id:
                    # Aggiungi partite alla competizione esistente
                    existing = tutte_competizioni[comp_id]
                    new_matches = comp.get("partite", [])
                    existing["partite"] = existing.get("partite", []) + new_matches
                    logger.info(f"  ✓ [JSON] {comp.get('nome')}: +{len(new_matches)} partite aggiunte")
        else:
            logger.info("  → JSON Fallback: nessuna partita")
        
        # Converte in lista risultato
        result = []
        for comp_id, comp in tutte_competizioni.items():
            comp_name = comp.get("nome", "Unknown")
            self.competitions[comp_id] = comp_name
            result.append((comp_id, comp_name))
        
        sources_str = ", ".join(sources_found) if sources_found else "NESSUNA"
        total_matches = sum(len(comp.get("partite", [])) for comp in tutte_competizioni.values())
        logger.info(f"✓✓✓ TOTALE: {len(result)} competizioni, {total_matches} partite (fonti: {sources_str})")
        
        return result

    def get_partite_campionato(self, comp_id, data=None):
        """Ritorna lista di partite per una competizione.
        
        Ordine fallback:
        1. TheSportsDB
        2. API-Football (se TheSportsDB non trova)
        3. JSON fallback (ultima risorsa)
        """
        if data is None:
            data = datetime.now().date()
        
        partite = []
        sources_tried = []
            
        # 1. Prova con TheSportsDB
        partite = self.sportsdb.get_partite_per_lega(comp_id, data)
        sources_tried.append("TheSportsDB")
        if partite:
            logger.info(f"Comp {comp_id}: trovate {len(partite)} partite su TheSportsDB")
        
        # 2. Se TheSportsDB non trova, prova API-Football
        if not partite:
            logger.info(f"Comp {comp_id}: TheSportsDB non ha trovato partite, provo API-Football")
            # Mappa inversa: TheSportsDB ID -> API-Football ID
            reverse_map = {v: k for k, v in APIFOOTBALL_TO_SPORTSDB.items()}
            apifootball_id = reverse_map.get(str(comp_id))
            apifootball_data = self.apifootball.get_partite_del_giorno(data)
            competizioni = apifootball_data.get("competizioni", [])
            for comp in competizioni:
                cid = str(comp.get("id", ""))
                if cid == str(comp_id) or cid == apifootball_id:
                    partite = comp.get("partite", [])
                    sources_tried.append("API-Football")
                    logger.info(f"  ✓ Trovate {len(partite)} partite su API-Football per {comp_id} (api_id={cid})")
                    break
        
        # 3. Se API-Football non trova, prova JSON fallback
        if not partite:
            logger.info(f"Comp {comp_id}: API-Football non ha trovato partite, provo JSON fallback")
            json_data = self.sportsdb.get_fallback_json_partite(data)
            competizioni = json_data.get("competizioni", [])
            for comp in competizioni:
                if comp.get("id") == comp_id:
                    partite = comp.get("partite", [])
                    sources_tried.append("JSON-Fallback")
                    logger.info(f"  ✓ Trovate {len(partite)} partite nel JSON per {comp_id}")
                    break
        
        result = []
        for p in partite:
            match_id = p.get("id", f"{p.get('casa', '')}_{p.get('trasferta', '')}")
            casa = p.get("casa", "Unknown")
            trasferta = p.get("trasferta", "Unknown")
            api_source = p.get("api_source")
            result.append((casa, trasferta, match_id, api_source))
        
        source_str = " -> ".join(sources_tried) if sources_tried else "nessuna"
        logger.info(f"Comp {comp_id}: {len(result)} partite totali (fonti provate: {source_str})")
        return result

    # =========================
    # Analisi Partita
    # =========================

    def analizza_partita(self, squadra_casa, squadra_trasferta, competizione=None, data=None):
        """Analizza una partita usando Gemini AI arricchita con dati reali."""
        logger.info(f"Analisi partita: {squadra_casa} vs {squadra_trasferta}")

        # Raccogli dati reali dalle fonti disponibili
        forma_casa = None
        forma_trasferta = None
        h2h = None

        try:
            forma_casa = get_team_form_with_details(squadra_casa)
            logger.info(f"Forma {squadra_casa}: {forma_casa.get('form', '?')} (fonte: {forma_casa.get('source', '?')})")
        except Exception as e:
            logger.warning(f"Errore recupero forma {squadra_casa}: {e}")

        try:
            forma_trasferta = get_team_form_with_details(squadra_trasferta)
            logger.info(f"Forma {squadra_trasferta}: {forma_trasferta.get('form', '?')} (fonte: {forma_trasferta.get('source', '?')})")
        except Exception as e:
            logger.warning(f"Errore recupero forma {squadra_trasferta}: {e}")

        try:
            h2h = get_head_to_head(squadra_casa, squadra_trasferta)
            if h2h:
                logger.info(f"H2H trovato: {h2h.get('total_matches', 0)} partite")
        except Exception as e:
            logger.warning(f"Errore recupero H2H: {e}")

        # Rating forza squadre: prova API standings, poi fallback statico
        rating_casa = get_team_rating(squadra_casa)
        rating_trasferta = get_team_rating(squadra_trasferta)

        try:
            standings = self._get_standings_ratings(competizione)
            if standings:
                for team, pos in standings.items():
                    team_lower = team.lower()
                    if squadra_casa.lower() in team_lower or team_lower in squadra_casa.lower():
                        rating_casa = rating_from_standings_position(pos)
                        logger.info(f"Rating API {squadra_casa}: {rating_casa} (pos. {pos})")
                    if squadra_trasferta.lower() in team_lower or team_lower in squadra_trasferta.lower():
                        rating_trasferta = rating_from_standings_position(pos)
                        logger.info(f"Rating API {squadra_trasferta}: {rating_trasferta} (pos. {pos})")
        except Exception as e:
            logger.warning(f"Errore recupero standings: {e}")

        # Predizione ML (se disponibile)
        ml_prediction = None
        try:
            from src.ml.ml_integration import get_ml_prediction
            ml_prediction = get_ml_prediction(squadra_casa, squadra_trasferta)
            if ml_prediction:
                logger.info(f"ML prediction: {ml_prediction.get('prediction')} (conf: {ml_prediction.get('confidence')}%)")
        except Exception as e:
            logger.warning(f"ML non disponibile: {e}")

        # Cerca standings (classifica) per le squadre
        standings_casa = None
        standings_trasferta = None
        for name, info in SERIE_A_STANDINGS.items():
            if name.lower() in squadra_casa.lower() or squadra_casa.lower() in name.lower():
                standings_casa = info
            if name.lower() in squadra_trasferta.lower() or squadra_trasferta.lower() in name.lower():
                standings_trasferta = info

        risultato = self.ai.analizza_partita(
            squadra_casa, squadra_trasferta,
            competizione=competizione, data=data,
            forma_casa=forma_casa, forma_trasferta=forma_trasferta,
            h2h=h2h, rating_casa=rating_casa, rating_trasferta=rating_trasferta,
            ml_prediction=ml_prediction,
            standings_casa=standings_casa, standings_trasferta=standings_trasferta
        )

        # Salva i dati REALI nel risultato (non quelli inventati dall'IA)
        risultato["_dati_reali"] = {
            "forma_casa": forma_casa,
            "forma_trasferta": forma_trasferta,
            "rating_casa": rating_casa,
            "rating_trasferta": rating_trasferta,
            "ml_prediction": ml_prediction,
        }

        return risultato

    def analizza_partita_smart(self, squadra_casa, squadra_trasferta, match_id=None, competizione=None, data=None):
        """Analizza partita con rilevamento automatico stato live/finita/programmata."""
        logger.info(f"Analisi smart: {squadra_casa} vs {squadra_trasferta} (match_id={match_id})")

        try:
            # Strategia 1: match_id numerico da API-Football -> query diretta
            fixture_id = None
            match_info = None

            if match_id and str(match_id).isdigit():
                match_info = self.apifootball.get_match_status(int(match_id))
                if match_info:
                    fixture_id = int(match_id)

            # Strategia 2: cerca per nome squadre su API-Football (per match da TheSportsDB/JSON)
            if not match_info:
                logger.info(f"Match_id '{match_id}' non e' API-Football, cerco per nome squadre...")
                from datetime import date as date_cls
                search_data = data if data else date_cls.today()
                match_info = self.apifootball.cerca_partita_per_squadre(squadra_casa, squadra_trasferta, search_data)
                if match_info:
                    fixture_id = match_info.get("fixture_id")

            if match_info:
                status_short = match_info.get("status_short", "")
                logger.info(f"Stato partita: {status_short} ({match_info.get('status_long', '')})")

                # PARTITA LIVE
                if status_short in ["LIVE", "1H", "2H", "HT", "ET", "PEN_LIVE", "INT"]:
                    return self._analisi_live(squadra_casa, squadra_trasferta, fixture_id, match_info)

                # PARTITA FINITA
                if status_short in ["FT", "AET", "PEN", "AWD", "WO"]:
                    return self._analisi_finita(squadra_casa, squadra_trasferta, fixture_id, match_info)

        except Exception as e:
            logger.warning(f"Errore check stato partita: {e}")

        # Default: analisi pre-partita (NS o errore)
        return self.analizza_partita(squadra_casa, squadra_trasferta, competizione=competizione, data=data)

    def _analisi_live(self, squadra_casa, squadra_trasferta, fixture_id, match_info):
        """Genera analisi per partita in corso con dati live."""
        risultato = match_info.get("risultato", "0-0")
        tempo = match_info.get("tempo", 0)

        logger.info(f"Analisi LIVE: {squadra_casa} vs {squadra_trasferta} - {risultato} ({tempo}')")

        # Recupera statistiche live
        stats = self.apifootball.get_live_statistics(fixture_id) if fixture_id else None

        # Analisi live con Gemini
        analisi_live = None
        try:
            pre_analisi = self.ai.analizza_partita(squadra_casa, squadra_trasferta)
            prob_pre = pre_analisi.get("probabilita", {})
            analisi_live = self.ai.analisi_live(
                squadra_casa, squadra_trasferta,
                risultato, tempo,
                stats or {},
                prob_pre
            )
        except Exception as e:
            logger.warning(f"Errore analisi Gemini live: {e}")

        return {
            "tipo": "live",
            "squadra_casa": squadra_casa,
            "squadra_trasferta": squadra_trasferta,
            "risultato_live": risultato,
            "tempo": tempo,
            "status": match_info.get("status_long", "Live"),
            "statistiche_live": stats,
            "analisi_live": analisi_live,
        }

    def _analisi_finita(self, squadra_casa, squadra_trasferta, fixture_id, match_info):
        """Genera output per partita terminata con statistiche."""
        risultato = match_info.get("risultato", "?-?")
        logger.info(f"Partita FINITA: {squadra_casa} vs {squadra_trasferta} - {risultato}")

        # Recupera statistiche della partita finita
        stats = self.apifootball.get_live_statistics(fixture_id) if fixture_id else None

        return {
            "tipo": "finita",
            "squadra_casa": squadra_casa,
            "squadra_trasferta": squadra_trasferta,
            "risultato_finale": risultato,
            "status": match_info.get("status_long", "Match Finished"),
            "statistiche": stats,
        }

    def formatta_output(self, analisi):
        """Formatta l'output dell'analisi per Telegram. Gestisce 3 tipi: live, finita, pre-partita."""
        tipo = analisi.get("tipo")

        if tipo == "live":
            return self._formatta_live(analisi)
        elif tipo == "finita":
            return self._formatta_finita(analisi)
        else:
            return self._formatta_pre_partita(analisi)

    def _formatta_statistiche(self, stats, casa, trasferta):
        """Formatta le statistiche di una partita (live o finita)."""
        if not stats:
            return ""

        team_names = list(stats.keys())
        if len(team_names) < 2:
            return ""

        t1_stats = stats.get(casa, {}).get("stats", {}) if casa in stats else {}
        t2_stats = stats.get(trasferta, {}).get("stats", {}) if trasferta in stats else {}
        
        # Fallback: se i nomi non corrispondono esattamente, cerca match parziale
        if not t1_stats or not t2_stats:
            team_names = list(stats.keys())
            if len(team_names) >= 2:
                # Prova a matchare per suffisso/nome parziale
                for name in team_names:
                    if casa.lower() in name.lower() or name.lower() in casa.lower():
                        t1_stats = stats[name].get("stats", {})
                    elif trasferta.lower() in name.lower() or name.lower() in trasferta.lower():
                        t2_stats = stats[name].get("stats", {})

        msg = f"📊 **STATISTICHE**:\n"
        msg += f"{'':>20} {casa[:10]:>10} - {trasferta[:10]}\n"

        stat_keys = [
            ("Ball Possession", "Possesso"),
            ("Total Shots", "Tiri totali"),
            ("Shots on Goal", "Tiri in porta"),
            ("Corner Kicks", "Corner"),
            ("Fouls", "Falli"),
            ("Yellow Cards", "Ammonizioni"),
            ("Red Cards", "Espulsioni"),
        ]
        for api_key, label in stat_keys:
            v1 = t1_stats.get(api_key)
            v2 = t2_stats.get(api_key)
            if v1 is not None or v2 is not None:
                msg += f"   {label}: `{v1 if v1 is not None else '-'}` - `{v2 if v2 is not None else '-'}`\n"

        return msg + "\n"

    def _formatta_live(self, analisi):
        """Formatta messaggio per partita LIVE."""
        casa = analisi.get("squadra_casa", "Casa")
        trasferta = analisi.get("squadra_trasferta", "Trasferta")
        risultato = analisi.get("risultato_live", "0-0")
        tempo = analisi.get("tempo", 0)
        status = analisi.get("status", "Live")
        stats = analisi.get("statistiche_live")
        analisi_live = analisi.get("analisi_live") or {}

        msg = (
            f"🔴 **LIVE** 🔴\n"
            f"{'='*45}\n\n"
            f"🏟 **{casa.upper()}**  `{risultato}`  **{trasferta.upper()}**\n"
            f"⏱ **{tempo}'** - _{status}_\n\n"
        )

        # Statistiche live
        msg += self._formatta_statistiche(stats, casa, trasferta)

        # Analisi live di Gemini
        if analisi_live:
            testo = analisi_live.get("analisi_testuale", "")
            if testo:
                msg += f"🧠 **ANALISI LIVE**:\n{testo}\n\n"

            prob_agg = analisi_live.get("probabilita_aggiornate", {})
            if prob_agg:
                msg += f"📈 **PROBABILITA' AGGIORNATE**:\n"
                msg += f"   • 1 (Casa): {prob_agg.get('1', '?')}%\n"
                msg += f"   • X (Pareggio): {prob_agg.get('X', '?')}%\n"
                msg += f"   • 2 (Trasferta): {prob_agg.get('2', '?')}%\n\n"

            pronostico_finale = analisi_live.get("pronostico_finale", "")
            confidence = analisi_live.get("confidence", 0)
            if pronostico_finale:
                msg += f"🎯 **PRONOSTICO FINALE**: `{pronostico_finale}` (confidence: {confidence}%)\n\n"

            consigli = analisi_live.get("consigli_live", [])
            if consigli:
                msg += f"{'='*45}\n💰 **CONSIGLI LIVE**:\n\n"
                for i, c in enumerate(consigli[:4], 1):
                    tipo = c.get("tipo", "?")
                    desc = c.get("descrizione", "")
                    msg += f"{i}. `{tipo}`\n"
                    if desc:
                        msg += f"   {desc}\n"
                msg += "\n"

        msg += f"⚠️ _Dati live da API-Football._"
        return msg

    def _formatta_finita(self, analisi):
        """Formatta messaggio per partita FINITA - stile completamente diverso."""
        casa = analisi.get("squadra_casa", "Casa")
        trasferta = analisi.get("squadra_trasferta", "Trasferta")
        risultato = analisi.get("risultato_finale", "?-?")
        stats = analisi.get("statistiche")

        try:
            gol_casa, gol_trasf = map(int, risultato.split("-"))
            if gol_casa > gol_trasf:
                esito = f"VITTORIA {casa.upper()}"
            elif gol_trasf > gol_casa:
                esito = f"VITTORIA {trasferta.upper()}"
            else:
                esito = "PAREGGIO"
        except (ValueError, IndexError):
            esito = "N/A"

        msg = (
            f"🏁🏁🏁 **PARTITA TERMINATA** 🏁🏁🏁\n"
            f"{'='*45}\n\n"
            f"🏟 **{casa.upper()}**  `{risultato}`  **{trasferta.upper()}**\n\n"
            f"🏆 **{esito}**\n\n"
        )

        # Statistiche finali
        msg += self._formatta_statistiche(stats, casa, trasferta)

        if not stats:
            msg += "_Statistiche non disponibili per questa partita._\n\n"

        msg += f"{'='*45}\n"
        msg += f"_Partita conclusa. Torna indietro per analizzare altre partite._"

        return msg

    def _formatta_pre_partita(self, analisi):
        """Formatta messaggio per analisi pre-partita."""
        pronostico = analisi.get("pronostico", {})
        if not isinstance(pronostico, dict):
            pronostico = {}
        probabilita = analisi.get("probabilita", {})
        if not isinstance(probabilita, dict):
            probabilita = {}
        info_analisi = analisi.get("analisi", {})
        if not isinstance(info_analisi, dict):
            info_analisi = {}
        scommesse = analisi.get("scommesse_consigliate", [])

        casa = analisi.get("squadra_casa", "Casa")
        trasferta = analisi.get("squadra_trasferta", "Trasferta")

        # Mostra quale engine ha generato l'analisi
        engine_id = analisi.get("_engine", "gemini")
        engine_name = self.ai.get_engine_name(engine_id)

        msg = (
            f"🤖 **ANALISI KOZA - Powered by {engine_name}**\n"
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

        # Dati REALI
        dati_reali = analisi.get("_dati_reali", {})
        ml_pred = dati_reali.get("ml_prediction")

        # FORMA: testo narrativo dell'IA (basato su dati reali passati nel prompt)
        forma_casa = info_analisi.get('forma_casa', '') if info_analisi else ''
        forma_trasf = info_analisi.get('forma_trasferta', '') if info_analisi else ''
        if forma_casa or forma_trasf:
            msg += f"📈 **FORMA**:\n"
            if forma_casa:
                msg += f"   {casa}: {forma_casa}\n"
            if forma_trasf:
                msg += f"   {trasferta}: {forma_trasf}\n"
            # Indica la fonte dei dati
            forma_source = dati_reali.get("forma_casa", {})
            if isinstance(forma_source, dict):
                src = forma_source.get("source", "static")
                if src == "telegram_live":
                    msg += "   _(dati live stagione corrente)_\n"
                elif src == "apifootball":
                    msg += "   _(dati stagione 2024/25)_\n"
                else:
                    msg += "   _(dati approssimativi)_\n"
            msg += "\n"

        # Predizione ML
        if ml_pred:
            ml_1 = ml_pred.get('1', '?')
            ml_x = ml_pred.get('X', '?')
            ml_2 = ml_pred.get('2', '?')
            ml_conf = ml_pred.get('confidence', '?')
            ml_pick = ml_pred.get('prediction', '?')
            msg += f"🧠 **ML** (RandomForest): {ml_pick} (conf: {ml_conf}%)\n"
            msg += f"   1: {ml_1}% | X: {ml_x}% | 2: {ml_2}%\n\n"

        # Analisi IA (assenti e scontri diretti)
        if info_analisi:
            assenti_casa = info_analisi.get('assenti_casa', [])
            assenti_trasf = info_analisi.get('assenti_trasferta', [])
            if assenti_casa:
                if isinstance(assenti_casa, str):
                    assenti_casa = [assenti_casa]
                msg += f"   ❌ Assenti {casa}: {', '.join(str(a) for a in assenti_casa)}\n"
            if assenti_trasf:
                if isinstance(assenti_trasf, str):
                    assenti_trasf = [assenti_trasf]
                msg += f"   ❌ Assenti {trasferta}: {', '.join(str(a) for a in assenti_trasf)}\n"

            ultimi_scontri = info_analisi.get('ultimi_scontri', [])
            if ultimi_scontri:
                if isinstance(ultimi_scontri, str):
                    ultimi_scontri = [ultimi_scontri]
                msg += f"\n⚔️ **ULTIMI SCONTRI**:\n"
                for scontro in ultimi_scontri[:3]:
                    if isinstance(scontro, dict):
                        data_s = scontro.get('data', 'N/A')
                        ris = scontro.get('risultato', '?-?')
                        vinc = scontro.get('vincitore', 'pareggio')
                        msg += f"   {data_s}: {ris} (V: {vinc})\n"
                    elif isinstance(scontro, str):
                        msg += f"   {scontro}\n"

            msg += "\n"

        # Scommesse consigliate
        if scommesse:
            msg += f"{'='*45}\n💰 **SCOMMESSE CONSIGLIATE**:\n\n"
            for i, sc in enumerate(scommesse[:MOSTRA_TOP_SCOMMESSE], 1):
                tipo = sc.get("tipo", "?")
                desc = sc.get("descrizione", "")
                prob = sc.get("probabilita", "")
                prob_str = f" ({prob}%)" if prob else ""
                msg += f"{i}. `{tipo}`{prob_str}\n"
                if desc:
                    msg += f"   {desc}\n"
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
        
        return self.ai.calcola_schedina(partite_input)

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