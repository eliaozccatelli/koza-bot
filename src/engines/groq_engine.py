"""
Groq Engine per KOZA Bot
Usa Groq Cloud (gratis) per eseguire Llama 3.3 70B.
API OpenAI-compatibile con JSON mode nativo.
"""

import os
import logging
import requests

from src.engines.base_engine import BaseAIEngine
from src.engines.koza_personality import (
    KOZA_SYSTEM_PROMPT,
    KOZA_MATCH_ANALYSIS_FORMAT,
    KOZA_LIVE_ANALYSIS_FORMAT,
    KOZA_SCHEDINA_FORMAT,
)

logger = logging.getLogger(__name__)


class GroqEngine(BaseAIEngine):
    """Engine AI basato su Groq Cloud (Llama 3.3 70B gratuito)."""

    def __init__(self, api_key=None, model=None):
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        self.model = model or os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
        self.base_url = "https://api.groq.com/openai/v1/chat/completions"
        self.session = requests.Session()

        if self.api_key:
            logger.info(f"GroqEngine inizializzato con modello: {self.model}")
        else:
            logger.warning("GroqEngine: API key mancante. Engine non attivo.")

    @property
    def is_available(self):
        return bool(self.api_key)

    def _call_groq(self, prompt, system_prompt=None, temperature=0.5, max_tokens=4096):
        """
        Chiama Groq API (formato OpenAI-compatibile).
        Supporta JSON mode nativo per risposte strutturate.
        """
        if not self.api_key:
            return None

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_object"},
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = self.session.post(
                self.base_url, json=payload, headers=headers, timeout=60
            )

            if response.status_code == 200:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                logger.info(f"Groq risposta OK ({self.model})")
                return content

            elif response.status_code == 429:
                logger.warning("Groq rate limit raggiunto")
                return None
            else:
                logger.error(f"Groq errore {response.status_code}: {response.text[:200]}")
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"Groq errore richiesta: {e}")
            return None

    # =========================
    # Metodi Pubblici - Analisi
    # =========================

    def analizza_partita(self, squadra_casa, squadra_trasferta, competizione=None, data=None,
                         forma_casa=None, forma_trasferta=None, h2h=None,
                         rating_casa=None, rating_trasferta=None, ml_prediction=None,
                         standings_casa=None, standings_trasferta=None):
        """Analizza una partita usando Groq/Llama."""
        data_str = ""
        if data:
            data_str = f" in programma il {data.strftime('%d/%m/%Y')}"

        comp_info = f" ({competizione})" if competizione else ""

        dati_reali = self._build_data_context(
            squadra_casa, squadra_trasferta,
            forma_casa, forma_trasferta, h2h,
            rating_casa, rating_trasferta,
            ml_prediction=ml_prediction,
            standings_casa=standings_casa, standings_trasferta=standings_trasferta
        )

        prompt = f"""Analizza la partita {squadra_casa} vs {squadra_trasferta}{comp_info}{data_str}.

{dati_reali}

{KOZA_MATCH_ANALYSIS_FORMAT}"""

        response = self._call_groq(prompt, system_prompt=KOZA_SYSTEM_PROMPT,
                                   temperature=0.5, max_tokens=4096)

        if not response:
            logger.warning("Groq non ha risposto, fallback a default")
            return None  # MultiEngine provera' il prossimo engine

        data_parsed = self._parse_json_response(response)

        if data_parsed:
            logger.info(f"Analisi Groq completata per {squadra_casa} vs {squadra_trasferta}")
            data_parsed = self._validate_gemini_response(data_parsed)

            scommesse = data_parsed.get("scommesse_consigliate", [])
            if not scommesse:
                risultato = data_parsed.get("pronostico", {}).get("risultato_esatto", "1-1")
                prob = data_parsed.get("probabilita", {})
                conf = data_parsed.get("pronostico", {}).get("confidence", 50)
                data_parsed["scommesse_consigliate"] = self._generate_smart_scommesse(
                    risultato, squadra_casa, squadra_trasferta,
                    probabilita=prob, confidence=conf
                )

            data_parsed["_engine"] = "groq"
            return data_parsed
        else:
            logger.warning("Risposta Groq non parsabile")
            return None

    def analisi_live(self, squadra_casa, squadra_trasferta, risultato_live, tempo,
                     statistiche_live, prob_pre_partita=None):
        """Analisi live di una partita in corso."""
        stats_text = ""
        if statistiche_live:
            stats_text = "\nSTATISTICHE LIVE:\n"
            for key, val in statistiche_live.items():
                stats_text += f"- {key}: {val}\n"

        prob_text = ""
        if prob_pre_partita:
            prob_text = f"\nProbabilita' pre-partita: 1={prob_pre_partita.get('1','')}% X={prob_pre_partita.get('X','')}% 2={prob_pre_partita.get('2','')}%"

        prompt = f"""Analizza la partita LIVE: {squadra_casa} {risultato_live} {squadra_trasferta}
Minuto: {tempo}'
{stats_text}{prob_text}

{KOZA_LIVE_ANALYSIS_FORMAT}"""

        response = self._call_groq(prompt, system_prompt=KOZA_SYSTEM_PROMPT,
                                   temperature=0.4, max_tokens=2048)

        if not response:
            return None

        data_parsed = self._parse_json_response(response)
        if data_parsed:
            data_parsed["_engine"] = "groq"
            return data_parsed
        return None

    def calcola_schedina(self, partite_list):
        """Calcola una schedina multipla."""
        partite_text = "\n".join([
            f"- {p.get('casa', '?')} vs {p.get('trasferta', '?')} ({p.get('competizione', '')})"
            for p in partite_list
        ])

        prompt = f"""Analizza queste partite per una schedina:
{partite_text}

Per ogni partita, suggerisci il pronostico piu' probabile.

{KOZA_SCHEDINA_FORMAT}"""

        response = self._call_groq(prompt, system_prompt=KOZA_SYSTEM_PROMPT,
                                   temperature=0.4, max_tokens=4096)

        if not response:
            return None

        data_parsed = self._parse_json_response(response)
        if data_parsed:
            data_parsed["_engine"] = "groq"
            return data_parsed
        return None


# Singleton
_groq_engine = None


def get_groq_engine(api_key=None):
    """Ritorna istanza singleton del motore Groq."""
    global _groq_engine
    if _groq_engine is None:
        _groq_engine = GroqEngine(api_key=api_key)
    return _groq_engine
