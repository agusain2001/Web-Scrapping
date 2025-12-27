"""
Cloudflare bypass module for ADB Projects Scraper.

This module provides multiple strategies to bypass Cloudflare protection:
1. cloudscraper - Solves Cloudflare challenges automatically
2. Playwright - Full browser automation as fallback
3. Enhanced session with realistic browser fingerprinting
"""

import time
import random
from typing import Optional, Tuple
from abc import ABC, abstractmethod

from .utils import logger, get_random_user_agent


class BaseFetcher(ABC):
    """Abstract base class for page fetchers."""
    
    @abstractmethod
    def fetch(self, url: str, timeout: int = 30) -> Tuple[str, int]:
        """Fetch a page and return (content, status_code)."""
        pass
    
    @abstractmethod
    def close(self) -> None:
        """Clean up resources."""
        pass


class CloudscraperFetcher(BaseFetcher):
    """Fetcher using cloudscraper to bypass Cloudflare.
    
    cloudscraper automatically handles:
    - JavaScript challenges
    - CAPTCHA (using 2captcha if configured)
    - Browser fingerprinting
    """
    
    def __init__(self, delay: float = 1.5):
        self.delay = delay
        self._session = None
        self._last_request = 0
    
    @property
    def session(self):
        """Lazy-load cloudscraper session."""
        if self._session is None:
            try:
                import cloudscraper
                self._session = cloudscraper.create_scraper(
                    browser={
                        'browser': 'chrome',
                        'platform': 'windows',
                        'desktop': True,
                    },
                    delay=10,  # Delay between retries for challenges
                )
                logger.info("CloudScraper session initialized")
            except ImportError:
                logger.warning("cloudscraper not installed, falling back to requests")
                import requests
                self._session = requests.Session()
                self._session.headers.update({
                    'User-Agent': get_random_user_agent(),
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                })
        return self._session
    
    def _rate_limit(self):
        """Enforce rate limiting."""
        elapsed = time.time() - self._last_request
        if elapsed < self.delay:
            sleep_time = self.delay - elapsed + random.uniform(0.1, 0.5)
            time.sleep(sleep_time)
        self._last_request = time.time()
    
    def fetch(self, url: str, timeout: int = 30) -> Tuple[str, int]:
        """Fetch page using cloudscraper."""
        self._rate_limit()
        
        try:
            response = self.session.get(url, timeout=timeout)
            return response.text, response.status_code
        except Exception as e:
            logger.error(f"CloudScraper fetch failed: {e}")
            raise
    
    def close(self) -> None:
        """Close the session."""
        if self._session:
            self._session.close()
            self._session = None


class PlaywrightFetcher(BaseFetcher):
    """Fetcher using Playwright for full browser automation.
    
    This is the most reliable but slowest option. Use as fallback
    when cloudscraper fails.
    """
    
    def __init__(self, headless: bool = False, delay: float = 2.0, slow_mo: int = 100):
        # Default to visible browser as it's harder for Cloudflare to detect
        self.headless = headless
        self.delay = delay
        self.slow_mo = slow_mo
        self._browser = None
        self._context = None
        self._page = None
        self._playwright = None
        self._last_request = 0
    
    def _ensure_browser(self):
        """Initialize Playwright browser if needed."""
        if self._browser is None:
            try:
                from playwright.sync_api import sync_playwright
                
                self._playwright = sync_playwright().start()
                self._browser = self._playwright.chromium.launch(
                    headless=self.headless,
                    slow_mo=self.slow_mo,  # Slow down actions to appear more human
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox',
                        '--disable-setuid-sandbox',
                        '--disable-infobars',
                        '--window-size=1920,1080',
                        '--start-maximized',
                    ]
                )
                self._context = self._browser.new_context(
                    viewport={'width': 1920, 'height': 1080},
                    user_agent=get_random_user_agent(),
                    locale='en-US',
                    timezone_id='America/New_York',
                    geolocation={'latitude': 40.7128, 'longitude': -74.0060},
                    permissions=['geolocation'],
                )
                
                # Add comprehensive stealth scripts
                self._context.add_init_script("""
                    // Override webdriver property
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    });
                    
                    // Override plugins
                    Object.defineProperty(navigator, 'plugins', {
                        get: () => [
                            { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer' },
                            { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai' },
                            { name: 'Native Client', filename: 'internal-nacl-plugin' }
                        ]
                    });
                    
                    // Override languages
                    Object.defineProperty(navigator, 'languages', {
                        get: () => ['en-US', 'en']
                    });
                    
                    // Override platform
                    Object.defineProperty(navigator, 'platform', {
                        get: () => 'Win32'
                    });
                    
                    // Override hardware concurrency
                    Object.defineProperty(navigator, 'hardwareConcurrency', {
                        get: () => 8
                    });
                    
                    // Override device memory
                    Object.defineProperty(navigator, 'deviceMemory', {
                        get: () => 8
                    });
                    
                    // Mock chrome runtime
                    window.chrome = {
                        runtime: {},
                        loadTimes: function() {},
                        csi: function() {},
                        app: {}
                    };
                    
                    // Override permissions query
                    const originalQuery = window.navigator.permissions.query;
                    window.navigator.permissions.query = (parameters) => (
                        parameters.name === 'notifications' ?
                            Promise.resolve({ state: Notification.permission }) :
                            originalQuery(parameters)
                    );
                """)
                
                self._page = self._context.new_page()
                logger.info("Playwright browser initialized")
                
            except ImportError:
                raise ImportError(
                    "Playwright is not installed. Run: pip install playwright && playwright install chromium"
                )
            except Exception as e:
                raise RuntimeError(f"Failed to initialize Playwright: {e}")
    
    def _rate_limit(self):
        """Enforce rate limiting."""
        elapsed = time.time() - self._last_request
        if elapsed < self.delay:
            sleep_time = self.delay - elapsed + random.uniform(0.2, 1.0)
            time.sleep(sleep_time)
        self._last_request = time.time()
    
    def fetch(self, url: str, timeout: int = 60) -> Tuple[str, int]:
        """Fetch page using Playwright browser."""
        self._ensure_browser()
        self._rate_limit()
        
        try:
            # Navigate with longer timeout
            response = self._page.goto(url, timeout=timeout * 1000, wait_until='domcontentloaded')
            
            # Initial wait
            self._page.wait_for_timeout(3000)
            
            # Check for Cloudflare challenge and wait longer if needed
            content = self._page.content()
            max_wait = 30000  # 30 seconds max wait for challenge
            waited = 0
            wait_interval = 2000
            
            while waited < max_wait and ('Checking your browser' in content or 'Just a moment' in content):
                logger.info(f"Cloudflare challenge detected, waiting... ({waited//1000}s)")
                self._page.wait_for_timeout(wait_interval)
                waited += wait_interval
                content = self._page.content()
            
            # Final wait for page to fully render
            self._page.wait_for_timeout(2000)
            content = self._page.content()
            
            status = response.status if response else 200
            return content, status
            
        except Exception as e:
            logger.error(f"Playwright fetch failed: {e}")
            raise
    
    def close(self) -> None:
        """Close the browser."""
        if self._page:
            self._page.close()
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()
        
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None


