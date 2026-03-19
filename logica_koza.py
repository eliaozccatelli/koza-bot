import math
import requests
import logging
from rapidfuzz import process, utils
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

# Carica .env
load_dotenv()

from config import (
    API_KEY, API_HOST, SEASON,
    FUZZY_MATCH_THRESHOLD, API_TIMEOUT, MAX_GOALS,
    MOSTRA_TOP_SCOMMESSE, MOSTRA_HEAD_TO_HEAD, LOG_LEVEL
)

logging.basicConfig(level=LOG_LEVEL)
logger = logging.getLogger(__name__)


class KozaEngine:
    """Motore di predizione KOZA con football-data.org API - Squadre da TUTTE le leghe"""
    
    def __init__(self):
        self.headers = {'X-Auth-Token': API_KEY}
        self.teams_cache = {}  # {nome_squadra: team_id}
        self.teams_stats = {}  # {team_id: stats}
        self.competitions = {}  # {comp_id: comp_name}
        self.team_competitions = {}  # {team_id: comp_id}
    
    def carica_database_squadre(self):
        """Carica squadre da TUTTE le competizioni disponibili"""
        url = f"https://{API_HOST}/v4/competitions"
        try:
            logger.info(f"Lettura competizioni...")
            response = requests.get(url, headers=self.headers, timeout=API_TIMEOUT)
            
            if response.status_code != 200:
                logger.error(f"Errore: {response.status_code}")
                return False
            
            response_data = response.json()
            competitions = response_data.get('competitions', [])
            
            if not competitions:
                logger.error(f"Nessuna competizione trovata")
                return False
            
            total_teams = 0
            for comp in competitions:
                comp_id = comp['id']
                comp_name = comp['name']
                self.competitions[comp_id] = comp_name
                
                team_count = self._carica_squadre_per_lega(comp_id, comp_name)
                total_teams += team_count
            
            logger.info(f"Caricate {total_teams} squadre da {len(self.competitions)} competizioni")
            return total_teams > 0
            
        except Exception as e:
            logger.error(f"Errore: {e}")
        return False
    
    def _carica_squadre_per_lega(self, league_id, league_name):
        """Carica squadre da una singola competizione"""
        url = f"https://{API_HOST}/v4/competitions/{league_id}/teams"
        try:
            response = requests.get(url, headers=self.headers, timeout=API_TIMEOUT)
            if response.status_code != 200:
                return 0
            
            response_data = response.json()
            team_count = 0
            
            if response_data.get('teams'):
                for team in response_data['teams']:
                    team_id = team['id']
                    team_name = team['name']
                    self.teams_cache[team_name] = team_id
                    self.team_competitions[team_id] = league_id
                    team_count += 1
            
            return team_count
        except Exception as e:
            logger.error(f"❌ Errore in {league_name}: {e}")
        return 0

    def trova_squadra(self, query):
        """Fuzzy matching - trova squadra da TUTTE le leghe"""
        if not query or not self.teams_cache:
            logger.warning(f"⚠️ Query vuota o cache vuota: query='{query}', cache_size={len(self.teams_cache)}")
            return None, None, None
        
        nomi = list(self.teams_cache.keys())
        match = process.extractOne(query, nomi, processor=utils.default_process)
        
        logger.info(f"🔍 Fuzzy match per '{query}': trovato '{match[0]}' con score {match[1]:.0f}%")
        
        if match and match[1] >= FUZZY_MATCH_THRESHOLD:
            nome_vero = match[0]
            team_id = self.teams_cache[nome_vero]
            comp_id = self.team_competitions.get(team_id)
            comp_name = self.competitions.get(comp_id, "Unknown")
            logger.info(f"✅ Squadra trovata: {nome_vero} (ID: {team_id}, Lega: {comp_name})")
            return team_id, nome_vero, comp_name
        
        logger.warning(f"❌ Nessun match trovato per '{query}' (miglior score: {match[1]:.0f}% < {FUZZY_MATCH_THRESHOLD}%)")
        return None, None, None

    def get_stats(self, team_id, comp_id):
        """Recupera statistiche della squadra da TUTTE le partite della stagione (FINISHED + LIVE)"""
        url = f"https://{API_HOST}/v4/teams/{team_id}/matches"
        # football-data.org si aspetta una stringa CSV per più stati,
        # non una lista Python, altrimenti può ignorare il filtro e
        # restituire 0 partite (poi si ricade sempre sulle stats di default)
        params = {'status': 'FINISHED,LIVE'}  # Includi LIVE matches per statistiche accurate
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=API_TIMEOUT)
            if response.status_code != 200:
                logger.warning(f"get_stats: risposta non OK ({response.status_code}) per team_id={team_id}")
                return self._default_stats()
            
            data = response.json()
            matches = data.get('matches', [])
            
            if not matches:
                logger.warning(f"get_stats: nessuna partita trovata per team_id={team_id}")
                return self._default_stats()
            
            # Calcola statistiche da TUTTE le partite della stagione
            gol_fatti = 0
            gol_subiti = 0
            partite = 0
            gialli = 0
            rossi = 0
            
            for match in matches:
                if match['status'] != 'FINISHED':
                    continue
                
                partite += 1
                home_id = match['homeTeam']['id']
                
                if home_id == team_id:
                    gol_fatti += match['score'].get('fullTime', {}).get('home', 0) or 0
                    gol_subiti += match['score'].get('fullTime', {}).get('away', 0) or 0
                else:
                    gol_fatti += match['score'].get('fullTime', {}).get('away', 0) or 0
                    gol_subiti += match['score'].get('fullTime', {}).get('home', 0) or 0
            
            if partite == 0:
                return self._default_stats()
            
            stats = {
                'media_segni': gol_fatti / partite,
                'media_subiti': gol_subiti / partite,
                'partite': partite,
                'gialli': max(1, int(partite * 0.6)),
                'rossi': max(0, int(partite * 0.05)),
                'tiri_in_porta': gol_fatti * 0.7,
                'possesso': 45 + (gol_fatti - gol_subiti) * 2
            }
            
            logger.info(f"✅ Statistiche squadra ID {team_id}: {partite} partite, {gol_fatti} gol fatti, {gol_subiti} subiti")
            return stats
            
        except Exception as e:
            logger.error(f"❌ Errore recupero stats: {e}")
        
        return self._default_stats()
    
    def _default_stats(self):
        """Statistiche di default quando non riesce a caricarle"""
        return {
            'media_segni': 1.5,
            'media_subiti': 1.2,
            'partite': 1,
            'gialli': 2.0,
            'rossi': 0.1,
            'tiri_in_porta': 1.0,
            'possesso': 47
        }

    def get_h2h_stats(self, team_id_1, team_id_2, comp_id):
        """Statistiche head-to-head (scontri diretti)"""
        url = f"https://{API_HOST}/v4/teams/{team_id_1}/matches"
        params = {'status': 'FINISHED'}
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=API_TIMEOUT)
            if response.status_code != 200:
                return {
                    'vittorie_1': 0, 'pareggi': 0, 'vittorie_2': 0, 'scontri': 0,
                    'matches': []
                }
            
            data = response.json()
            matches = data.get('matches', [])
            
            vittorie_1, pareggi, vittorie_2 = 0, 0, 0
            scontri = 0
            match_details = []
            
            for match in matches:
                if match['status'] != 'FINISHED':
                    continue
                
                home_id = match['homeTeam']['id']
                away_id = match['awayTeam']['id']
                home_name = match['homeTeam'].get('name', 'Unknown')
                away_name = match['awayTeam'].get('name', 'Unknown')
                
                if not ((home_id == team_id_1 and away_id == team_id_2) or 
                        (home_id == team_id_2 and away_id == team_id_1)):
                    continue
                
                scontri += 1
                
                goals_home = match['score'].get('fullTime', {}).get('home', 0) or 0
                goals_away = match['score'].get('fullTime', {}).get('away', 0) or 0
                match_date = match.get('utcDate', '')
                
                try:
                    parsed_date = datetime.fromisoformat(match_date.replace('Z', '+00:00'))
                    formatted_date = parsed_date.strftime('%d/%m/%Y')
                except:
                    formatted_date = match_date[:10] if match_date else 'N/A'
                
                match_details.append({
                    'date': formatted_date,
                    'home': home_name,
                    'away': away_name,
                    'result': f"{goals_home}-{goals_away}"
                })
                
                if home_id == team_id_1:
                    if goals_home > goals_away:
                        vittorie_1 += 1
                    elif goals_home == goals_away:
                        pareggi += 1
                    else:
                        vittorie_2 += 1
                else:
                    if goals_away > goals_home:
                        vittorie_1 += 1
                    elif goals_away == goals_home:
                        pareggi += 1
                    else:
                        vittorie_2 += 1
            
            logger.info(f"✅ Scontri diretti trovati: {scontri}")
            return {
                'vittorie_1': vittorie_1,
                'pareggi': pareggi,
                'vittorie_2': vittorie_2,
                'scontri': scontri,
                'matches': match_details
            }
        except Exception as e:
            logger.error(f"❌ Errore H2H: {e}")
        
        return {
            'vittorie_1': 0, 'pareggi': 0, 'vittorie_2': 0, 'scontri': 0,
            'matches': []
        }

    def trova_prossima_partita(self, team_id_1, team_id_2, data_partita=None):
        """Trova la prossima partita tra due squadre"""
        url = f"https://{API_HOST}/v4/teams/{team_id_1}/matches"
        params = {}
        
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=API_TIMEOUT)
            if response.status_code != 200:
                return {'found': False, 'date': None, 'status': 'unknown'}
            
            data = response.json()
            matches = data.get('matches', [])
            
            partite_trovate = []
            for match in matches:
                home_id = match['homeTeam']['id']
                away_id = match['awayTeam']['id']
                
                if not ((home_id == team_id_1 and away_id == team_id_2) or 
                        (home_id == team_id_2 and away_id == team_id_1)):
                    continue
                
                match_date = match.get('utcDate', '')
                match_status = match.get('status', 'UNKNOWN')
                
                partite_trovate.append({
                    'date': match_date,
                    'status': match_status,
                    'goals_home': match['score'].get('fullTime', {}).get('home', 0),
                    'goals_away': match['score'].get('fullTime', {}).get('away', 0),
                    'timestamp': datetime.fromisoformat(match_date.replace('Z', '+00:00')) if match_date else None
                })
            
            if data_partita:
                for p in partite_trovate:
                    if p['timestamp'] and p['timestamp'].date() == data_partita.date():
                        return {'found': True, 'data': p}
                return {'found': False, 'data': None}
            
            partite_trovate.sort(key=lambda x: x['timestamp'] if x['timestamp'] else datetime.min)
            
            if partite_trovate:
                now = datetime.now(timezone.utc)
                for p in partite_trovate:
                    if p['timestamp'] and p['timestamp'] > now and p['status'] == 'TIMED':
                        return {'found': True, 'data': p}
                
                return {'found': True, 'data': partite_trovate[-1]}
            
            return {'found': False, 'data': None}
            
        except Exception as e:
            logger.error(f"❌ Errore ricerca partita: {e}")
            return {'found': False, 'data': None}

    @staticmethod
    def poisson(lmbda, k):
        """Distribuzione di Poisson per calcolo probabilità"""
        if lmbda <= 0 or k < 0:
            return 0
        try:
            return (math.exp(-lmbda) * (lmbda ** k)) / math.factorial(k)
        except:
            return 0

    def calcola_pronostico(self, id_casa, nome_casa, id_trasf, nome_trasf, comp_id):
        """Calcola tutti i pronostici della partita"""
        
        s_c = self.get_stats(id_casa, comp_id)
        s_t = self.get_stats(id_trasf, comp_id)
        h2h = self.get_h2h_stats(id_casa, id_trasf, comp_id)
        
        xg_c = max(0.5, (s_c['media_segni'] + s_t['media_subiti']) / 2)
        xg_t = max(0.5, (s_t['media_segni'] + s_c['media_subiti']) / 2)
        
        matrice = {}
        p1, px, p2, over25, over35, btts = 0, 0, 0, 0, 0, 0

        for i in range(MAX_GOALS):
            for j in range(MAX_GOALS):
                p = self.poisson(xg_c, i) * self.poisson(xg_t, j)
                matrice[(i, j)] = p

                if i > j:
                    p1 += p
                elif i == j:
                    px += p
                else:
                    p2 += p

                if i + j >= 3:
                    over25 += p
                if i + j >= 4:
                    over35 += p
                if i > 0 and j > 0:
                    btts += p

        risultati_esatti = sorted(matrice.items(), key=lambda x: x[1], reverse=True)[:3]

        cart_media = (s_c['gialli'] + s_t['gialli']) / 2
        cart_over4 = min(max(cart_media / 5, 0.3), 0.95)

        verdetto = self._genera_verdetto(p1, px, p2, over25, btts, cart_over4)

        return {
            'nome_casa': nome_casa,
            'nome_trasf': nome_trasf,
            'xg_casa': xg_c,
            'xg_trasf': xg_t,
            'p1': max(p1, 0.01),
            'px': max(px, 0.01),
            'p2': max(p2, 0.01),
            'over25': max(over25, 0.01),
            'over35': max(over35, 0.01),
            'btts': max(btts, 0.01),
            'cart_media': cart_media,
            'cart_over4': max(cart_over4, 0.01),
            'risultati_esatti': risultati_esatti,
            'verdetto': verdetto,
            'h2h': h2h,
            'stats_casa': s_c,
            'stats_trasf': s_t
        }

    def _genera_verdetto(self, p1, px, p2, over25, btts, cart_over4):
        """Genera il verdetto consigliato"""
        parti = []

        if p1 > px and p1 > p2:
            if p1 > 0.55:
                parti.append("1")
            elif p1 > 0.40:
                parti.append("1X")
        elif p2 > px and p2 > p1:
            if p2 > 0.55:
                parti.append("2")
            elif p2 > 0.40:
                parti.append("X2")
        else:
            parti.append("X")

        if over25 > 0.55:
            parti.append("Over 2.5")
        elif over25 < 0.40:
            parti.append("Under 2.5")

        if btts > 0.55:
            parti.append("Gol")
        elif btts < 0.35:
            parti.append("No Gol")

        if cart_over4 > 0.60:
            parti.append("Over 4.5 Cart.")

        return " + ".join(parti) if parti else "Partita equilibrata"

    def formatta_output(self, pronostico):
        """Formatta il pronostico in messaggio"""
        
        scommesse = [
            ('1️⃣ Vittoria Casa', pronostico['p1'] * 100),
            ('❌ Pareggio', pronostico['px'] * 100),
            ('2️⃣ Vittoria Trasferta', pronostico['p2'] * 100),
            ('🔥 Over 2.5', pronostico['over25'] * 100),
            ('🔴 Over 3.5', pronostico['over35'] * 100),
            ('🥅 BTTS', pronostico['btts'] * 100),
            ('🟨 Over 4.5 Cartellini', pronostico['cart_over4'] * 100),
        ]

        scommesse.sort(key=lambda x: x[1], reverse=True)

        messaggio = (
            f"📊 **ANALISI KOZA**\n"
            f"{'='*40}\n\n"
            f"🏟 **{pronostico['nome_casa'].upper()}** vs **{pronostico['nome_trasf'].upper()}**\n\n"
            f"💡 **VERDETTO**: `{pronostico['verdetto']}`\n\n"
            f"⚽ **xG**: `{pronostico['xg_casa']:.2f}` - `{pronostico['xg_trasf']:.2f}`\n"
            f"📈 **Media Cartellini**: `{pronostico['cart_media']:.1f}`\n\n"
            f"🎯 **RISULTATI ESATTI**:\n"
        )

        for (g_casa, g_trasf), prob in pronostico['risultati_esatti']:
            if prob > 0:
                messaggio += f"   {g_casa}-{g_trasf}: **{prob * 100:.1f}%**\n"

        messaggio += f"\n{'='*40}\n📋 **PRONOSTICI**:\n\n"

        for i, (nome, prob) in enumerate(scommesse[:MOSTRA_TOP_SCOMMESSE], 1):
            messaggio += f"{i}. {nome}: **{prob:.1f}%**\n"

        if MOSTRA_HEAD_TO_HEAD and pronostico['h2h']['scontri'] > 0:
            messaggio += (
                f"\n⚔️ **Ultimi Scontri Diretti** ({pronostico['h2h']['scontri']} incontri):\n"
                f"   {pronostico['nome_casa']}: {pronostico['h2h']['vittorie_1']} V | "
                f"Pareggi: {pronostico['h2h']['pareggi']} | "
                f"{pronostico['nome_trasf']}: {pronostico['h2h']['vittorie_2']} V\n"
            )
            
            if pronostico['h2h'].get('matches'):
                messaggio += "\n   📝 Ultimi Risultati:\n"
                for match in pronostico['h2h']['matches'][-5:]:
                    messaggio += f"      • {match['home']} **{match['result']}** {match['away']} ({match['date']})\n"

        return messaggio

    def calcola_schedina(self, pronostici_list):
        """Calcola combinazioni di schedule"""
        if not pronostici_list or len(pronostici_list) < 2:
            return None
        
        num_partite = len(pronostici_list)
        combos = []
        
        # COMBO 1: Tutte vittorie casa
        prob_combo_1 = 1.0
        quota_combo_1 = 1.0
        for p in pronostici_list:
            prob_combo_1 *= p['p1']
            quota_combo_1 *= (1 / p['p1']) if p['p1'] > 0 else 1
        combos.append({
            'nome': 'Tutte Vittorie Casa (1X1X...)',
            'scommesse': ['1'] * num_partite,
            'probabilita': prob_combo_1,
            'quota': quota_combo_1,
            'descrizione': ' | '.join([f"{p['nome_casa']}" for p in pronostici_list])
        })
        
        # COMBO 2: Tutte vittorie trasferta
        prob_combo_2 = 1.0
        quota_combo_2 = 1.0
        for p in pronostici_list:
            prob_combo_2 *= p['p2']
            quota_combo_2 *= (1 / p['p2']) if p['p2'] > 0 else 1
        combos.append({
            'nome': 'Tutte Vittorie Trasferta (2X2X...)',
            'scommesse': ['2'] * num_partite,
            'probabilita': prob_combo_2,
            'quota': quota_combo_2,
            'descrizione': ' | '.join([f"{p['nome_trasf']}" for p in pronostici_list])
        })
        
        # COMBO 3: Tutte Pareggi
        prob_combo_x = 1.0
        quota_combo_x = 1.0
        for p in pronostici_list:
            prob_combo_x *= p['px']
            quota_combo_x *= (1 / p['px']) if p['px'] > 0 else 1
        combos.append({
            'nome': 'Tutti Pareggi (XxXxX...)',
            'scommesse': ['X'] * num_partite,
            'probabilita': prob_combo_x,
            'quota': quota_combo_x,
            'descrizione': 'Tutte le partite finiscono in pareggio'
        })
        
        # COMBO 4: Over 2.5 su tutte
        prob_over = 1.0
        quota_over = 1.0
        for p in pronostici_list:
            prob_over *= p['over25']
            quota_over *= (1 / p['over25']) if p['over25'] > 0 else 1
        combos.append({
            'nome': 'Over 2.5 su Tutte',
            'scommesse': ['Over 2.5'] * num_partite,
            'probabilita': prob_over,
            'quota': quota_over,
            'descrizione': '2+ gol in ogni partita'
        })
        
        # COMBO 5: BTTS su tutte
        prob_btts = 1.0
        quota_btts = 1.0
        for p in pronostici_list:
            prob_btts *= p['btts']
            quota_btts *= (1 / p['btts']) if p['btts'] > 0 else 1
        combos.append({
            'nome': 'BTTS su Tutte (Gol)',
            'scommesse': ['Gol'] * num_partite,
            'probabilita': prob_btts,
            'quota': quota_btts,
            'descrizione': 'Entrambe le squadre segnano in ogni match'
        })
        
        # COMBO 6: Intelligente
        prob_smart = 1.0
        quota_smart = 1.0
        scommesse_smart = []
        descrizione_smart = []
        
        for p in pronostici_list:
            esiti = [
                ('1', p['p1']),
                ('X', p['px']),
                ('2', p['p2']),
                ('Over 2.5', p['over25']),
            ]
            esiti.sort(key=lambda x: x[1], reverse=True)
            miglior_esito, miglior_prob = esiti[0]
            scommesse_smart.append(miglior_esito)
            prob_smart *= miglior_prob
            quota_smart *= (1 / miglior_prob) if miglior_prob > 0 else 1
            descrizione_smart.append(f"{p['nome_casa']} vs {p['nome_trasf']}: {miglior_esito}")
        
        combos.append({
            'nome': 'COMBO INTELLIGENTE (Miglior Combo)',
            'scommesse': scommesse_smart,
            'probabilita': prob_smart,
            'quota': quota_smart,
            'descrizione': ' | '.join(scommesse_smart)
        })
        
        combos.sort(key=lambda x: x['probabilita'], reverse=True)
        
        return {
            'num_partite': num_partite,
            'partite': [f"{p['nome_casa']} vs {p['nome_trasf']}" for p in pronostici_list],
            'combos': combos,
            'miglior_combo': combos[0] if combos else None
        }

    def get_competizioni_con_partite(self):
        """Ritorna lista di competizioni che hanno partite oggi"""
        competizioni_con_partite = []
        
        try:
            # Non limitiamo più a 15 competizioni, così Europa League,
            # Conference, ecc. non vengono escluse in base all'ordine
            for comp_id, comp_name in list(self.competitions.items()):
                url = f"https://{API_HOST}/v4/competitions/{comp_id}/matches"
                # Alcune partite risultano come TIMED invece che SCHEDULED,
                # quindi chiediamo entrambe per non perderle
                params = {'status': 'SCHEDULED,TIMED'}
                
                try:
                    response = requests.get(url, headers=self.headers, params=params, timeout=API_TIMEOUT)
                    if response.status_code != 200:
                        continue
                    
                    data = response.json()
                    matches = data.get('matches', [])
                    
                    # Filtra solo partite di oggi
                    today = datetime.now().date()
                    partite_oggi = []
                    
                    for match in matches:
                        match_date_str = match.get('utcDate', '')
                        try:
                            parsed_date = datetime.fromisoformat(match_date_str.replace('Z', '+00:00'))
                            if parsed_date.date() == today:
                                partite_oggi.append(match)
                        except:
                            pass
                    
                    if partite_oggi:
                        competizioni_con_partite.append((comp_id, comp_name))
                
                except Exception as e:
                    logger.warning(f"Errore competizione {comp_id}: {e}")
                    continue
        
        except Exception as e:
            logger.error(f"Errore get_competizioni_con_partite: {e}")
        
        return competizioni_con_partite
    
    def get_partite_campionato(self, comp_id):
        """Ritorna lista di partite di un campionato (oggi)"""
        partite = []
        
        try:
            url = f"https://{API_HOST}/v4/competitions/{comp_id}/matches"
            # Come sopra: includiamo sia SCHEDULED che TIMED
            params = {'status': 'SCHEDULED,TIMED'}
            
            response = requests.get(url, headers=self.headers, params=params, timeout=API_TIMEOUT)
            if response.status_code != 200:
                return []
            
            data = response.json()
            matches = data.get('matches', [])
            
            # Filtra solo partite di oggi
            today = datetime.now().date()
            
            for match in matches:
                match_date_str = match.get('utcDate', '')
                match_id = match.get('id')
                
                try:
                    parsed_date = datetime.fromisoformat(match_date_str.replace('Z', '+00:00'))
                    if parsed_date.date() == today:
                        home_team = match['homeTeam'].get('name', 'Unknown')
                        away_team = match['awayTeam'].get('name', 'Unknown')
                        partite.append((home_team, away_team, match_id))
                except Exception as e:
                    logger.warning(f"Errore parsing partita {match_id}: {e}")
            
            return partite
        
        except Exception as e:
            logger.error(f"Errore get_partite_campionato: {e}")
            return []

    def formatta_schedina(self, schedina_data, importo_scommessa=100):
        """Formatta la schedina per Telegram"""
        if not schedina_data:
            return "❌ Nessuna schedina disponibile"
        
        messaggio = (
            f"📋 **ANALISI SCHEDINA**\n"
            f"{'='*50}\n\n"
            f"🎯 **Partite**: {schedina_data['num_partite']}\n"
        )
        
        for i, partita in enumerate(schedina_data['partite'], 1):
            messaggio += f"   {i}. {partita}\n"
        
        messaggio += f"\n{'='*50}\n\n"
        messaggio += f"💰 **IMPORTO SCOMMESSA**: €{importo_scommessa:.2f}\n\n"
        
        best = schedina_data['miglior_combo']
        if best:
            payout = importo_scommessa * best['quota']
            messaggio += (
                f"🏆 **COMBO CONSIGLIATA**:\n"
                f"{best['nome']}\n\n"
                f"   Scommesse: {' | '.join(best['scommesse'])}\n"
                f"   Probabilità: **{best['probabilita']*100:.1f}%**\n"
                f"   Quota: **{best['quota']:.2f}x**\n"
                f"   Payout potenziale: **€{payout:.2f}**\n"
            )
        
        messaggio += f"\n{'='*50}\n\n📊 **ALTRE COMBO**:\n\n"
        
        for i, combo in enumerate(schedina_data['combos'][1:6], 1):
            payout = importo_scommessa * combo['quota']
            messaggio += (
                f"{i}. {combo['nome']}\n"
                f"   Probabilità: {combo['probabilita']*100:.1f}% | "
                f"Quota: {combo['quota']:.2f}x | Payout: €{payout:.2f}\n"
            )
        
        return messaggio
