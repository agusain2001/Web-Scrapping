"""
Main scraper module for ADB Projects.

This module provides the ADBProjectScraper class which orchestrates
the scraping process, handling pagination, rate limiting, and error recovery.

Now includes automatic Cloudflare bypass using:
1. CloudScraper - Solves JS challenges automatically
2. Playwright - Full browser automation as fallback
"""

import os
import time
from typing import Generator, List, Optional, Union
from urllib.parse import urljoin
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .models import ProjectListing, ProjectDetail, serialize_projects
from .parsers import ListingPageParser, DetailPageParser, BASE_URL
from .exceptions import (
    ScraperError, NetworkError, ParseError, 
    RateLimitError, CloudflareBlockError
)
from .utils import (
    logger, RateLimiter, retry_with_backoff,
    get_default_headers, get_random_user_agent, build_url
)
from .cloudflare import create_fetcher, HybridFetcher


class ADBProjectScraper:
    """Main scraper class for ADB Projects website.
    
    This class handles the complete scraping workflow including:
    - Session management with proper headers
    - Pagination through listing pages
    - Fetching individual project detail pages
    - Rate limiting and retry logic
    - Error handling and recovery
    
    Example:
        >>> scraper = ADBProjectScraper()
        >>> for project in scraper.scrape_projects(max_pages=5):
        ...     print(project.title)
        
        >>> # Or get all at once
        >>> projects = scraper.scrape_all_projects(max_pages=5)
    """
    
    # Default URLs
    BASE_URL = 'https://www.adb.org'
    PROJECTS_URL = 'https://www.adb.org/projects'
    
    def __init__(
        self,
        request_delay: float = 1.5,
        max_delay: float = 3.0,
        timeout: int = 30,
        max_retries: int = 3,
        proxy: Optional[str] = None,
        rotate_user_agent: bool = True,
        bypass_cloudflare: bool = True,
        fetch_strategy: str = 'hybrid',
    ):
        """Initialize the scraper.
        
        Args:
            request_delay: Minimum delay between requests in seconds
            max_delay: Maximum delay (for random variation)
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts for failed requests
            proxy: Optional proxy URL (http://host:port)
            rotate_user_agent: Whether to rotate User-Agent headers
            bypass_cloudflare: Use advanced Cloudflare bypass (cloudscraper/playwright)
            fetch_strategy: 'hybrid' (recommended), 'cloudscraper', or 'playwright'
        """
        self.request_delay = request_delay
        self.max_delay = max_delay
        self.timeout = timeout
        self.max_retries = max_retries
        self.proxy = proxy
        self.rotate_user_agent = rotate_user_agent
        self.bypass_cloudflare = bypass_cloudflare
        self.fetch_strategy = fetch_strategy
        
        # Initialize rate limiter
        self.rate_limiter = RateLimiter(request_delay, max_delay)
        
        # Initialize session (fallback)
        self.session = self._create_session()
        
        # Initialize Cloudflare bypass fetcher
        self._fetcher = None
        if bypass_cloudflare:
            try:
                self._fetcher = create_fetcher(
                    strategy=fetch_strategy,
                    delay=request_delay,
                )
                logger.info(f"Cloudflare bypass enabled with strategy: {fetch_strategy}")
            except Exception as e:
                logger.warning(f"Failed to initialize Cloudflare bypass: {e}")
                self._fetcher = None
        
        # Statistics
        self.stats = {
            'pages_scraped': 0,
            'projects_found': 0,
            'details_fetched': 0,
            'errors': 0,
            'cloudflare_bypassed': 0,
        }
    
    def _create_session(self) -> requests.Session:
        """Create and configure a requests session.
        
        Returns:
            Configured requests.Session
        """
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=self.max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Set default headers
        session.headers.update(get_default_headers())
        
        # Configure proxy if provided
        if self.proxy:
            session.proxies = {
                'http': self.proxy,
                'https': self.proxy,
            }
        
        return session
    
    def _update_headers(self) -> None:
        """Update session headers, optionally rotating User-Agent."""
        if self.rotate_user_agent:
            self.session.headers['User-Agent'] = get_random_user_agent()
    
    def _fetch_page(self, url: str) -> str:
        """Fetch a page with error handling and Cloudflare bypass.
        
        Args:
            url: URL to fetch
        
        Returns:
            HTML content of the page
        
        Raises:
            NetworkError: If request fails
            RateLimitError: If rate limited
            CloudflareBlockError: If blocked by Cloudflare
        """
        # Try Cloudflare bypass fetcher first
        if self._fetcher:
            try:
                content, status = self._fetcher.fetch(url, timeout=self.timeout)
                
                if status == 429:
                    raise RateLimitError("Rate limited by server", url=url)
                
                if status >= 400:
                    raise NetworkError(f"HTTP {status}", url=url, status_code=status)
                
                self.stats['cloudflare_bypassed'] += 1
                return content
                
            except RuntimeError as e:
                logger.warning(f"Cloudflare bypass failed, trying standard fetch: {e}")
            except Exception as e:
                logger.debug(f"Fetcher error: {e}")
        
        # Fallback to standard requests
        self.rate_limiter.wait()
        self._update_headers()
        
        try:
            response = self.session.get(url, timeout=self.timeout)
            
            # Check for rate limiting
            if response.status_code == 429:
                retry_after = int(response.headers.get('Retry-After', 60))
                raise RateLimitError(
                    "Rate limited by server",
                    url=url,
                    retry_after=retry_after
                )
            
            # Check for Cloudflare block
            if self._is_cloudflare_block(response):
                raise CloudflareBlockError(url=url)
            
            response.raise_for_status()
            return response.text
            
        except requests.exceptions.Timeout:
            raise NetworkError(f"Request timed out after {self.timeout}s", url=url)
        except requests.exceptions.ConnectionError as e:
            raise NetworkError(f"Connection error: {e}", url=url)
        except requests.exceptions.HTTPError as e:
            raise NetworkError(
                f"HTTP error: {e}",
                url=url,
                status_code=e.response.status_code if e.response else None
            )
    
    def _is_cloudflare_block(self, response: requests.Response) -> bool:
        """Check if response indicates Cloudflare protection.
        
        Args:
            response: Response object
        
        Returns:
            True if Cloudflare block detected
        """
        # Check for common Cloudflare indicators
        cloudflare_indicators = [
            'cf-ray' in response.headers,
            'cloudflare' in response.headers.get('server', '').lower(),
            'Checking your browser' in response.text[:1000],
            'cf-browser-verification' in response.text[:1000],
            'Just a moment...' in response.text[:500],
        ]
        
        return any(cloudflare_indicators) and response.status_code in [403, 503]
    
    @retry_with_backoff(max_retries=3, base_delay=2.0, exceptions=(NetworkError,))
    def _fetch_with_retry(self, url: str) -> str:
        """Fetch a page with automatic retry on failure.
        
        Args:
            url: URL to fetch
        
        Returns:
            HTML content
        """
        return self._fetch_page(url)
    
    def scrape_listing_page(self, url: str = None, page: int = None) -> tuple[List[ProjectListing], Optional[str]]:
        """Scrape a single listing page.
        
        Args:
            url: Specific URL to scrape (overrides page parameter)
            page: Page number (1-indexed)
        
        Returns:
            Tuple of (list of projects, next page URL)
        """
        if url is None:
            if page and page > 1:
                url = build_url(self.PROJECTS_URL, page=page - 1)  # ADB uses 0-indexed pages
            else:
                url = self.PROJECTS_URL
        
        logger.info(f"Scraping listing page: {url}")
        
        try:
            html = self._fetch_with_retry(url)
            parser = ListingPageParser(html, url)
            projects = parser.parse()
            next_url = parser.get_next_page_url()
            
            self.stats['pages_scraped'] += 1
            self.stats['projects_found'] += len(projects)
            
            return projects, next_url
            
        except ScraperError as e:
            logger.error(f"Failed to scrape listing page: {e}")
            self.stats['errors'] += 1
            raise
    
    def scrape_project_detail(self, project: ProjectListing) -> ProjectDetail:
        """Scrape detail page for a specific project.
        
        Args:
            project: ProjectListing with detail_url
        
        Returns:
            ProjectDetail with complete information
        """
        logger.debug(f"Scraping detail page: {project.detail_url}")
        
        try:
            html = self._fetch_with_retry(project.detail_url)
            parser = DetailPageParser(html, project.detail_url, project)
            detail = parser.parse()
            
            self.stats['details_fetched'] += 1
            
            return detail
            
        except ScraperError as e:
            logger.warning(f"Failed to scrape detail page for {project.project_id}: {e}")
            self.stats['errors'] += 1
            # Return a ProjectDetail based on listing data
            return ProjectDetail.from_listing(project)
    
    def scrape_projects(
        self,
        max_pages: int = None,
        include_details: bool = False,
        start_page: int = 1,
    ) -> Generator[Union[ProjectListing, ProjectDetail], None, None]:
        """Scrape projects as a generator.
        
        This is memory-efficient for large scraping jobs as it yields
        projects one at a time rather than building a full list.
        
        Args:
            max_pages: Maximum number of listing pages to scrape (None for all)
            include_details: Whether to fetch detail pages for each project
            start_page: Starting page number (1-indexed)
        
        Yields:
            ProjectListing or ProjectDetail objects
        """
        current_page = start_page
        pages_scraped = 0
        next_url = None
        
        while True:
            # Check page limit
            if max_pages and pages_scraped >= max_pages:
                logger.info(f"Reached max pages limit ({max_pages})")
                break
            
            # Determine URL for this page
            if next_url:
                url = next_url
            elif current_page == 1:
                url = self.PROJECTS_URL
            else:
                url = build_url(self.PROJECTS_URL, page=current_page - 1)
            
            try:
                projects, next_url = self.scrape_listing_page(url=url)
                
                # Check if we got any projects
                if not projects:
                    logger.info("No more projects found, stopping")
                    break
                
                # Yield each project
                for project in projects:
                    if include_details:
                        try:
                            detail = self.scrape_project_detail(project)
                            yield detail
                        except Exception as e:
                            logger.warning(f"Error fetching details for {project.project_id}: {e}")
                            yield project
                    else:
                        yield project
                
                pages_scraped += 1
                current_page += 1
                
                # Check if there are more pages
                if not next_url:
                    logger.info("No more pages available")
                    break
                    
            except CloudflareBlockError:
                logger.error("Blocked by Cloudflare. Consider using a proxy or increasing delays.")
                break
            except ScraperError as e:
                logger.error(f"Error scraping page {current_page}: {e}")
                self.stats['errors'] += 1
                break
    
    def scrape_all_projects(
        self,
        max_pages: int = None,
        include_details: bool = False,
        start_page: int = 1,
    ) -> List[Union[ProjectListing, ProjectDetail]]:
        """Scrape all projects and return as a list.
        
        This collects all projects into memory. For large scraping jobs,
        consider using scrape_projects() generator instead.
        
        Args:
            max_pages: Maximum number of listing pages
            include_details: Whether to fetch detail pages
            start_page: Starting page number
        
        Returns:
            List of ProjectListing or ProjectDetail objects
        """
        return list(self.scrape_projects(max_pages, include_details, start_page))
    
    def scrape_single_project(self, project_id: str) -> Optional[ProjectDetail]:
        """Scrape a single project by ID.
        
        Args:
            project_id: Project ID (e.g., "55220-001")
        
        Returns:
            ProjectDetail or None if not found
        """
        url = f"{self.BASE_URL}/projects/{project_id}"
        
        try:
            html = self._fetch_with_retry(url)
            parser = DetailPageParser(html, url)
            return parser.parse()
        except ScraperError as e:
            logger.error(f"Failed to scrape project {project_id}: {e}")
            return None
    
    def get_stats(self) -> dict:
        """Get scraping statistics.
        
        Returns:
            Dictionary with scraping stats
        """
        return self.stats.copy()
    
    def reset_stats(self) -> None:
        """Reset scraping statistics."""
        self.stats = {
            'pages_scraped': 0,
            'projects_found': 0,
            'details_fetched': 0,
            'errors': 0,
        }
    
    def close(self) -> None:
        """Close the session and cleanup resources."""
        if self.session:
            self.session.close()
        if self._fetcher:
            self._fetcher.close()
            self._fetcher = None
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        return False
