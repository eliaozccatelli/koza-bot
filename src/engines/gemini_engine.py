"""
Gemini AI Engine per KOZA Bot
Gestisce le chiamate all'API Google Gemini per analisi calcistica
"""

import os
import json
import logging
import requests
from datetime import datetime, timedelta

from src.utils.team_ratings import get_team_rating, get_team_form
from src.engines.base_engine import BaseAIEngine

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = "gemini-2.0-flash"


def _get_gemini_api_keys():
    """Ottiene la lista di API key Gemini dalla config o env."""
    try:
        from src.core.config import GEMINI_API_KEYS
        if GEMINI_API_KEYS:
            # Rimuovi eventuali virgolette dalle key
            return [k.strip().strip('"').strip("'") for k in GEMINI_API_KEYS if k.strip()]
    except ImportError:
        pass
    
    # Fallback a variabile singola
    key = os.getenv("GEMINI_API_KEY", "")
    if key:
        # Rimuovi virgolette esterne e splitta
        key = key.strip().strip('"').strip("'")
        return [k.strip().strip('"').strip("'") for k in key.split(",") if k.strip()]
    return []


class GeminiEngine(BaseAIEngine):
    """Motore AI basato su Google Gemini per analisi calcistica."""
    
    def __init__(self, api_keys=None, model=DEFAULT_MODEL):
        # Supporta singola key o lista di key
        if api_keys is None:
            api_keys = _get_gemini_api_keys()
        elif isinstance(api_keys, str):
            api_keys = [api_keys]
        
        self.api_keys = api_keys if api_keys else [GEMINI_API_KEY] if GEMINI_API_KEY else []
        self.current_key_index = 0  # Index della key attualmente in uso
        self.model = model
        self.base_url = f"{GEMINI_BASE_URL}/{model}"
        self.session = requests.Session()
        
    def _get_current_api_key(self):
        """Ritorna l'API key corrente."""
        if not self.api_keys:
            return None
        return self.api_keys[self.current_key_index]
    
    def _switch_to_next_key(self):
        """Passa alla prossima API key disponibile."""
        if len(self.api_keys) > 1:
            self.current_key_index = (self.current_key_index + 1) % len(self.api_keys)
            logger.info(f"🔄 Switching to Gemini API key {self.current_key_index + 1}/{len(self.api_keys)}")
            return True
        return False
        
    def _call_gemini(self, prompt, temperature=0.7, max_tokens=2048):
        """Chiama l'API Gemini con il prompt fornito. Prova multiple key se disponibili."""
        if not self.api_keys:
            logger.error("Nessuna API Key Gemini configurata")
            return None
        
        original_key_index = self.current_key_index
        attempts = 0
        max_attempts = len(self.api_keys)
        
        while attempts < max_attempts:
            api_key = self._get_current_api_key()
            if not api_key:
                logger.error("API Key Gemini non valida")
                return None
            
            url = f"{self.base_url}:generateContent?key={api_key}"
            
            payload = {
                "contents": [{
                    "parts": [{"text": prompt}]
                }],
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": max_tokens,
                    "topP": 0.95,
                    "topK": 40
                }
            }
            
            try:
                response = self.session.post(
                    url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=60
                )
                
                if response.status_code == 429:
                    # Quota exceeded - prova prossima key
                    logger.warning(f"API key {self.current_key_index + 1} quota exceeded (429)")
                    if self._switch_to_next_key():
                        attempts += 1
                        continue
                    else:
                        logger.error("Tutte le API key hanno superato la quota")
                        return None
                
                if response.status_code != 200:
                    logger.error(f"Errore Gemini API: {response.status_code} - {response.text[:200]}")
                    # Per errori diversi da 429, prova comunque la prossima key
                    if self._switch_to_next_key():
                        attempts += 1
                        continue
                    return None
                
                # Successo! Resetta l'index per future chiamate
                data = response.json()
                
                if "candidates" in data and len(data["candidates"]) > 0:
                    content = data["candidates"][0].get("content", {})
                    parts = content.get("parts", [])
                    if parts:
                        # Ripristina index originale per mantenere consistenza
                        self.current_key_index = original_key_index
                        return parts[0].get("text", "").strip()
                
                logger.warning("Risposta Gemini vuota o malformata")
                return None
                
            except Exception as e:
                logger.error(f"Errore chiamata Gemini: {e}")
                if self._switch_to_next_key():
                    attempts += 1
                    continue
                return None
        
        logger.error(f"Tutte le {max_attempts} API key hanno fallito")
        return None
    
    def _parse_json_response(self, text):
        """Estrae JSON dalla risposta testuale di Gemini."""
        if not text:
            return None
            
        # Prova a trovare JSON tra backticks
        import re
        
        # Pattern per JSON in ```json ... ```
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except:
                pass
        
        # Prova a parsare tutto il testo come JSON
        try:
            return json.loads(text)
        except:
            pass
            
        # Prova a trovare qualsiasi oggetto JSON
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except:
                pass
                
        logger.warning(f"Impossibile parsare JSON da: {text[:200]}")
        return None
    
    # =========================
    # Metodi Pubblici - Partite e Competizioni
    # =========================
    
    def get_partite_del_giorno(self, data=None):
        """
        Ottiene le partite del giorno specificato usando Gemini.
        Ritorna un dict con le competizioni e le partite.
        """
        if data is None:
            data = datetime.now().date()
        
        # Prova con Gemini prima
        result = self._get_partite_gemini(data)
        
        # Se Gemini fallisce, usa fallback
        if not result or not result.get("competizioni"):
            logger.warning("Gemini non ha risposto, uso fallback di test")
            result = self._get_partite_fallback(data)
        
        return result
    
    def _get_partite_gemini(self, data):
        """Chiama Gemini per partite reali."""
        prompt = f"""
        Elenca le partite di calcio previste per il giorno {data.strftime('%d/%m/%Y')}.
        Per ogni competizione (Serie A, Premier League, La Liga, Bundesliga, Ligue 1),
        elenca le partite previste con nomi delle squadre.
        
        Ritorna in formato JSON:
        {{
            "competizioni": [
                {{
                    "id": "IT1",
                    "nome": "Serie A",
                    "partite": [
                        {{"id": "1", "casa": "Inter", "trasferta": "Milan"}},
                        {{"id": "2", "casa": "Juventus", "trasferta": "Napoli"}}
                    ]
                }}
            ]
        }}
        """
        
        risposta = self._call_gemini(prompt, temperature=0.3)
        if not risposta:
            return None
            
        data_parsed = self._parse_json_response(risposta)
        return data_parsed
    
    def _get_partite_fallback(self, data):
        """Fallback con partite di test."""
        giorno = data.strftime('%d/%m/%Y')
        return {
            "competizioni": [
                {
                    "id": "IT1",
                    "nome": f"Serie A - {giorno}",
                    "partite": [
                        {"id": "IT1_1", "casa": "Inter", "trasferta": "Milan"},
                        {"id": "IT1_2", "casa": "Juventus", "trasferta": "Napoli"},
                        {"id": "IT1_3", "casa": "Roma", "trasferta": "Lazio"}
                    ]
                },
                {
                    "id": "EN1",
                    "nome": f"Premier League - {giorno}",
                    "partite": [
                        {"id": "EN1_1", "casa": "Manchester City", "trasferta": "Liverpool"},
                        {"id": "EN1_2", "casa": "Arsenal", "trasferta": "Chelsea"}
                    ]
                },
                {
                    "id": "ES1",
                    "nome": f"La Liga - {giorno}",
                    "partite": [
                        {"id": "ES1_1", "casa": "Real Madrid", "trasferta": "Barcelona"},
                        {"id": "ES1_2", "casa": "Atletico Madrid", "trasferta": "Sevilla"}
                    ]
                },
                {
                    "id": "DE1",
                    "nome": f"Bundesliga - {giorno}",
                    "partite": [
                        {"id": "DE1_1", "casa": "Bayern Monaco", "trasferta": "Dortmund"},
                        {"id": "DE1_2", "casa": "Leverkusen", "trasferta": "RB Leipzig"}
                    ]
                }
            ]
        }
    
    def get_competizioni(self):
        """Ritorna la lista delle competizioni disponibili."""
        return [
            {"id": "serie_a", "nome": "Serie A", "paese": "Italia"},
            {"id": "premier_league", "nome": "Premier League", "paese": "Inghilterra"},
            {"id": "la_liga", "nome": "La Liga", "paese": "Spagna"},
            {"id": "bundesliga", "nome": "Bundesliga", "paese": "Germania"},
            {"id": "ligue_1", "nome": "Ligue 1", "paese": "Francia"},
            {"id": "champions_league", "nome": "Champions League", "paese": "Europa"},
            {"id": "europa_league", "nome": "Europa League", "paese": "Europa"},
            {"id": "conference_league", "nome": "Conference League", "paese": "Europa"},
        ]
    
    def get_partite_campionato(self, comp_id, data=None):
        """Ritorna le partite di una specifica competizione per una data."""
        # Ottieni tutte le partite del giorno
        partite_giorno = self.get_partite_del_giorno(data)
        
        # Filtra per la competizione richiesta
        for comp in partite_giorno.get("competizioni", []):
            if comp["id"] == comp_id:
                return comp.get("partite", [])
        
        return []
    
    # =========================
    # Metodi Pubblici - Analisi Partita
    # =========================
    
    def analizza_partita(self, squadra_casa, squadra_trasferta, competizione=None, data=None,
                         forma_casa=None, forma_trasferta=None, h2h=None,
                         rating_casa=None, rating_trasferta=None, ml_prediction=None,
                         standings_casa=None, standings_trasferta=None):
        """
        Analizza una partita specifica usando Gemini AI.
        Accetta dati reali opzionali per arricchire il prompt.
        """
        data_str = ""
        if data:
            data_str = f" in programma il {data.strftime('%d/%m/%Y')}"

        comp_info = f" ({competizione})" if competizione else ""

        # Costruisci sezione dati reali per il prompt
        dati_reali = self._build_data_context(
            squadra_casa, squadra_trasferta,
            forma_casa, forma_trasferta, h2h,
            rating_casa, rating_trasferta,
            ml_prediction=ml_prediction,
            standings_casa=standings_casa, standings_trasferta=standings_trasferta
        )

        prompt = f"""Sei un esperto tipster calcistico professionista. Analizza la partita {squadra_casa} vs {squadra_trasferta}{comp_info}{data_str}.

{dati_reali}

Basandoti sui DATI REALI forniti sopra (se presenti), fornisci un pronostico dettagliato.
Se i dati sono segnalati come "approssimativi", usali come indicazione ma integra con la tua conoscenza.
Se e' presente una PREDIZIONE ML, confrontala con la tua analisi. Se le probabilita' ML differiscono significativamente, adatta il tuo pronostico o motiva perche' la ritieni errata.

COERENZA OBBLIGATORIA:
- Le probabilita' 1/X/2 DEVONO essere coerenti col risultato previsto (se prevedi vittoria casa, prob_1 > prob_2)
- X non puo' essere sotto 10% (nessuna partita reale ha pareggio sotto 10%)
- Se prevedi 3+ gol totali, over25 DEVE essere almeno 60%
- La confidence deve riflettere quanto sei sicuro: partita equilibrata = max 55%

IMPORTANTE per le scommesse consigliate:
- Scegli le 4-5 scommesse PIU' PROBABILI e FATTIBILI basandoti sui dati
- VARIA i tipi di scommessa! Non dare sempre 1X2 + Over 2.5
- Scegli tra: 1, X, 2, 1X, X2, 12, Over/Under (1.5, 2.5, 3.5), Gol/NoGol, Multigol (0-1, 1-2, 2-3, 2-4, 3-5), Handicap (-1, +1), Combo (es. "1 + Over 1.5"), Parziale/Finale (1/1, X/2), Primo Tempo (1 PT, Over 0.5 PT)
- Per ogni scommessa indica la probabilita' stimata di vincita (0-100)
- Ordina dalla piu' probabile alla meno probabile
- Motiva brevemente ogni scelta

Rispondi con questo formato JSON ESATTO:
{{
  "pronostico": {{
    "risultato_esatto": "2-1",
    "vincitore": "casa",
    "over_under": "Over 2.5",
    "gol_nogol": "Gol",
    "confidence": 75,
    "descrizione": "Breve motivazione del pronostico..."
  }},
  "probabilita": {{
    "1": 55,
    "X": 25,
    "2": 20,
    "over25": 65,
    "over35": 40,
    "gol": 70,
    "cartellini_over45": 60
  }},
  "analisi": {{
    "forza_casa": 85,
    "forza_trasferta": 70,
    "forma_casa": "Molto buona (4 vittorie nelle ultime 5)",
    "forma_trasferta": "Buona (3 vittorie, 1 pareggio, 1 sconfitta)",
    "assenti_casa": ["Giocatore X (infortunato)"],
    "assenti_trasferta": [],
    "ultimi_scontri": [
      {{"data": "15/09/2024", "risultato": "2-1", "vincitore": "casa"}}
    ]
  }},
  "scommesse_consigliate": [
    {{"tipo": "1 + Over 1.5", "probabilita": 62, "descrizione": "Casa vince e almeno 2 gol, forma ottima"}},
    {{"tipo": "Multigol 2-4", "probabilita": 58, "descrizione": "Range gol piu' probabile basato sulle medie"}},
    {{"tipo": "Gol", "probabilita": 55, "descrizione": "Entrambe in gol nelle ultime 4 su 5"}},
    {{"tipo": "Over 2.5", "probabilita": 52, "descrizione": "Media gol alta per entrambe"}}
  ]
}}

Confidence 0-100. Probabilita' numeri interi 0-100. Analisi REALISTICA.
Rispondi SOLO con il JSON valido."""

        response = self._call_gemini(prompt, temperature=0.5, max_tokens=4096)

        if not response:
            logger.error("Gemini non ha risposto per l'analisi partita")
            return self._default_analysis(squadra_casa, squadra_trasferta)

        data_parsed = self._parse_json_response(response)

        if data_parsed:
            logger.info(f"Analisi Gemini completata per {squadra_casa} vs {squadra_trasferta}")
            # Valida coerenza della risposta Gemini
            data_parsed = self._validate_gemini_response(data_parsed)
            # Usa le scommesse di Gemini direttamente. Fallback solo se mancanti/vuote.
            scommesse = data_parsed.get("scommesse_consigliate", [])
            if not scommesse or len(scommesse) == 0:
                risultato = data_parsed.get("pronostico", {}).get("risultato_esatto", "1-1")
                prob = data_parsed.get("probabilita", {})
                conf = data_parsed.get("pronostico", {}).get("confidence", 50)
                data_parsed["scommesse_consigliate"] = self._generate_smart_scommesse(
                    risultato, squadra_casa, squadra_trasferta,
                    probabilita=prob, confidence=conf
                )
            return data_parsed
        else:
            logger.warning("Risposta Gemini non parsabile, uso default")
            return self._default_analysis(squadra_casa, squadra_trasferta)

    def _validate_gemini_response(self, data):
        """
        Valida e corregge incoerenze nella risposta Gemini.
        Es: pronostico 4-0 ma prob casa 48% → corregge.
        """
        try:
            pronostico = data.get("pronostico", {})
            prob = data.get("probabilita", {})
            vincitore = pronostico.get("vincitore", "")
            risultato = pronostico.get("risultato_esatto", "1-1")

            prob_1 = prob.get("1", 33)
            prob_x = prob.get("X", 33)
            prob_2 = prob.get("2", 33)

            # 1. X mai sotto 10% (irrealistico)
            if prob_x < 10:
                deficit = 10 - prob_x
                prob_x = 10
                # Distribuisci il deficit proporzionalmente
                if prob_1 + prob_2 > 0:
                    ratio = prob_1 / (prob_1 + prob_2)
                    prob_1 -= deficit * ratio
                    prob_2 -= deficit * (1 - ratio)
                logger.info(f"Validazione: X corretto da {prob.get('X')}% a 10%")

            # 2. Probabilità coerenti col vincitore
            if vincitore == "casa" and prob_1 < prob_2:
                prob_1, prob_2 = prob_2, prob_1
                logger.info("Validazione: swap prob 1/2 per coerenza col vincitore casa")
            elif vincitore == "trasferta" and prob_2 < prob_1:
                prob_1, prob_2 = prob_2, prob_1
                logger.info("Validazione: swap prob 1/2 per coerenza col vincitore trasferta")

            # Normalizza a 100
            total = prob_1 + prob_x + prob_2
            if total > 0 and abs(total - 100) > 1:
                prob_1 = round(prob_1 * 100 / total, 1)
                prob_x = round(prob_x * 100 / total, 1)
                prob_2 = round(100 - prob_1 - prob_x, 1)

            prob["1"] = round(prob_1, 1)
            prob["X"] = round(prob_x, 1)
            prob["2"] = round(prob_2, 1)

            # 3. Over 2.5 coerente coi gol previsti
            try:
                gol_parts = risultato.split('-')
                totale_gol = int(gol_parts[0]) + int(gol_parts[1])
                over25 = prob.get("over25", 50)

                if totale_gol >= 3 and over25 < 55:
                    prob["over25"] = max(60, over25 + 20)
                    logger.info(f"Validazione: over25 corretto da {over25}% a {prob['over25']}% ({totale_gol} gol previsti)")
                elif totale_gol <= 2 and over25 > 55:
                    prob["over25"] = min(45, over25 - 15)
                    logger.info(f"Validazione: over25 corretto da {over25}% a {prob['over25']}% ({totale_gol} gol previsti)")
            except (ValueError, IndexError):
                pass

            # 4. Confidence coerente
            confidence = pronostico.get("confidence", 50)
            prob_vincitore = prob_1 if vincitore == "casa" else (prob_2 if vincitore == "trasferta" else prob_x)
            diff_12 = abs(prob_1 - prob_2)

            if prob_vincitore < 40 and confidence > 55:
                pronostico["confidence"] = min(confidence, 55)
                logger.info(f"Validazione: confidence abbassata da {confidence} a {pronostico['confidence']} (prob vincitore bassa)")
            elif diff_12 < 10 and confidence > 50:
                pronostico["confidence"] = min(confidence, 50)
                logger.info(f"Validazione: confidence abbassata da {confidence} a {pronostico['confidence']} (partita equilibrata)")

            data["pronostico"] = pronostico
            data["probabilita"] = prob

        except Exception as e:
            logger.warning(f"Errore validazione risposta: {e}")

        return data

    def _build_data_context(self, casa, trasferta, forma_casa, forma_trasferta, h2h,
                            rating_casa, rating_trasferta, ml_prediction=None):
        """Costruisce la sezione DATI REALI per il prompt Gemini."""
        lines = ["DATI REALI DISPONIBILI:"]

        # Forma casa
        if forma_casa:
            source = forma_casa.get('source', 'static')
            source_tags = {
                'telegram_live': 'dati live gruppo',
                'training_data': 'dati reali stagione',
                'apifootball': 'dati API',
                'rapidapi': 'dati live',
            }
            tag = source_tags.get(source, 'approssimativo')
            form_str = forma_casa.get('form', '?')
            w = forma_casa.get('wins', 0)
            d = forma_casa.get('draws', 0)
            l = forma_casa.get('losses', 0)
            gf = forma_casa.get('goals_for', 0)
            ga = forma_casa.get('goals_against', 0)
            line = f"- {casa}: Forma ultime 5 = {form_str} ({w}V-{d}P-{l}S"
            if gf or ga:
                line += f", {gf} gol fatti, {ga} subiti"
            line += f") [{tag}]"
            lines.append(line)

        # Forma trasferta
        if forma_trasferta:
            source = forma_trasferta.get('source', 'static')
            source_tags = {
                'telegram_live': 'dati live gruppo',
                'training_data': 'dati reali stagione',
                'apifootball': 'dati API',
                'rapidapi': 'dati live',
            }
            tag = source_tags.get(source, 'approssimativo')
            form_str = forma_trasferta.get('form', '?')
            w = forma_trasferta.get('wins', 0)
            d = forma_trasferta.get('draws', 0)
            l = forma_trasferta.get('losses', 0)
            gf = forma_trasferta.get('goals_for', 0)
            ga = forma_trasferta.get('goals_against', 0)
            line = f"- {trasferta}: Forma ultime 5 = {form_str} ({w}V-{d}P-{l}S"
            if gf or ga:
                line += f", {gf} gol fatti, {ga} subiti"
            line += f") [{tag}]"
            lines.append(line)

        # Rating
        if rating_casa and rating_trasferta:
            lines.append(f"- Forza stimata: {casa} {rating_casa}/100, {trasferta} {rating_trasferta}/100")

        # H2H
        if h2h:
            total = h2h.get('total_matches', 0)
            if total > 0:
                w1 = h2h.get('team1_wins', 0)
                w2 = h2h.get('team2_wins', 0)
                dr = h2h.get('draws', 0)
                lines.append(f"- Scontri diretti (ultimi {total}): {casa} {w1}V, {dr}P, {trasferta} {w2}V")
                matches = h2h.get('matches', [])
                for m in matches[:3]:
                    lines.append(f"  - {m.get('date', '?')}: {m.get('score', '?')} ({m.get('result', '?')})")

        # Predizione ML
        if ml_prediction:
            lines.append("")
            lines.append("PREDIZIONE ML (modello RandomForest, basato su dati storici):")
            lines.append(f"- 1: {ml_prediction.get('1', '?')}%, X: {ml_prediction.get('X', '?')}%, 2: {ml_prediction.get('2', '?')}%")
            lines.append(f"- Predizione: {ml_prediction.get('prediction', '?')} (confidence: {ml_prediction.get('confidence', '?')}%)")
            lines.append("- Confronta con la tua analisi. Se discordi, motiva la differenza.")

        if len(lines) == 1:
            lines.append("- Nessun dato specifico disponibile. Usa la tua conoscenza aggiornata.")

        return "\n".join(lines)
    
    def _generate_smart_scommesse(self, risultato, casa, trasferta,
                                   probabilita=None, confidence=None):
        """
        Genera scommesse intelligenti basate su risultato, probabilità e confidence.
        Confidence bassa → scommesse safe. Confidence alta → scommesse aggressive.
        """
        try:
            gol_casa, gol_trasf = map(int, risultato.split('-'))
            totale_gol = gol_casa + gol_trasf

            prob_1 = probabilita.get("1", 33) if probabilita else 33
            prob_x = probabilita.get("X", 33) if probabilita else 33
            prob_2 = probabilita.get("2", 33) if probabilita else 33
            over25 = probabilita.get("over25", 50) if probabilita else 50
            prob_gol = probabilita.get("gol", 50) if probabilita else 50
            conf = confidence if confidence else 50

            safe = conf < 55  # Partita incerta → scommesse conservative

            scommesse = []

            # 1. Esito basato su probabilità (non solo risultato)
            if gol_casa > gol_trasf:
                margin = gol_casa - gol_trasf
                if prob_1 >= 60 and not safe:
                    scommesse.append({
                        "tipo": "1", "probabilita": int(prob_1),
                        "descrizione": f"Vittoria {casa} ({prob_1:.0f}% prob)"
                    })
                    if margin >= 2 and conf >= 65:
                        scommesse.append({
                            "tipo": "1 -1.5", "probabilita": int(prob_1 * 0.6),
                            "descrizione": f"{casa} vince con margine"
                        })
                elif prob_1 >= 45:
                    scommesse.append({
                        "tipo": "1X", "probabilita": int(prob_1 + prob_x),
                        "descrizione": f"{casa} non perde ({prob_1 + prob_x:.0f}% prob)"
                    })
                else:
                    scommesse.append({
                        "tipo": "1X", "probabilita": int(prob_1 + prob_x),
                        "descrizione": f"Partita equilibrata, {casa} non perde"
                    })
            elif gol_trasf > gol_casa:
                margin = gol_trasf - gol_casa
                if prob_2 >= 60 and not safe:
                    scommesse.append({
                        "tipo": "2", "probabilita": int(prob_2),
                        "descrizione": f"Vittoria {trasferta} ({prob_2:.0f}% prob)"
                    })
                    if margin >= 2 and conf >= 65:
                        scommesse.append({
                            "tipo": "2 -1.5", "probabilita": int(prob_2 * 0.6),
                            "descrizione": f"{trasferta} vince con margine"
                        })
                elif prob_2 >= 45:
                    scommesse.append({
                        "tipo": "X2", "probabilita": int(prob_2 + prob_x),
                        "descrizione": f"{trasferta} non perde ({prob_2 + prob_x:.0f}% prob)"
                    })
                else:
                    scommesse.append({
                        "tipo": "X2", "probabilita": int(prob_2 + prob_x),
                        "descrizione": f"Partita equilibrata, {trasferta} non perde"
                    })
            else:
                scommesse.append({
                    "tipo": "X", "probabilita": int(prob_x),
                    "descrizione": f"Pareggio previsto ({risultato})"
                })

            # 2. Over/Under basato su probabilità over25 (non solo totale gol)
            if over25 >= 60:
                scommesse.append({
                    "tipo": "Over 2.5", "probabilita": int(over25),
                    "descrizione": f"Almeno 3 gol ({over25:.0f}% prob)"
                })
                if totale_gol >= 4 and conf >= 60:
                    scommesse.append({
                        "tipo": "Over 3.5", "probabilita": int(over25 * 0.65),
                        "descrizione": "Partita aperta"
                    })
            elif over25 <= 40:
                scommesse.append({
                    "tipo": "Under 2.5", "probabilita": int(100 - over25),
                    "descrizione": f"Pochi gol attesi ({100 - over25:.0f}% prob)"
                })
                if totale_gol <= 1:
                    scommesse.append({
                        "tipo": "Under 1.5", "probabilita": int((100 - over25) * 0.65),
                        "descrizione": "Partita chiusa"
                    })
            else:
                # Over25 incerto (40-60%): multigol come scommessa safe
                if totale_gol <= 3:
                    scommesse.append({
                        "tipo": "Multigol 1-3", "probabilita": 60,
                        "descrizione": "Range gol più probabile"
                    })
                else:
                    scommesse.append({
                        "tipo": "Multigol 2-4", "probabilita": 55,
                        "descrizione": "Range gol più probabile"
                    })

            # 3. Gol/No Gol
            if prob_gol >= 60:
                scommesse.append({
                    "tipo": "Gol", "probabilita": int(prob_gol),
                    "descrizione": f"Entrambe segnano ({prob_gol:.0f}% prob)"
                })
            elif prob_gol <= 40:
                scommesse.append({
                    "tipo": "No Gol", "probabilita": int(100 - prob_gol),
                    "descrizione": f"Almeno una non segna ({100 - prob_gol:.0f}% prob)"
                })

            # Ordina per probabilità decrescente
            scommesse.sort(key=lambda x: x.get("probabilita", 0), reverse=True)
            return scommesse[:4]

        except (ValueError, IndexError):
            return [
                {"tipo": "1X2", "probabilita": 50, "descrizione": "Esito finale"},
                {"tipo": "Over/Under 2.5", "probabilita": 50, "descrizione": "Totale gol"}
            ]
    
    def _default_analysis(self, casa, trasferta):
        """
        Ritorna un'analisi di default se Gemini fallisce.
        Usa rating realistici delle squadre da database statico.
        """
        # Usa rating reali delle squadre (0-100)
        forza_casa = get_team_rating(casa)
        forza_trasf = get_team_rating(trasferta)
        
        # Aggiungi piccola variazione casuale giornaliera (±5 punti)
        import random
        from datetime import date
        random.seed(date.today().toordinal())  # Seed basato sulla data
        forza_casa += random.randint(-5, 5)
        forza_trasf += random.randint(-5, 5)
        
        # Probabilità basate sulla forza relativa
        diff = forza_casa - forza_trasf
        prob_1 = min(75, max(25, 50 + diff * 0.8 + random.randint(-3, 3)))
        prob_2 = min(75, max(25, 50 - diff * 0.8 + random.randint(-3, 3)))
        prob_x = 100 - prob_1 - prob_2
        
        # Normalizza se necessario
        if prob_x < 10:
            prob_1 = max(25, prob_1 - 5)
            prob_2 = max(25, prob_2 - 5)
            prob_x = 100 - prob_1 - prob_2
        
        # Risultato pronosticato basato sulle probabilità
        if prob_1 > prob_2 and prob_1 > prob_x:
            gol_casa = 1 + (forza_casa // 30) + random.randint(0, 1)
            gol_trasf = random.randint(0, forza_trasf // 40)
            risultato = f"{gol_casa}-{gol_trasf}"
            vincitore = "casa"
            consiglio = "1"
            desc_cons = f"Vittoria {casa} favorita"
        elif prob_2 > prob_1 and prob_2 > prob_x:
            gol_casa = random.randint(0, forza_casa // 40)
            gol_trasf = 1 + (forza_trasf // 30) + random.randint(0, 1)
            risultato = f"{gol_casa}-{gol_trasf}"
            vincitore = "trasferta"
            consiglio = "2"
            desc_cons = f"Vittoria {trasferta} possibile"
        else:
            gol_casa = 1 + (forza_casa // 35)
            gol_trasf = 1 + (forza_trasf // 35)
            risultato = f"{gol_casa}-{gol_trasf}"
            vincitore = "pareggio"
            consiglio = "X"
            desc_cons = "Pareggio probabile"
        
        # Forma realistica basata sul rating
        forma_casa = get_team_form(casa)
        forma_trasf = get_team_form(trasferta)
        
        # Over/Under basato sulla forza offensiva complessiva
        media_forza = (forza_casa + forza_trasf) / 2
        over25 = min(80, max(30, int(media_forza * 0.6) + random.randint(-5, 5)))
        gol = min(75, max(35, over25 - 10 + random.randint(-5, 5)))
        
        # Confidence basata sulla differenza di forza
        confidence = min(90, max(45, 50 + abs(diff) // 2))
        
        # Quote variabili basate sulle probabilità
        quota_1 = f"{1.2 + (100/prob_1):.2f}" if prob_1 > 0 else "3.50"
        quota_x = f"{1.2 + (100/prob_x):.2f}" if prob_x > 0 else "3.20"
        quota_2 = f"{1.2 + (100/prob_2):.2f}" if prob_2 > 0 else "3.50"
        
        # Genera scommesse consigliate variabili basate sulle probabilità
        scommesse = []
        
        # 1. Esito principale (1/X/2) o doppia chance
        if prob_1 > 55:
            scommesse.append({"tipo": "1", "descrizione": "Vittoria casa netta"})
        elif prob_2 > 55:
            scommesse.append({"tipo": "2", "descrizione": "Vittoria trasferta netta"})
        elif prob_x > 35:
            scommesse.append({"tipo": "X", "descrizione": "Pareggio probabile"})
        elif prob_1 + prob_x > 65:
            scommesse.append({"tipo": "1X", "descrizione": "Casa non perde"})
        elif prob_2 + prob_x > 65:
            scommesse.append({"tipo": "X2", "descrizione": "Trasferta non perde"})
        else:
            scommesse.append({"tipo": "12", "descrizione": "Non pareggia"})
        
        # 2. Gol / No Gol con variante multigol
        if gol > 60:
            scommesse.append({"tipo": "Gol", "descrizione": "Entrambe segnano"})
            # Multigol basato sulla forza offensiva
            if media_forza > 75:
                scommesse.append({"tipo": "Multigol 2-4", "descrizione": "Totale gol 2-4"})
            else:
                scommesse.append({"tipo": "Multigol 1-3", "descrizione": "Totale gol 1-3"})
        elif gol < 40:
            scommesse.append({"tipo": "No Gol", "descrizione": "Almeno una non segna"})
            scommesse.append({"tipo": "Multigol 0-2", "descrizione": "Pochi gol previsti"})
        else:
            # Caso incerto
            scommesse.append({"tipo": "Gol", "descrizione": "Rischio Gol"})
            scommesse.append({"tipo": "Under 3.5", "descrizione": "Massimo 3 gol"})
        
        # 3. Over/Under con varianti
        if over25 > 60:
            scommesse.append({"tipo": "Over 2.5", "descrizione": "Più di 2 gol"})
            if over25 > 70:
                scommesse.append({"tipo": "Over 3.5", "descrizione": "Partita aperta"})
        elif over25 < 40:
            scommesse.append({"tipo": "Under 2.5", "descrizione": "Meno di 2 gol"})
            if media_forza < 65:
                scommesse.append({"tipo": "Under 1.5", "descrizione": "Partita chiusa"})
        
        # 4. Gol squadra specifici
        if forza_casa > forza_trasf + 10:
            scommesse.append({"tipo": f"Gol {casa}", "descrizione": f"{casa} segna"})
        elif forza_trasf > forza_casa + 10:
            scommesse.append({"tipo": f"Gol {trasferta}", "descrizione": f"{trasferta} segna"})
        
        return {
            "pronostico": {
                "risultato_esatto": risultato,
                "vincitore": vincitore,
                "over_under": "Over 2.5" if over25 > 50 else "Under 2.5",
                "gol_nogol": "Gol" if gol > 50 else "No Gol",
                "confidence": confidence,
                "descrizione": f"Analisi {casa} vs {trasferta}: {casa} (forza: {forza_casa}/100), {trasferta} (forza: {forza_trasf}/100). {desc_cons}."
            },
            "probabilita": {
                "1": prob_1,
                "X": prob_x,
                "2": prob_2,
                "over25": over25,
                "over35": max(20, over25 - 20),
                "gol": gol,
                "cartellini_over45": 40 + random.randint(0, 20)
            },
            "analisi": {
                "forza_casa": forza_casa,
                "forza_trasferta": forza_trasf,
                "forma_casa": forma_casa,
                "forma_trasferta": forma_trasf,
                "assenti_casa": [],
                "assenti_trasferta": [],
                "ultimi_scontri": []
            },
            "scommesse_consigliate": self._generate_smart_scommesse(
                risultato, casa, trasferta,
                probabilita={"1": prob_1, "X": prob_x, "2": prob_2,
                              "over25": over25, "gol": gol},
                confidence=confidence
            )
        }
    
    def get_info_squadra(self, nome_squadra):
        """Ottiene informazioni su una squadra usando Gemini."""
        prompt = f"""Fornisci informazioni sulla squadra {nome_squadra}.

Formato JSON:
{{
  "nome": "{nome_squadra}",
  "paese": "Italia",
  "competizione": "Serie A",
  "stadio": "Nome Stadio",
  "allenatore": "Nome Allenatore",
  "classifica": 5,
  "punti": 45,
  "forma": "WWDLW"
}}

Rispondi SOLO con il JSON valido."""

        response = self._call_gemini(prompt, temperature=0.5)
        return self._parse_json_response(response) or {"nome": nome_squadra}
    
    def calcola_schedina(self, partite_list):
        """
        Calcola una schedina multipla basata su una lista di partite.
        partite_list: lista di dict con {'casa': 'Team A', 'trasferta': 'Team B'}
        """
        partite_str = "\n".join([f"{p['casa']} vs {p['trasferta']}" for p in partite_list])
        
        prompt = f"""Analizza queste partite per una schedina multipla:

{partite_str}

Per ogni partita fornisci:
1. Esito consigliato (1, X, 2, Over 2.5, Under 2.5, Gol, No Gol)
2. Probabilità stimata
3. Quota indicativa

Restituisci questo JSON:
{{
  "schedina": [
    {{
      "partita": "Inter vs Milan",
      "consiglio": "1",
      "probabilita": 55,
      "quota": "1.75"
    }}
  ],
  "combo_principale": {{
    "esiti": ["1", "Over 2.5", "X"],
    "quota_totale": "8.50",
    "probabilita": 12
  }},
  "analisi_complessiva": "La combo principale copre..."
}}

Rispondi SOLO con il JSON valido."""

        response = self._call_gemini(prompt, temperature=0.6, max_tokens=4096)
        
        if not response:
            # Ritorna una schedina di default
            return {
                "schedina": [
                    {
                        "partita": f"{p['casa']} vs {p['trasferta']}",
                        "consiglio": "1",
                        "probabilita": 50,
                        "quota": "1.80"
                    }
                    for p in partite_list
                ],
                "combo_principale": {
                    "esiti": ["1"] * len(partite_list),
                    "quota_totale": f"{1.8 ** len(partite_list):.2f}",
                    "probabilita": 10
                },
                "analisi_complessiva": "Schedina generata con valori di default"
            }
            
        return self._parse_json_response(response) or {}

    def analisi_live(self, squadra_casa, squadra_trasferta, risultato_live, tempo, statistiche_live, prob_pre_partita=None):
        """
        Analizza le statistiche live con Gemini AI e fornisce pronostico aggiornato.
        
        Args:
            squadra_casa: Nome squadra casa
            squadra_trasferta: Nome squadra trasferta  
            risultato_live: Risultato attuale (es. "2-1")
            tempo: Minuto di gioco
            statistiche_live: Dict con statistiche per squadra
            prob_pre_partita: Probabilità pre-partita (opzionale)
        
        Returns:
            Dict con analisi aggiornata, nuove probabilità, consigli
        """
        # Formatta statistiche per il prompt
        stats_text = ""
        for team_name, team_data in statistiche_live.items():
            stats_dict = team_data.get("stats", {})
            stats_text += f"\n{team_name}:\n"
            for key, val in stats_dict.items():
                if val is not None:
                    stats_text += f"  - {key}: {val}\n"
        
        # Probabilità pre-partita come contesto
        prob_context = ""
        if prob_pre_partita:
            prob_context = f"""
Probabilità pre-partita:
- 1 (vittoria {squadra_casa}): {prob_pre_partita.get('1', 33)}%
- X (pareggio): {prob_pre_partita.get('X', 33)}%  
- 2 (vittoria {squadra_trasferta}): {prob_pre_partita.get('2', 33)}%
"""
        
        prompt = f"""Sei un esperto analista calcistico. Analizza questa partita IN DIRETTA e aggiorna le probabilità basandoti sulle statistiche live.

PARTITA: {squadra_casa} vs {squadra_trasferta}
TEMPO: {tempo} minuti
RISULTATO ATTUALE: {risultato_live}

STATISTICHE LIVE:{stats_text}
{prob_context}

Fornisci un'analisi AGGIORNATA considerando:
1. Chi sta dominando il gioco (possesso, tiri, pericolosità)
2. Se il risultato attuale è sorprendente o atteso
3. Probabilità che il risultato cambi nel tempo rimanente
4. Squadra più stanca / più fresca
5. Pressione offensiva attuale

Rispondi SOLO con questo JSON ESATTO:
{{
  "analisi_testuale": "L'Italia sta dominando con 70% possesso ma ha segnato solo 1 gol...",
  "probabilita_aggiornate": {{
    "1": 75,
    "X": 15, 
    "2": 10
  }},
  "pronostico_finale": "2-0",
  "confidence": 70,
  "fattori_chiave": [
    "Supremazia del possesso",
    "Più tiri in porta",
    "Trasferta in difficoltà"
  ],
  "consigli_live": [
    {{"tipo": "1", "descrizione": "Vittoria casa molto probabile"}},
    {{"tipo": "Under 3.5", "descrizione": "Partita controllata"}}
  ]
}}

Confidence 0-100. Probabilità devono sommare a 100. Analisi realistica basata sui dati."""

        response = self._call_gemini(prompt, temperature=0.7, max_tokens=2048)
        
        if not response:
            logger.error("Gemini non ha risposto per l'analisi live")
            return None
            
        data_parsed = self._parse_json_response(response)
        
        if data_parsed:
            logger.info(f"Analisi live Gemini completata per {squadra_casa} vs {squadra_trasferta}")
            return data_parsed
        else:
            logger.warning("Risposta Gemini live non parsabile")
            return None


# Istanza singleton
gemini_engine = None

def get_gemini_engine(api_keys=None):
    """Ritorna l'istanza singleton del motore Gemini."""
    global gemini_engine
    if gemini_engine is None:
        gemini_engine = GeminiEngine(api_keys=api_keys)
    return gemini_engine
