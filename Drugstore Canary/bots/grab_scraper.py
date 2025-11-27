"""
Grab Mart pharmacy scraper
Monitors medicine availability on Grab delivery app
"""
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional
import sys

sys.path.append(str(Path(__file__).parent.parent))

from bots.playwright_scraper import PlaywrightScraper


class GrabScraper(PlaywrightScraper):
    """Scraper for Grab Mart pharmacy section"""
    
    def __init__(self, headless: bool = True, debug: bool = False):
        super().__init__(headless, debug)
        self.base_url = "https://www.grab.com/th/en/mart/"
        self.results = []
    
    async def search_pharmacy(self, pharmacy_name: str, location: str = "Hat Yai") -> bool:
        """
        Search for a specific pharmacy on Grab Mart
        
        Args:
            pharmacy_name: Name of pharmacy (e.g., "Boots", "Watsons")
            location: Location to search in
            
        Returns:
            True if pharmacy found, False otherwise
        """
        try:
            if self.debug:
                print(f"\n🔍 Searching for {pharmacy_name} in {location}...")
            
            # Navigate to Grab Mart
            await self.navigate(self.base_url)
            
            # Wait for page to load
            await asyncio.sleep(3)
            
            # Look for location input
            location_selector = "input[placeholder*='location'], input[placeholder*='address']"
            if await self.wait_for_selector(location_selector, timeout=5000):
                await self.type_text(location_selector, location)
                await asyncio.sleep(2)
            
            # Look for search input
            search_selector = "input[placeholder*='search'], input[type='search']"
            if await self.wait_for_selector(search_selector, timeout=5000):
                await self.type_text(search_selector, pharmacy_name)
                await asyncio.sleep(2)
                
                # Press Enter or click search button
                await self.page.keyboard.press("Enter")
                await asyncio.sleep(3)
            
            # Take screenshot
            await self.take_screenshot(f"grab_{pharmacy_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
            
            return True
            
        except Exception as e:
            if self.debug:
                print(f"❌ Search error: {e}")
            return False
    
    async def check_item_availability(self, item_keywords: List[str]) -> List[Dict]:
        """
        Check availability of specific medicine items
        
        Args:
            item_keywords: List of keywords to search for
            
        Returns:
            List of items with availability status
        """
        items_found = []
        
        try:
            # Scroll to load all items
            await self.scroll_to_bottom(pause_time=2)
            
            # Get all product cards
            product_selectors = [
                "div[class*='product']",
                "div[class*='item']",
                "div[class*='card']",
                "article",
            ]
            
            for selector in product_selectors:
                products = await self.page.query_selector_all(selector)
                
                if products and len(products) > 0:
                    if self.debug:
                        print(f"✓ Found {len(products)} products with selector: {selector}")
                    
                    for product in products[:50]:  # Limit to first 50
                        try:
                            # Get product name
                            name_element = await product.query_selector("h3, h4, h5, p[class*='name'], span[class*='title']")
                            if not name_element:
                                continue
                            
                            product_name = await name_element.text_content()
                            product_name = product_name.strip() if product_name else ""
                            
                            # Check if any keyword matches
                            matches_keyword = any(
                                keyword.lower() in product_name.lower()
                                for keyword in item_keywords
                            )
                            
                            if not matches_keyword:
                                continue
                            
                            # Check availability status
                            is_available = True
                            
                            # Look for "sold out" or "unavailable" indicators
                            sold_out_indicators = [
                                "sold out",
                                "out of stock",
                                "unavailable",
                                "หมด",
                                "ไม่มีสินค้า"
                            ]
                            
                            product_html = await product.inner_html()
                            for indicator in sold_out_indicators:
                                if indicator.lower() in product_html.lower():
                                    is_available = False
                                    break
                            
                            # Check for disabled/grayed out elements
                            if is_available:
                                disabled_element = await product.query_selector("[disabled], [class*='disabled'], [class*='unavailable']")
                                if disabled_element:
                                    is_available = False
                            
                            # Get price if available
                            price_element = await product.query_selector("span[class*='price'], p[class*='price']")
                            price = await price_element.text_content() if price_element else "N/A"
                            
                            item_data = {
                                "platform": "grab",
                                "product_name": product_name,
                                "is_available": is_available,
                                "price": price.strip() if price else "N/A",
                                "timestamp": datetime.now().isoformat(),
                                "matched_keywords": [kw for kw in item_keywords if kw.lower() in product_name.lower()]
                            }
                            
                            items_found.append(item_data)
                            
                            if self.debug:
                                status = "✅ Available" if is_available else "❌ Sold Out"
                                print(f"  {status}: {product_name} - {price}")
                        
                        except Exception as e:
                            if self.debug:
                                print(f"  ⚠️ Error parsing product: {e}")
                            continue
                    
                    break  # Found products, no need to try other selectors
            
            if self.debug:
                print(f"\n📊 Found {len(items_found)} matching items")
            
        except Exception as e:
            if self.debug:
                print(f"❌ Availability check error: {e}")
        
        return items_found
    
    async def scrape_pharmacy_stock(
        self,
        pharmacy_name: str,
        item_categories: Dict[str, List[str]],
        location: str = "Hat Yai"
    ) -> Dict:
        """
        Complete scraping workflow for a pharmacy
        
        Args:
            pharmacy_name: Pharmacy name
            item_categories: Dict of category -> keywords
            location: Location
            
        Returns:
            Scraping results
        """
        result = {
            "pharmacy_name": pharmacy_name,
            "location": location,
            "platform": "grab",
            "timestamp": datetime.now().isoformat(),
            "items": [],
            "success": False
        }
        
        try:
            # Search for pharmacy
            found = await self.search_pharmacy(pharmacy_name, location)
            
            if not found:
                if self.debug:
                    print(f"⚠️ Pharmacy {pharmacy_name} not found")
                return result
            
            # Check each category
            for category, keywords in item_categories.items():
                if self.debug:
                    print(f"\n📦 Checking category: {category}")
                
                items = await self.check_item_availability(keywords)
                
                for item in items:
                    item["category"] = category
                    result["items"].append(item)
            
            result["success"] = True
            result["total_items_found"] = len(result["items"])
            result["items_available"] = sum(1 for item in result["items"] if item["is_available"])
            result["items_sold_out"] = sum(1 for item in result["items"] if not item["is_available"])
            
            if self.debug:
                print(f"\n✅ Scraping complete:")
                print(f"   Total items: {result['total_items_found']}")
                print(f"   Available: {result['items_available']}")
                print(f"   Sold out: {result['items_sold_out']}")
        
        except Exception as e:
            if self.debug:
                print(f"❌ Scraping error: {e}")
            result["error"] = str(e)
        
        return result


async def test_grab_scraper():
    """Test the Grab scraper"""
    # Load key items
    key_items_path = Path(__file__).parent / "key_items.json"
    with open(key_items_path) as f:
        key_items = json.load(f)
    
    # Extract keywords
    item_categories = {
        category: data["keywords"]
        for category, data in key_items.items()
        if data["priority"] in ["high", "medium"]
    }
    
    async with GrabScraper(headless=False, debug=True) as scraper:
        result = await scraper.scrape_pharmacy_stock(
            pharmacy_name="Boots",
            item_categories=item_categories,
            location="Hat Yai"
        )
        
        # Save results
        output_path = Path("grab_results.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Results saved to: {output_path}")


if __name__ == "__main__":
    asyncio.run(test_grab_scraper())
