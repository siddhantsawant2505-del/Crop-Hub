import time
import requests
import json

def test_apis():
    lat, lon = 19.076, 72.877 # Mumbai
    
    print("Testing Open-Meteo...")
    start = time.time()
    try:
        url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=temperature_2m,precipitation"
        res = requests.get(url, timeout=10)
        print(f"Open-Meteo took: {time.time() - start:.2f}s")
    except Exception as e:
        print(f"Open-Meteo failed: {e}")

    print("Testing SoilGrids...")
    start = time.time()
    try:
        url = "https://rest.isric.org/soilgrids/v2.0/properties/query"
        params = {
            'lon': lon, 'lat': lat,
            'property': ['clay', 'sand', 'silt', 'ph', 'nitrogen'],
            'depth': '0-5cm'
        }
        res = requests.get(url, params=params, timeout=10)
        print(f"SoilGrids took: {time.time() - start:.2f}s")
    except Exception as e:
        print(f"SoilGrids failed: {e}")

if __name__ == "__main__":
    test_apis()
