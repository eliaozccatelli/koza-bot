"""
Test rapido per verificare l'integrazione Gemini API
"""
import os
os.environ["GEMINI_API_KEY"] = "AIzaSyB0AGuOdwTGLqlFUDhMoA8LN_03Lfx0Fiw"

from src.engines.gemini_engine import GeminiEngine

def test_gemini():
    print("🧪 Test Gemini API...")
    engine = GeminiEngine()
    
    # Test 1: Get partite del giorno
    print("\n1️⃣ Test: get_partite_del_giorno()")
    from datetime import datetime
    partite = engine.get_partite_del_giorno(datetime.now().date())
    print(f"   Trovate {len(partite.get('competizioni', []))} competizioni")
    for comp in partite.get('competizioni', [])[:3]:
        print(f"   - {comp['nome']}: {len(comp.get('partite', []))} partite")
    
    # Test 2: Analizza partita
    print("\n2️⃣ Test: analizza_partita()")
    analisi = engine.analizza_partita("Inter", "Milan", "Serie A")
    pronostico = analisi.get('pronostico', {})
    print(f"   Pronostico: {pronostico.get('risultato_esatto', 'N/A')}")
    print(f"   Confidence: {pronostico.get('confidence', 0)}%")
    print(f"   Favorito: {pronostico.get('vincitore', 'incerto')}")
    
    # Test 3: Schedina
    print("\n3️⃣ Test: calcola_schedina()")
    partite_test = [
        {"casa": "Inter", "trasferta": "Milan"},
        {"casa": "Juventus", "trasferta": "Napoli"},
        {"casa": "Roma", "trasferta": "Lazio"}
    ]
    schedina = engine.calcola_schedina(partite_test)
    print(f"   Generata schedina con {len(schedina.get('schedina', []))} partite")
    
    print("\n✅ Test completati!")

if __name__ == "__main__":
    test_gemini()
