"""
Stealth configuration for web scraping bots
Anti-detection measures to avoid bot blocking
"""
import random

# User agents pool (recent browsers)
USER_AGENTS = [
    # Chrome on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    # Firefox on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0",
    # Safari on Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    # Edge
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
]

# Viewport sizes (common resolutions)
VIEWPORTS = [
    {"width": 1920, "height": 1080},
    {"width": 1366, "height": 768},
    {"width": 1536, "height": 864},
    {"width": 1440, "height": 900},
    {"width": 1280, "height": 720},
]

# Stealth settings for Playwright
STEALTH_CONFIG = {
    "user_agent": random.choice(USER_AGENTS),
    "viewport": random.choice(VIEWPORTS),
    "locale": "th-TH",
    "timezone_id": "Asia/Bangkok",
    "geolocation": {
        "latitude": 7.0087,
        "longitude": 100.4754,
        "accuracy": 100
    },
    "permissions": ["geolocation"],
    "color_scheme": "light",
    "reduced_motion": "no-preference",
    "forced_colors": "none",
}

# Timing settings (in milliseconds)
TIMING = {
    "page_load_timeout": 30000,
    "navigation_timeout": 30000,
    "min_delay": 2000,  # Minimum delay between actions
    "max_delay": 5000,  # Maximum delay between actions
    "typing_delay": 100,  # Delay between keystrokes
}

# Retry settings
RETRY_CONFIG = {
    "max_retries": 3,
    "retry_delay": 5000,  # 5 seconds
    "exponential_backoff": True,
}

# Screenshot settings
SCREENSHOT_CONFIG = {
    "enabled": True,
    "on_error": True,
    "full_page": False,
    "path": "screenshots",
}


def get_random_user_agent():
    """Get a random user agent from the pool"""
    return random.choice(USER_AGENTS)


def get_random_viewport():
    """Get a random viewport size"""
    return random.choice(VIEWPORTS)


def get_random_delay():
    """Get a random delay between min and max"""
    return random.randint(TIMING["min_delay"], TIMING["max_delay"])


def get_stealth_config():
    """Get a fresh stealth configuration with randomized values"""
    return {
        "user_agent": get_random_user_agent(),
        "viewport": get_random_viewport(),
        "locale": STEALTH_CONFIG["locale"],
        "timezone_id": STEALTH_CONFIG["timezone_id"],
        "geolocation": STEALTH_CONFIG["geolocation"],
        "permissions": STEALTH_CONFIG["permissions"],
        "color_scheme": STEALTH_CONFIG["color_scheme"],
        "reduced_motion": STEALTH_CONFIG["reduced_motion"],
        "forced_colors": STEALTH_CONFIG["forced_colors"],
    }
