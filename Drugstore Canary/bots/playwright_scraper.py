"""
Base Playwright scraper with anti-detection measures
"""
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import sys

sys.path.append(str(Path(__file__).parent.parent))

try:
    from playwright.async_api import async_playwright, Page, Browser, BrowserContext
except ImportError:
    print("Playwright not installed. Run: pip install playwright")
    print("Then run: playwright install chromium")
    async_playwright = None

from bots.stealth_config import (
    get_stealth_config,
    get_random_delay,
    TIMING,
    RETRY_CONFIG,
    SCREENSHOT_CONFIG
)


class PlaywrightScraper:
    """Base class for Playwright-based web scrapers"""
    
    def __init__(self, headless: bool = True, debug: bool = False):
        self.headless = headless
        self.debug = debug
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.stealth_config = get_stealth_config()
        
        # Create screenshots directory
        if SCREENSHOT_CONFIG["enabled"]:
            Path(SCREENSHOT_CONFIG["path"]).mkdir(exist_ok=True)
    
    async def initialize(self):
        """Initialize browser and context"""
        if async_playwright is None:
            raise ImportError("Playwright is required")
        
        playwright = await async_playwright().start()
        
        # Launch browser
        self.browser = await playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox',
            ]
        )
        
        # Create context with stealth settings
        self.context = await self.browser.new_context(
            user_agent=self.stealth_config["user_agent"],
            viewport=self.stealth_config["viewport"],
            locale=self.stealth_config["locale"],
            timezone_id=self.stealth_config["timezone_id"],
            geolocation=self.stealth_config["geolocation"],
            permissions=self.stealth_config["permissions"],
            color_scheme=self.stealth_config["color_scheme"],
        )
        
        # Set extra headers
        await self.context.set_extra_http_headers({
            "Accept-Language": "th-TH,th;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        })
        
        # Create page
        self.page = await self.context.new_page()
        
        # Set timeouts
        self.page.set_default_timeout(TIMING["page_load_timeout"])
        self.page.set_default_navigation_timeout(TIMING["navigation_timeout"])
        
        # Inject anti-detection scripts
        await self._inject_stealth_scripts()
        
        if self.debug:
            print(f"✓ Browser initialized with user agent: {self.stealth_config['user_agent'][:50]}...")
    
    async def _inject_stealth_scripts(self):
        """Inject JavaScript to bypass bot detection"""
        await self.page.add_init_script("""
            // Override navigator.webdriver
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Override plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
            
            // Override languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['th-TH', 'th', 'en-US', 'en']
            });
            
            // Chrome runtime
            window.chrome = {
                runtime: {}
            };
            
            // Permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)
    
    async def navigate(self, url: str, wait_until: str = "networkidle") -> bool:
        """
        Navigate to URL with retry logic
        
        Args:
            url: URL to navigate to
            wait_until: Wait condition (load, domcontentloaded, networkidle)
            
        Returns:
            True if successful, False otherwise
        """
        for attempt in range(RETRY_CONFIG["max_retries"]):
            try:
                if self.debug:
                    print(f"Navigating to: {url} (attempt {attempt + 1})")
                
                await self.page.goto(url, wait_until=wait_until)
                
                # Random delay to mimic human behavior
                await asyncio.sleep(get_random_delay() / 1000)
                
                return True
                
            except Exception as e:
                if self.debug:
                    print(f"Navigation error (attempt {attempt + 1}): {e}")
                
                if attempt < RETRY_CONFIG["max_retries"] - 1:
                    delay = RETRY_CONFIG["retry_delay"]
                    if RETRY_CONFIG["exponential_backoff"]:
                        delay *= (2 ** attempt)
                    await asyncio.sleep(delay / 1000)
                else:
                    await self.take_screenshot(f"navigation_error_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
                    return False
        
        return False
    
    async def wait_for_selector(
        self, 
        selector: str, 
        timeout: int = 10000,
        state: str = "visible"
    ) -> bool:
        """
        Wait for element to appear
        
        Args:
            selector: CSS selector
            timeout: Timeout in milliseconds
            state: Element state (visible, attached, hidden)
            
        Returns:
            True if element found, False otherwise
        """
        try:
            await self.page.wait_for_selector(
                selector,
                timeout=timeout,
                state=state
            )
            return True
        except Exception as e:
            if self.debug:
                print(f"Selector not found: {selector} - {e}")
            return False
    
    async def click(self, selector: str, delay: bool = True) -> bool:
        """
        Click element with human-like delay
        
        Args:
            selector: CSS selector
            delay: Whether to add random delay after click
            
        Returns:
            True if successful, False otherwise
        """
        try:
            await self.page.click(selector)
            
            if delay:
                await asyncio.sleep(get_random_delay() / 1000)
            
            return True
        except Exception as e:
            if self.debug:
                print(f"Click error on {selector}: {e}")
            return False
    
    async def type_text(self, selector: str, text: str) -> bool:
        """
        Type text with human-like delays
        
        Args:
            selector: CSS selector
            text: Text to type
            
        Returns:
            True if successful, False otherwise
        """
        try:
            await self.page.fill(selector, "")  # Clear first
            await self.page.type(
                selector,
                text,
                delay=TIMING["typing_delay"]
            )
            return True
        except Exception as e:
            if self.debug:
                print(f"Type error on {selector}: {e}")
            return False
    
    async def get_text(self, selector: str) -> Optional[str]:
        """Get text content of element"""
        try:
            element = await self.page.query_selector(selector)
            if element:
                return await element.text_content()
            return None
        except Exception as e:
            if self.debug:
                print(f"Get text error on {selector}: {e}")
            return None
    
    async def get_attribute(self, selector: str, attribute: str) -> Optional[str]:
        """Get attribute value of element"""
        try:
            element = await self.page.query_selector(selector)
            if element:
                return await element.get_attribute(attribute)
            return None
        except Exception as e:
            if self.debug:
                print(f"Get attribute error on {selector}: {e}")
            return None
    
    async def take_screenshot(self, name: str) -> Optional[str]:
        """
        Take screenshot
        
        Args:
            name: Screenshot filename (without extension)
            
        Returns:
            Path to screenshot file
        """
        if not SCREENSHOT_CONFIG["enabled"]:
            return None
        
        try:
            filepath = Path(SCREENSHOT_CONFIG["path"]) / f"{name}.png"
            await self.page.screenshot(
                path=str(filepath),
                full_page=SCREENSHOT_CONFIG["full_page"]
            )
            if self.debug:
                print(f"Screenshot saved: {filepath}")
            return str(filepath)
        except Exception as e:
            if self.debug:
                print(f"Screenshot error: {e}")
            return None
    
    async def scroll_to_bottom(self, pause_time: float = 1.0):
        """Scroll to bottom of page with pauses"""
        try:
            await self.page.evaluate("""
                async () => {
                    await new Promise((resolve) => {
                        let totalHeight = 0;
                        const distance = 100;
                        const timer = setInterval(() => {
                            const scrollHeight = document.body.scrollHeight;
                            window.scrollBy(0, distance);
                            totalHeight += distance;
                            
                            if(totalHeight >= scrollHeight){
                                clearInterval(timer);
                                resolve();
                            }
                        }, 100);
                    });
                }
            """)
            await asyncio.sleep(pause_time)
        except Exception as e:
            if self.debug:
                print(f"Scroll error: {e}")
    
    async def close(self):
        """Close browser and clean up"""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            
            if self.debug:
                print("✓ Browser closed")
        except Exception as e:
            if self.debug:
                print(f"Close error: {e}")
    
    async def __aenter__(self):
        """Context manager entry"""
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        await self.close()


# Example usage
async def test_scraper():
    """Test the base scraper"""
    async with PlaywrightScraper(headless=False, debug=True) as scraper:
        # Navigate to a test page
        success = await scraper.navigate("https://www.google.com")
        if success:
            print("✓ Navigation successful")
            await scraper.take_screenshot("test_google")
            await asyncio.sleep(2)


if __name__ == "__main__":
    asyncio.run(test_scraper())
