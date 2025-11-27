"""
Lineman pharmacy scraper
Monitors medicine availability on LINE MAN delivery app
"""
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict
import sys

sys.path.append(str(Path(__file__).parent.parent))

from bots.playwright_scraper import PlaywrightScraper


class LinemanScraper(PlaywrightScraper):
    """Scraper for LINE MAN pharmacy section"""
    
    def __init__(self, headless: bool = True, debug: bool = False):
        super().__init__(headless, debug)
        self.base_url = "https://shop.lineman.in.th"
        self.results = []
    
    async def navigate_to_pharmacy(self, location: str = "Hat Yai") -> bool:
        """Navigate to pharmacy section"""
        try:
            if self.debug:
                print(f"\n🔍 Navigating to LINE MAN pharmacy...")
            
            await self.navigate(self.base_url)
            await asyncio.sleep(3)
            
            # Look for pharmacy/health category
            pharmacy_selectors = [
                "a[href*='pharmacy']",
                "a[href*='health']",
                "button:has-text('ร้านขายยา')",
                "div:has-text('ร้านขายยา')"
            ]
            
            for selector in pharmacy_selectors:
                if await self.wait_for_selector(selector, timeout=3000):
                    await self.click(selector)
                    await asyncio.sleep(2)
                    break
            
            await self.take_screenshot(f"lineman_pharmacy_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            return True
            
        except Exception as e:
            if self.debug:
                print(f"❌ Navigation error: {e}")
            return False
    
    async def search_items(self, keywords: List[str]) -> List[Dict]:
        """Search for items and check availability"""
        items_found = []
        
        try:
            # Look for search box
            search_selector = "input[placeholder*='ค้นหา'], input[type='search']"
            
            for keyword in keywords[:5]:  # Limit searches
                if self.debug:
                    print(f"\n🔍 Searching for: {keyword}")
                
                if await self.wait_for_selector(search_selector, timeout=5000):
                    await self.type_text(search_selector, keyword)
                    await asyncio.sleep(1)
                    await self.page.keyboard.press("Enter")
                    await asyncio.sleep(3)
                    
                    # Check results
                    items = await self._parse_search_results(keyword)
                    items_found.extend(items)
                    
                    # Clear search
                    await self.page.fill(search_selector, "")
                    await asyncio.sleep(1)
        
        except Exception as e:
            if self.debug:
                print(f"❌ Search error: {e}")
        
        return items_found
    
    async def _parse_search_results(self, keyword: str) -> List[Dict]:
        """Parse search results for availability"""
        items = []
        
        try:
            # Wait for results
            await asyncio.sleep(2)
            
            # Get product elements
            products = await self.page.query_selector_all("div[class*='product'], div[class*='item']")
            
            for product in products[:20]:
                try:
                    # Get name
                    name_elem = await product.query_selector("h3, h4, p[class*='name']")
                    if not name_elem:
                        continue
                    
                    name = await name_elem.text_content()
                    name = name.strip() if name else ""
                    
                    # Check availability
                    is_available = True
                    html = await product.inner_html()
                    
                    if any(x in html.lower() for x in ["หมด", "sold out", "unavailable"]):
                        is_available = False
                    
                    # Get price
                    price_elem = await product.query_selector("span[class*='price']")
                    price = await price_elem.text_content() if price_elem else "N/A"
                    
                    items.append({
                        "platform": "lineman",
                        "product_name": name,
                        "is_available": is_available,
                        "price": price.strip() if price else "N/A",
                        "timestamp": datetime.now().isoformat(),
                        "search_keyword": keyword
                    })
                    
                    if self.debug:
                        status = "✅" if is_available else "❌"
                        print(f"  {status} {name}")
                
                except Exception as e:
                    if self.debug:
                        print(f"  ⚠️ Parse error: {e}")
                    continue
        
        except Exception as e:
            if self.debug:
                print(f"❌ Results parse error: {e}")
        
        return items
    
    async def scrape_pharmacy_stock(
        self,
        item_categories: Dict[str, List[str]],
        location: str = "Hat Yai"
    ) -> Dict:
        """Complete scraping workflow"""
        result = {
            "platform": "lineman",
            "location": location,
            "timestamp": datetime.now().isoformat(),
            "items": [],
            "success": False
        }
        
        try:
            # Navigate to pharmacy
            if not await self.navigate_to_pharmacy(location):
                return result
            
            # Search each category
            for category, keywords in item_categories.items():
                if self.debug:
                    print(f"\n📦 Category: {category}")
                
                items = await self.search_items(keywords)
                
                for item in items:
                    item["category"] = category
                    result["items"].append(item)
            
            result["success"] = True
            result["total_items_found"] = len(result["items"])
            result["items_available"] = sum(1 for item in result["items"] if item["is_available"])
            result["items_sold_out"] = sum(1 for item in result["items"] if not item["is_available"])
            
            if self.debug:
                print(f"\n✅ Complete: {result['total_items_found']} items found")
        
        except Exception as e:
            if self.debug:
                print(f"❌ Error: {e}")
            result["error"] = str(e)
        
        return result


async def test_lineman_scraper():
    """Test the Lineman scraper"""
    key_items_path = Path(__file__).parent / "key_items.json"
    with open(key_items_path) as f:
        key_items = json.load(f)
    
    item_categories = {
        category: data["keywords"][:3]  # Limit keywords
        for category, data in key_items.items()
        if data["priority"] == "high"
    }
    
    async with LinemanScraper(headless=False, debug=True) as scraper:
        result = await scraper.scrape_pharmacy_stock(
            item_categories=item_categories,
            location="Hat Yai"
        )
        
        output_path = Path("lineman_results.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Results saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(test_lineman_scraper())
