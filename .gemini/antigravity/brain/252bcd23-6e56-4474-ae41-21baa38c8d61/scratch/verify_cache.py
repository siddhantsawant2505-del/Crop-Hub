import asyncio
import sys
import os
from pathlib import Path

# Add current dir to sys.path to allow relative imports if needed
# or just mock the environment
sys.path.append(str(Path("E:/Projects/CropHub/ml_service")))

from fathom_layer.market_service import MarketService

async def test_cache():
    print("Testing MarketService SQLite Cache...")
    
    state = "Maharashtra"
    district = "Pune"
    
    print(f"Fetching prices for {district}, {state} (First time - should hit API/Simulate)...")
    res1 = await MarketService.get_market_prices(state, district)
    print(f"Source 1: {res1['source']}")
    print(f"Location 1: {res1['location']}")
    
    print(f"\nFetching prices for {district}, {state} (Second time - should be CACHED)...")
    res2 = await MarketService.get_market_prices(state, district)
    print(f"Source 2: {res2['source']}")
    print(f"Location 2: {res2['location']}")
    
    if "Cached" in res2['source']:
        print("\nSUCCESS: SQLite Caching works!")
    else:
        print("\nFAILURE: SQLite Caching failed!")

if __name__ == "__main__":
    asyncio.run(test_cache())
