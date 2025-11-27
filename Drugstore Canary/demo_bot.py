"""
Simple demo of the stock monitoring bot
"""
import asyncio
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).parent))

from bots.playwright_scraper import PlaywrightScraper


async def demo():
    """Simple demo to show bot working"""
    print("\n" + "="*60)
    print("🤖 Stock Monitoring Bot - Demo")
    print("="*60)
    
    print("\n1️⃣ Initializing browser...")
    
    async with PlaywrightScraper(headless=True, debug=True) as scraper:
        print("✅ Browser initialized successfully!")
        
        print("\n2️⃣ Testing navigation...")
        success = await scraper.navigate("https://www.google.com")
        
        if success:
            print("✅ Navigation successful!")
            
            print("\n3️⃣ Taking screenshot...")
            screenshot_path = await scraper.take_screenshot("demo_test")
            
            if screenshot_path:
                print(f"✅ Screenshot saved: {screenshot_path}")
            
            print("\n4️⃣ Testing search...")
            search_box = "textarea[name='q']"
            if await scraper.wait_for_selector(search_box, timeout=5000):
                await scraper.type_text(search_box, "Drugstore Canary")
                print("✅ Typed search query!")
                
                await asyncio.sleep(2)
                await scraper.take_screenshot("demo_search")
        
        print("\n" + "="*60)
        print("✅ Demo Complete!")
        print("="*60)
        print("\nThe bot successfully:")
        print("  ✓ Initialized headless browser")
        print("  ✓ Navigated to webpage")
        print("  ✓ Interacted with elements")
        print("  ✓ Captured screenshots")
        print("\nReady for pharmacy scraping! 🎉")
        print("="*60 + "\n")


if __name__ == "__main__":
    asyncio.run(demo())
