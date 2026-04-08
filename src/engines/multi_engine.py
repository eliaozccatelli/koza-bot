"""
Multi-Engine AI Orchestrator per KOZA Bot.
Prova i motori AI in ordine di priorita': Groq -> Gemini -> Default locale.
Se un engine fallisce, passa automaticamente al successivo.
"""

import os
import logging

from src.engines.base_engine import BaseAIEngine
from src.engines.groq_engine import GroqEngine
from src.engines.gemini_engine import GeminiEngine

logger = logging.getLogger(__name__)

# Mappa nomi engine -> nomi visualizzazione
ENGINE_DISPLAY_NAMES = {
    "groq": "Llama 3.3 70B (Groq)",
    "gemini": "Gemini AI",
    "default": "Analisi Locale",
}


class MultiEngine:
    """
    Orchestratore che prova i motori AI in ordine di priorita'.
    Groq (Llama 70B) -> Gemini (Flash) -> Default locale.
    """

    def __init__(self, groq_key=None, gemini_keys=None):
        self.engines = []
        self._fallback_engine = BaseAIEngine()

        # Gemini serve ANCHE come motore per get_competizioni, get_partite, etc.
        self._gemini = None
        gemini_key = gemini_keys or os.getenv("GEMINI_API_KEY", "")
        if gemini_key:
            self._gemini = GeminiEngine(api_keys=gemini_key)

        # 1. Groq (primario per analisi)
        groq_api_key = groq_key or os.getenv("GROQ_API_KEY", "")
        if groq_api_key:
            groq = GroqEngine(api_key=groq_api_key)
            if groq.is_available:
                self.engines.append(("groq", groq))
                logger.info("MultiEngine: Groq (Llama 3.3 70B) attivato come primario")

        # 2. Gemini (fallback per analisi)
        if self._gemini:
            self.engines.append(("gemini", self._gemini))
            logger.info("MultiEngine: Gemini attivato come fallback")

        if not self.engines:
            logger.warning("MultiEngine: nessun engine AI configurato, solo analisi locale")

        logger.info(f"MultiEngine inizializzato con {len(self.engines)} engine(s)")

    def get_engine_name(self, engine_id):
        """Ritorna il nome visualizzazione di un engine."""
        return ENGINE_DISPLAY_NAMES.get(engine_id, engine_id)

    # =========================
    # Metodi con Fallback
    # =========================

    def analizza_partita(self, squadra_casa, squadra_trasferta, **kwargs):
        """Prova ogni engine in ordine. Se uno fallisce, passa al successivo."""
        for name, engine in self.engines:
            try:
                result = engine.analizza_partita(squadra_casa, squadra_trasferta, **kwargs)
                if result and result.get("pronostico"):
                    result["_engine"] = name
                    logger.info(f"Analisi completata con engine: {name}")
                    return result
            except Exception as e:
                logger.warning(f"Engine {name} fallito: {e}")
                continue

        # Tutti gli engine hanno fallito -> analisi default locale
        logger.warning("Tutti gli engine falliti, uso analisi default")
        return self._fallback_engine._default_analysis(squadra_casa, squadra_trasferta)

    def analisi_live(self, squadra_casa, squadra_trasferta, risultato_live, tempo,
                     statistiche_live, prob_pre_partita=None):
        """Analisi live con fallback."""
        for name, engine in self.engines:
            try:
                if hasattr(engine, 'analisi_live'):
                    result = engine.analisi_live(
                        squadra_casa, squadra_trasferta,
                        risultato_live, tempo, statistiche_live, prob_pre_partita
                    )
                    if result:
                        result["_engine"] = name
                        return result
            except Exception as e:
                logger.warning(f"Engine {name} analisi_live fallito: {e}")
                continue
        return None

    def calcola_schedina(self, partite_list):
        """Calcolo schedina con fallback."""
        for name, engine in self.engines:
            try:
                if hasattr(engine, 'calcola_schedina'):
                    result = engine.calcola_schedina(partite_list)
                    if result:
                        result["_engine"] = name
                        return result
            except Exception as e:
                logger.warning(f"Engine {name} calcola_schedina fallito: {e}")
                continue
        return None

    # =========================
    # Metodi delegati a Gemini (non hanno fallback Groq)
    # =========================

    def get_competizioni(self):
        """Delega a Gemini (Groq non gestisce liste competizioni)."""
        if self._gemini:
            return self._gemini.get_competizioni()
        return []

    def get_partite_del_giorno(self, data=None):
        """Delega a Gemini."""
        if self._gemini:
            return self._gemini.get_partite_del_giorno(data)
        return {}

    def get_partite_campionato(self, comp_id, data=None):
        """Delega a Gemini."""
        if self._gemini:
            return self._gemini.get_partite_campionato(comp_id, data)
        return []

    def get_info_squadra(self, nome_squadra):
        """Delega a Gemini."""
        if self._gemini:
            return self._gemini.get_info_squadra(nome_squadra)
        return None


# Singleton
_multi_engine = None


def get_multi_engine(groq_key=None, gemini_keys=None):
    """Ritorna istanza singleton del MultiEngine."""
    global _multi_engine
    if _multi_engine is None:
        _multi_engine = MultiEngine(groq_key=groq_key, gemini_keys=gemini_keys)
    return _multi_engine
