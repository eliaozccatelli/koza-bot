"""Test per verificare tutti gli interventi di miglioramento."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_parser():
    print("=" * 50)
    print("TEST 1: Parser messaggi")
    print("=" * 50)
    from src.utils.message_parser import parse_match_result, parse_all_matches_in_message, infer_competition

    # Test parsing base
    tests = [
        ("Inter-Juve 2-1", True),
        ("Brighton-Liverpool 2-1", True),
        ("Real Madrid vs Barcelona 3-1", True),
        ("PSG-Lyon 3-1", True),
    ]
    for text, should_parse in tests:
        r = parse_match_result(text)
        if r and should_parse:
            print(f"  OK: {text} -> {r['match_desc']} ({r['result']}) [{r['competition']}]")
        elif not r and not should_parse:
            print(f"  OK: {text} -> Scartato correttamente")
        else:
            print(f"  FAIL: {text} -> {'Trovato' if r else 'Non trovato'}")

    # Test competizione
    print("\n  --- Inferenza competizione ---")
    comp_tests = [
        ("Inter", "Milan", "Serie A"),
        ("Arsenal", "Liverpool", "Premier League"),
        ("Real Madrid", "Barcelona", "La Liga"),
        ("Dortmund", "Leverkusen", "Bundesliga"),
        ("PSG", "Monaco", "Ligue 1"),
    ]
    for h, a, expected in comp_tests:
        result = infer_competition(h, a)
        ok = "OK" if result == expected else "FAIL"
        print(f"  {ok}: {h} vs {a} -> {result} (atteso: {expected})")

    # Test multi-match
    print("\n  --- Multi-match ---")
    multi = "Inter-Napoli 2-1\nMilan-Torino 3-2\nJuventus-Roma 1-1"
    results = parse_all_matches_in_message(multi)
    print(f"  Trovate {len(results)} partite:")
    for r in results:
        print(f"    {r['match_desc']} -> {r['competition']}")


def test_csv_clean():
    print("\n" + "=" * 50)
    print("TEST 2: CSV pulito")
    print("=" * 50)
    import csv
    
    csv_file = "parsed_matches.csv"
    if not os.path.exists(csv_file):
        print("  SKIP: parsed_matches.csv non trovato")
        return
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    # Verifica header
    has_competition = 'Competition' in rows[0] if rows else False
    print(f"  Colonna Competition: {'OK' if has_competition else 'MANCANTE'}")
    print(f"  Righe totali: {len(rows)}")
    
    # Verifica no righe corrotte
    corrupt = 0
    for i, row in enumerate(rows):
        home = row.get('HomeTeam', '')
        away = row.get('AwayTeam', '')
        if '\n' in home or '\n' in away or 'giornata' in home.lower() or 'giornata' in away.lower():
            corrupt += 1
            print(f"  CORROTTA riga {i+2}: {home} vs {away}")
    
    if corrupt == 0:
        print("  OK: Nessuna riga corrotta")
    
    # Verifica duplicati
    seen = set()
    dupes = 0
    for row in rows:
        key = f"{row.get('Date', '')}_{row.get('HomeTeam', '')}_{row.get('AwayTeam', '')}_{row.get('FTHG', '')}_{row.get('FTAG', '')}"
        if key in seen:
            dupes += 1
            print(f"  DUPLICATO: {key}")
        seen.add(key)
    
    if dupes == 0:
        print("  OK: Nessun duplicato")


def test_training_data():
    print("\n" + "=" * 50)
    print("TEST 3: Forma da training data (serie_a_2026.csv)")
    print("=" * 50)
    from src.utils.team_form_bridge import get_form_from_training_data
    
    teams = ["Inter", "Milan", "Juventus", "Napoli", "Roma", "Lazio", "Fiorentina"]
    
    for team in teams:
        form = get_form_from_training_data(team)
        if form:
            print(f"  OK: {team:15s} -> {form['form']} ({form['wins']}V-{form['draws']}P-{form['losses']}S, {form['goals_for']}GF-{form['goals_against']}GS) [source: {form['source']}]")
        else:
            print(f"  FAIL: {team} -> Nessun dato")


def test_form_priority():
    print("\n" + "=" * 50)
    print("TEST 4: Priorita' fonti forma")
    print("=" * 50)
    from src.utils.team_form_bridge import get_team_form_with_details
    
    teams = ["Inter", "Milan", "Brighton", "PSG", "Dortmund", "Barcelona"]
    
    for team in teams:
        details = get_team_form_with_details(team)
        print(f"  {team:15s} -> {details['form']} [source: {details['source']}]")


if __name__ == "__main__":
    test_parser()
    test_csv_clean()
    test_training_data()
    test_form_priority()
    print("\n" + "=" * 50)
    print("TUTTI I TEST COMPLETATI")
    print("=" * 50)
