"""
Gemini AI Engine per KOZA Bot
Gestisce le chiamate all'API Google Gemini per analisi calcistica
"""

import os
import json
import logging
import requests
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = "gemini-2.0-flash"


class GeminiEngine:
    """Motore AI basato su Google Gemini per analisi calcistica."""
    
    def __init__(self, api_key=None, model=DEFAULT_MODEL):
        self.api_key = api_key or GEMINI_API_KEY
        self.model = model
        self.base_url = f"{GEMINI_BASE_URL}/{model}"
        self.session = requests.Session()
        
    def _call_gemini(self, prompt, temperature=0.7, max_tokens=2048):
        """Chiama l'API Gemini con il prompt fornito."""
        if not self.api_key:
            logger.error("API Key Gemini non configurata")
            return None
            
        url = f"{self.base_url}:generateContent?key={self.api_key}"
        
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
            
            if response.status_code != 200:
                logger.error(f"Errore Gemini API: {response.status_code} - {response.text[:200]}")
                return None
                
            data = response.json()
            
            if "candidates" in data and len(data["candidates"]) > 0:
                content = data["candidates"][0].get("content", {})
                parts = content.get("parts", [])
                if parts:
                    return parts[0].get("text", "").strip()
                    
            logger.warning("Risposta Gemini vuota o malformata")
            return None
            
        except Exception as e:
            logger.error(f"Errore chiamata Gemini: {e}")
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
    
    def analizza_partita(self, squadra_casa, squadra_trasferta, competizione=None, data=None):
        """
        Analizza una partita specifica usando Gemini AI.
        Ritorna un dict con pronostico e analisi completa.
        """
        data_str = ""
        if data:
            data_str = f" in programma il {data.strftime('%d/%m/%Y')}"
        
        comp_info = f" ({competizione})" if competizione else ""
        
        prompt = f"""Sei un esperto analista calcistico. Analizza la partita{squadra_casa} vs {squadra_trasferta}{comp_info}{data_str}.

Fornisci un pronostico dettagliato con questo formato JSON ESATTO:
{{
  "pronostico": {{
    "risultato_esatto": "2-1",
    "vincitore": "casa",
    "over_under": "Over 2.5",
    "gol_nogol": "Gol",
    "confidence": 75,
    "descrizione": "L'Inter ha un attacco in forma..."
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
    {{"tipo": "1", "quota": "1.75", "descrizione": "Vittoria casa"}},
    {{"tipo": "Over 2.5", "quota": "1.90", "descrizione": "Più di 2 gol"}},
    {{"tipo": "Gol", "quota": "1.80", "descrizione": "Entrambe segnano"}}
  ]
}}

Confidence deve essere 0-100.
Probabilità devono essere numeri interi 0-100.
Fornisci analisi realistica basata sulla forma attuale delle squadre.
Rispondi SOLO con il JSON valido, nessun testo aggiuntivo."""

        response = self._call_gemini(prompt, temperature=0.7, max_tokens=4096)
        
        if not response:
            logger.error("Gemini non ha risposto per l'analisi partita")
            return self._default_analysis(squadra_casa, squadra_trasferta)
            
        data_parsed = self._parse_json_response(response)
        
        if data_parsed:
            logger.info(f"Analisi Gemini completata per {squadra_casa} vs {squadra_trasferta}")
            return data_parsed
        else:
            logger.warning("Risposta Gemini non parsabile, uso default")
            return self._default_analysis(squadra_casa, squadra_trasferta)
    
    def _default_analysis(self, casa, trasferta):
        """
        Ritorna un'analisi di default se Gemini fallisce.
        Genera statistiche variabili basate sui nomi delle squadre.
        """
        # Genera valori pseudo-casuali ma deterministici basati sui nomi squadre
        casa_hash = sum(ord(c) for c in casa)
        trasf_hash = sum(ord(c) for c in trasferta)
        
        # Forza squadre (60-90)
        forza_casa = 60 + (casa_hash % 31)
        forza_trasf = 60 + (trasf_hash % 31)
        
        # Probabilità basate sulla forza
        prob_1 = min(70, max(20, forza_casa - forza_trasf + 50 + (casa_hash % 11) - 5))
        prob_2 = min(70, max(20, forza_trasf - forza_casa + 50 + (trasf_hash % 11) - 5))
        prob_x = 100 - prob_1 - prob_2
        
        # Normalizza
        if prob_x < 10:
            prob_1 = prob_1 - 5
            prob_2 = prob_2 - 5
            prob_x = 100 - prob_1 - prob_2
        
        # Risultato pronosticato
        if prob_1 > prob_2 and prob_1 > prob_x:
            risultato = f"{1 + (casa_hash % 3)}-{casa_hash % 2}"
            vincitore = "casa"
            consiglio = "1"
            desc_cons = f"Vittoria {casa} favorita"
        elif prob_2 > prob_1 and prob_2 > prob_x:
            risultato = f"{trasf_hash % 2}-{1 + (trasf_hash % 3)}"
            vincitore = "trasferta"
            consiglio = "2"
            desc_cons = f"Vittoria {trasferta} possibile"
        else:
            risultato = f"{1 + (casa_hash % 2)}-{1 + (trasf_hash % 2)}"
            vincitore = "pareggio"
            consiglio = "X"
            desc_cons = "Pareggio probabile"
        
        # Forme diverse
        forme = [
            "Ottima (4 vittorie nelle ultime 5)",
            "Buona (3 vittorie, 1 pareggio, 1 sconfitta)",
            "Discreta (2 vittorie, 2 pareggi, 1 sconfitta)",
            "Irregolare (2 vittorie, 1 pareggio, 2 sconfitte)",
            "In calo (1 vittoria, 1 pareggio, 3 sconfitte)"
        ]
        forma_casa = forme[casa_hash % len(forme)]
        forma_trasf = forme[trasf_hash % len(forme)]
        
        # Over/Under basato sulla forza offensiva
        over25 = min(80, max(30, (forza_casa + forza_trasf) // 2 + (casa_hash % 21) - 10))
        gol = min(75, max(35, over25 - 10 + (trasf_hash % 21) - 10))
        
        return {
            "pronostico": {
                "risultato_esatto": risultato,
                "vincitore": vincitore,
                "over_under": "Over 2.5" if over25 > 50 else "Under 2.5",
                "gol_nogol": "Gol" if gol > 50 else "No Gol",
                "confidence": min(90, max(40, abs(forza_casa - forza_trasf) + 40)),
                "descrizione": f"Analisi {casa} vs {trasferta}: {casa} ({forma_casa.lower()}), {trasferta} ({forma_trasferta.lower()}). {desc_cons.lower()}."
            },
            "probabilita": {
                "1": prob_1,
                "X": prob_x,
                "2": prob_2,
                "over25": over25,
                "over35": max(20, over25 - 20),
                "gol": gol,
                "cartellini_over45": 40 + ((casa_hash + trasf_hash) % 31)
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
            "scommesse_consigliate": [
                {"tipo": consiglio, "quota": f"{1.5 + (casa_hash % 30)/10:.2f}", "descrizione": desc_cons},
                {"tipo": "Gol" if gol > 50 else "No Gol", "quota": f"{1.7 + (trasf_hash % 25)/10:.2f}", "descrizione": "Entrambe le squadre segnano" if gol > 50 else "Almeno una non segna"},
                {"tipo": "Over 2.5" if over25 > 50 else "Under 2.5", "quota": f"{1.8 + (casa_hash % 20)/10:.2f}", "descrizione": "Più di 2 gol" if over25 > 50 else "Meno di 2 gol"}
            ]
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


# Istanza singleton
gemini_engine = None

def get_gemini_engine(api_key=None):
    """Ritorna l'istanza singleton del motore Gemini."""
    global gemini_engine
    if gemini_engine is None:
        gemini_engine = GeminiEngine(api_key=api_key)
    return gemini_engine
