"""
Base AI Engine - Classe base con metodi comuni a tutti gli engine AI.
GeminiEngine e GroqEngine ereditano da questa classe.
"""

import json
import re
import random
import logging
from datetime import date

from src.utils.team_ratings import get_team_rating, get_team_form

logger = logging.getLogger(__name__)


class BaseAIEngine:
    """Classe base per engine AI. Contiene metodi condivisi."""

    def _parse_json_response(self, text):
        """Estrae JSON dalla risposta testuale dell'AI."""
        if not text:
            return None

        # Pattern per JSON in ```json ... ```
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except Exception:
                pass

        # Prova a parsare tutto il testo come JSON
        try:
            return json.loads(text)
        except Exception:
            pass

        # Prova a trovare qualsiasi oggetto JSON
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except Exception:
                pass

        logger.warning(f"Impossibile parsare JSON da: {text[:200]}")
        return None

    def _build_data_context(self, casa, trasferta, forma_casa, forma_trasferta, h2h,
                            rating_casa, rating_trasferta, ml_prediction=None,
                            standings_casa=None, standings_trasferta=None):
        """Costruisce la sezione DATI REALI per il prompt AI."""
        lines = ["DATI REALI DISPONIBILI:"]

        # Classifica attuale (dato cruciale per l'analisi)
        if standings_casa or standings_trasferta:
            lines.append("")
            lines.append("CLASSIFICA ATTUALE:")
            if standings_casa:
                lines.append(f"- {casa}: {standings_casa['pos']}° posto, {standings_casa['pts']} punti ({standings_casa.get('played', '?')} partite giocate)")
            if standings_trasferta:
                lines.append(f"- {trasferta}: {standings_trasferta['pos']}° posto, {standings_trasferta['pts']} punti ({standings_trasferta.get('played', '?')} partite giocate)")
            lines.append("")

        # Forma casa
        if forma_casa:
            source = forma_casa.get('source', 'static')
            if source == 'telegram_live':
                tag = "dati LIVE stagione corrente"
            elif source in ('rapidapi', 'apifootball'):
                tag = "stagione 2024/25"
            else:
                tag = "approssimativo"
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
            # Dettaglio partite reali per narrativa accurata
            for m in forma_casa.get('matches', []):
                venue = "casa" if m.get('venue') == 'home' else "trasferta"
                lines.append(f"  - {m.get('date','?')}: {m['result']} {m.get('score','?')} vs {m.get('opponent','?')} ({venue})")

        # Forma trasferta
        if forma_trasferta:
            source = forma_trasferta.get('source', 'static')
            if source == 'telegram_live':
                tag = "dati LIVE stagione corrente"
            elif source in ('rapidapi', 'apifootball'):
                tag = "stagione 2024/25"
            else:
                tag = "approssimativo"
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
            # Dettaglio partite reali per narrativa accurata
            for m in forma_trasferta.get('matches', []):
                venue = "casa" if m.get('venue') == 'home' else "trasferta"
                lines.append(f"  - {m.get('date','?')}: {m['result']} {m.get('score','?')} vs {m.get('opponent','?')} ({venue})")

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
                t1_name = h2h.get('team1_name', casa)
                t2_name = h2h.get('team2_name', trasferta)
                lines.append(f"- Scontri diretti (ultimi {total}): {t1_name} {w1}V, {dr}P, {t2_name} {w2}V")
                matches = h2h.get('matches', [])
                for m in matches[:5]:
                    home_t = m.get('home_team', m.get('home', '?'))
                    away_t = m.get('away_team', m.get('away', '?'))
                    score = m.get('score', '?')
                    comp = m.get('competition', '')
                    date = m.get('date', '?')
                    comp_str = f" ({comp})" if comp else ""
                    lines.append(f"  - {date}: {home_t} {score} {away_t}{comp_str}")

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

    def _validate_gemini_response(self, data):
        """Valida e corregge incoerenze nella risposta AI."""
        try:
            pronostico = data.get("pronostico", {})
            prob = data.get("probabilita", {})
            vincitore = pronostico.get("vincitore", "")
            risultato = pronostico.get("risultato_esatto", "1-1")

            prob_1 = prob.get("1", 33)
            prob_x = prob.get("X", 33)
            prob_2 = prob.get("2", 33)

            # 1. X mai sotto 10%
            if prob_x < 10:
                deficit = 10 - prob_x
                prob_x = 10
                if prob_1 + prob_2 > 0:
                    ratio = prob_1 / (prob_1 + prob_2)
                    prob_1 -= deficit * ratio
                    prob_2 -= deficit * (1 - ratio)
                logger.info(f"Validazione: X corretto da {prob.get('X')}% a 10%")

            # 2. Probabilita' coerenti col vincitore
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
                    logger.info(f"Validazione: over25 corretto a {prob['over25']}%")
                elif totale_gol <= 2 and over25 > 55:
                    prob["over25"] = min(45, over25 - 15)
                    logger.info(f"Validazione: over25 corretto a {prob['over25']}%")
            except (ValueError, IndexError):
                pass

            # 4. Confidence coerente
            confidence = pronostico.get("confidence", 50)
            prob_vincitore = prob_1 if vincitore == "casa" else (prob_2 if vincitore == "trasferta" else prob_x)
            diff_12 = abs(prob_1 - prob_2)

            if prob_vincitore < 40 and confidence > 55:
                pronostico["confidence"] = min(confidence, 55)
            elif diff_12 < 10 and confidence > 50:
                pronostico["confidence"] = min(confidence, 50)

            data["pronostico"] = pronostico
            data["probabilita"] = prob

        except Exception as e:
            logger.warning(f"Errore validazione risposta: {e}")

        return data

    def _generate_smart_scommesse(self, risultato, casa, trasferta,
                                   probabilita=None, confidence=None):
        """Genera scommesse intelligenti basate su risultato, probabilita' e confidence."""
        try:
            gol_casa, gol_trasf = map(int, risultato.split('-'))
            totale_gol = gol_casa + gol_trasf

            prob_1 = probabilita.get("1", 33) if probabilita else 33
            prob_x = probabilita.get("X", 33) if probabilita else 33
            prob_2 = probabilita.get("2", 33) if probabilita else 33
            over25 = probabilita.get("over25", 50) if probabilita else 50
            prob_gol = probabilita.get("gol", 50) if probabilita else 50
            conf = confidence if confidence else 50

            safe = conf < 55

            scommesse = []

            # 1. Esito basato su probabilita'
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

            # 2. Over/Under basato su probabilita' over25
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
                if totale_gol <= 3:
                    scommesse.append({
                        "tipo": "Multigol 1-3", "probabilita": 60,
                        "descrizione": "Range gol piu' probabile"
                    })
                else:
                    scommesse.append({
                        "tipo": "Multigol 2-4", "probabilita": 55,
                        "descrizione": "Range gol piu' probabile"
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

            scommesse.sort(key=lambda x: x.get("probabilita", 0), reverse=True)
            return scommesse[:4]

        except (ValueError, IndexError):
            return [
                {"tipo": "1X2", "probabilita": 50, "descrizione": "Esito finale"},
                {"tipo": "Over/Under 2.5", "probabilita": 50, "descrizione": "Totale gol"}
            ]

    def _default_analysis(self, casa, trasferta):
        """Ritorna analisi di default basata sui rating statici."""
        forza_casa = get_team_rating(casa)
        forza_trasf = get_team_rating(trasferta)

        random.seed(date.today().toordinal())
        forza_casa += random.randint(-5, 5)
        forza_trasf += random.randint(-5, 5)

        diff = forza_casa - forza_trasf
        prob_1 = min(75, max(25, 50 + diff * 0.8 + random.randint(-3, 3)))
        prob_2 = min(75, max(25, 50 - diff * 0.8 + random.randint(-3, 3)))
        prob_x = 100 - prob_1 - prob_2

        if prob_x < 10:
            prob_1 = max(25, prob_1 - 5)
            prob_2 = max(25, prob_2 - 5)
            prob_x = 100 - prob_1 - prob_2

        if prob_1 > prob_2 and prob_1 > prob_x:
            gol_casa = 1 + (forza_casa // 30) + random.randint(0, 1)
            gol_trasf = random.randint(0, forza_trasf // 40)
            risultato = f"{gol_casa}-{gol_trasf}"
            vincitore = "casa"
            desc_cons = f"Vittoria {casa} favorita"
        elif prob_2 > prob_1 and prob_2 > prob_x:
            gol_casa = random.randint(0, forza_casa // 40)
            gol_trasf = 1 + (forza_trasf // 30) + random.randint(0, 1)
            risultato = f"{gol_casa}-{gol_trasf}"
            vincitore = "trasferta"
            desc_cons = f"Vittoria {trasferta} possibile"
        else:
            gol_casa = 1 + (forza_casa // 35)
            gol_trasf = 1 + (forza_trasf // 35)
            risultato = f"{gol_casa}-{gol_trasf}"
            vincitore = "pareggio"
            desc_cons = "Pareggio probabile"

        forma_casa_str = get_team_form(casa)
        forma_trasf_str = get_team_form(trasferta)

        media_forza = (forza_casa + forza_trasf) / 2
        over25 = min(80, max(30, int(media_forza * 0.6) + random.randint(-5, 5)))
        gol = min(75, max(35, over25 - 10 + random.randint(-5, 5)))
        confidence = min(90, max(45, 50 + abs(diff) // 2))

        probabilita = {
            "1": prob_1, "X": prob_x, "2": prob_2,
            "over25": over25, "over35": max(20, over25 - 20),
            "gol": gol, "cartellini_over45": 40 + random.randint(0, 20)
        }

        return {
            "pronostico": {
                "risultato_esatto": risultato,
                "vincitore": vincitore,
                "over_under": "Over 2.5" if over25 > 50 else "Under 2.5",
                "gol_nogol": "Gol" if gol > 50 else "No Gol",
                "confidence": confidence,
                "descrizione": f"{desc_cons}. {casa} (forza: {forza_casa}/100), {trasferta} (forza: {forza_trasf}/100)."
            },
            "probabilita": probabilita,
            "analisi": {
                "forza_casa": forza_casa,
                "forza_trasferta": forza_trasf,
                "forma_casa": forma_casa_str,
                "forma_trasferta": forma_trasf_str,
                "assenti_casa": [],
                "assenti_trasferta": [],
                "ultimi_scontri": []
            },
            "scommesse_consigliate": self._generate_smart_scommesse(
                risultato, casa, trasferta,
                probabilita=probabilita, confidence=confidence
            ),
            "_engine": "default"
        }