class HybridFetcher(BaseFetcher):
    """Fetcher that tries multiple strategies in order.
    
    1. First tries CloudScraper (fastest)
    2. Falls back to Playwright if blocked
    """
    
    def __init__(self, delay: float = 1.5, use_playwright_fallback: bool = True):
        self.delay = delay
        self.use_playwright_fallback = use_playwright_fallback
        
        self._cloudscraper = CloudscraperFetcher(delay=delay)
        self._playwright: Optional[PlaywrightFetcher] = None
        
        self._cloudflare_detected = False
        self._consecutive_failures = 0
    
    def _is_blocked(self, content: str, status_code: int) -> bool:
        """Check if request was blocked by Cloudflare."""
        if status_code in [403, 503]:
            blockers = [
                'Checking your browser',
                'Just a moment',
                'cf-browser-verification',
                'challenge-platform',
                'Cloudflare Ray ID',
            ]
            return any(blocker in content for blocker in blockers)
        return False
    
    def fetch(self, url: str, timeout: int = 30) -> Tuple[str, int]:
        """Fetch page, trying multiple strategies."""
        
        # If we know Cloudflare is active, skip to Playwright
        if not self._cloudflare_detected:
            try:
                content, status = self._cloudscraper.fetch(url, timeout)
                
                if not self._is_blocked(content, status):
                    self._consecutive_failures = 0
                    return content, status
                
                logger.warning("CloudScraper blocked by Cloudflare")
                self._cloudflare_detected = True
                
            except Exception as e:
                logger.warning(f"CloudScraper failed: {e}")
                self._consecutive_failures += 1
        
        # Try Playwright as fallback
        if self.use_playwright_fallback:
            logger.info("Trying Playwright fallback...")
            
            if self._playwright is None:
                self._playwright = PlaywrightFetcher(delay=self.delay)
            
            try:
                content, status = self._playwright.fetch(url, timeout)
                
                if not self._is_blocked(content, status):
                    return content, status
                
                logger.error("Playwright also blocked, site may require manual intervention")
                
            except ImportError:
                logger.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
            except Exception as e:
                logger.error(f"Playwright failed: {e}")
        
        raise RuntimeError(f"All fetch strategies failed for {url}")
    
    def close(self) -> None:
        """Close all fetchers."""
        self._cloudscraper.close()
        if self._playwright:
            self._playwright.close()


def create_fetcher(
    strategy: str = 'hybrid',
    delay: float = 1.5,
    headless: bool = True,
) -> BaseFetcher:
    """Factory function to create the appropriate fetcher.
    
    Args:
        strategy: One of 'cloudscraper', 'playwright', or 'hybrid'
        delay: Delay between requests
        headless: Whether to run browser in headless mode
    
    Returns:
        Configured fetcher instance
    """
    if strategy == 'cloudscraper':
        return CloudscraperFetcher(delay=delay)
    elif strategy == 'playwright':
        return PlaywrightFetcher(headless=headless, delay=delay)
    elif strategy == 'hybrid':
        return HybridFetcher(delay=delay, use_playwright_fallback=True)
    else:
        raise ValueError(f"Unknown strategy: {strategy}")
