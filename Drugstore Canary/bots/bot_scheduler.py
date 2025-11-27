"""
Bot scheduler for automated stock monitoring
Runs scrapers at scheduled intervals
"""
import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List
import sys

sys.path.append(str(Path(__file__).parent.parent))

from bots.grab_scraper import GrabScraper
from bots.lineman_scraper import LinemanScraper


class BotScheduler:
    """Schedule and manage scraping bots"""
    
    def __init__(self, interval_hours: int = 2, debug: bool = False):
        self.interval_hours = interval_hours
        self.debug = debug
        self.results_dir = Path(__file__).parent.parent / "bot_results"
        self.results_dir.mkdir(exist_ok=True)
        
        # Load key items
        key_items_path = Path(__file__).parent / "key_items.json"
        with open(key_items_path) as f:
            self.key_items = json.load(f)
        
        # Extract high-priority keywords
        self.item_categories = {
            category: data["keywords"]
            for category, data in self.key_items.items()
            if data["priority"] in ["high", "medium"]
        }
        
        # Pharmacies to monitor
        self.pharmacies = ["Boots", "Watsons", "Fascino"]
        
        self.running = False
    
    async def run_grab_scraper(self) -> Dict:
        """Run Grab scraper for all pharmacies"""
        if self.debug:
            print(f"\n{'='*60}")
            print(f"🟢 Running Grab Scraper - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*60}")
        
        all_results = []
        
        for pharmacy in self.pharmacies:
            try:
                async with GrabScraper(headless=True, debug=self.debug) as scraper:
                    result = await scraper.scrape_pharmacy_stock(
                        pharmacy_name=pharmacy,
                        item_categories=self.item_categories,
                        location="Hat Yai"
                    )
                    all_results.append(result)
                    
                    # Small delay between pharmacies
                    await asyncio.sleep(30)
            
            except Exception as e:
                if self.debug:
                    print(f"❌ Grab scraper error for {pharmacy}: {e}")
                all_results.append({
                    "pharmacy_name": pharmacy,
                    "platform": "grab",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                })
        
        return {
            "platform": "grab",
            "timestamp": datetime.now().isoformat(),
            "pharmacies": all_results
        }
    
    async def run_lineman_scraper(self) -> Dict:
        """Run Lineman scraper"""
        if self.debug:
            print(f"\n{'='*60}")
            print(f"🔵 Running Lineman Scraper - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"{'='*60}")
        
        try:
            async with LinemanScraper(headless=True, debug=self.debug) as scraper:
                result = await scraper.scrape_pharmacy_stock(
                    item_categories=self.item_categories,
                    location="Hat Yai"
                )
                return result
        
        except Exception as e:
            if self.debug:
                print(f"❌ Lineman scraper error: {e}")
            return {
                "platform": "lineman",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }
    
    async def run_all_scrapers(self) -> List[Dict]:
        """Run all scrapers in sequence"""
        results = []
        
        # Run Grab
        grab_result = await self.run_grab_scraper()
        results.append(grab_result)
        
        # Delay between platforms
        await asyncio.sleep(60)
        
        # Run Lineman
        lineman_result = await self.run_lineman_scraper()
        results.append(lineman_result)
        
        # Save results
        self._save_results(results)
        
        return results
    
    def _save_results(self, results: List[Dict]):
        """Save scraping results to file"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = self.results_dir / f"stock_check_{timestamp}.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        if self.debug:
            print(f"\n💾 Results saved to: {filename}")
        
        # Also save to latest.json for easy access
        latest_file = self.results_dir / "latest.json"
        with open(latest_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
    
    async def start_scheduled_monitoring(self):
        """Start continuous monitoring at scheduled intervals"""
        self.running = True
        
        print(f"\n{'='*60}")
        print(f"🤖 Stock Monitoring Bot Started")
        print(f"{'='*60}")
        print(f"Interval: Every {self.interval_hours} hours")
        print(f"Platforms: Grab, Lineman")
        print(f"Pharmacies: {', '.join(self.pharmacies)}")
        print(f"Results directory: {self.results_dir}")
        print(f"{'='*60}\n")
        
        run_count = 0
        
        while self.running:
            run_count += 1
            
            print(f"\n🔄 Run #{run_count} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            try:
                # Run all scrapers
                results = await self.run_all_scrapers()
                
                # Calculate summary
                total_items = 0
                total_sold_out = 0
                
                for platform_result in results:
                    if "pharmacies" in platform_result:
                        for pharmacy in platform_result["pharmacies"]:
                            if "items" in pharmacy:
                                total_items += len(pharmacy["items"])
                                total_sold_out += sum(
                                    1 for item in pharmacy["items"]
                                    if not item.get("is_available", True)
                                )
                    elif "items" in platform_result:
                        total_items += len(platform_result["items"])
                        total_sold_out += sum(
                            1 for item in platform_result["items"]
                            if not item.get("is_available", True)
                        )
                
                stockout_rate = (total_sold_out / total_items * 100) if total_items > 0 else 0
                
                print(f"\n📊 Summary:")
                print(f"   Total items checked: {total_items}")
                print(f"   Sold out: {total_sold_out}")
                print(f"   Stockout rate: {stockout_rate:.1f}%")
                
                # Alert if high stockout rate
                if stockout_rate > 30:
                    print(f"\n⚠️  HIGH STOCKOUT RATE DETECTED: {stockout_rate:.1f}%")
                
            except Exception as e:
                print(f"\n❌ Error in run #{run_count}: {e}")
            
            # Wait for next interval
            next_run = datetime.now() + timedelta(hours=self.interval_hours)
            print(f"\n⏰ Next run scheduled at: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   Sleeping for {self.interval_hours} hours...")
            
            await asyncio.sleep(self.interval_hours * 3600)
    
    def stop(self):
        """Stop the scheduler"""
        self.running = False
        print("\n🛑 Stopping scheduler...")


async def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Stock monitoring bot scheduler")
    parser.add_argument(
        "--interval",
        type=int,
        default=2,
        help="Interval between runs in hours (default: 2)"
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run once and exit (don't schedule)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug output"
    )
    
    args = parser.parse_args()
    
    scheduler = BotScheduler(
        interval_hours=args.interval,
        debug=args.debug
    )
    
    if args.once:
        print("🔄 Running once...")
        await scheduler.run_all_scrapers()
        print("✅ Complete!")
    else:
        try:
            await scheduler.start_scheduled_monitoring()
        except KeyboardInterrupt:
            scheduler.stop()
            print("\n✅ Scheduler stopped by user")


if __name__ == "__main__":
    asyncio.run(main())
