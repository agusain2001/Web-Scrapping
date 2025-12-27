"""
Utility functions for the ADB Projects Scraper.

This module provides common utilities including retry logic,
logging configuration, rate limiting, and data validation.
"""

import logging
import time
import random
from functools import wraps
from typing import Callable, Any, List, Optional
from datetime import datetime
import re


# Configure module-level logger
def setup_logger(name: str = 'adb_scraper', level: int = logging.INFO) -> logging.Logger:
    """Configure and return a logger instance.
    
    Args:
        name: Logger name
        level: Logging level (default: INFO)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    logger.setLevel(level)
    return logger


# Default logger instance
logger = setup_logger()


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    exceptions: tuple = (Exception,),
    on_retry: Callable[[Exception, int], None] = None
) -> Callable:
    """Decorator that implements retry logic with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries
        exponential_base: Base for exponential backoff calculation
        jitter: Whether to add random jitter to delays
        exceptions: Tuple of exception types to catch and retry
        on_retry: Optional callback function called on each retry
    
    Returns:
        Decorated function with retry logic
    
    Example:
        @retry_with_backoff(max_retries=3, base_delay=1.0)
        def fetch_page(url):
            return requests.get(url)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        logger.error(f"Max retries ({max_retries}) exceeded for {func.__name__}")
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)
                    
                    # Add jitter to prevent thundering herd
                    if jitter:
                        delay = delay * (0.5 + random.random())
                    
                    logger.warning(
                        f"Attempt {attempt + 1}/{max_retries + 1} failed for {func.__name__}: {e}. "
                        f"Retrying in {delay:.2f}s..."
                    )
                    
                    if on_retry:
                        on_retry(e, attempt)
                    
                    time.sleep(delay)
            
            raise last_exception
        
        return wrapper
    return decorator


class RateLimiter:
    """Rate limiter to control request frequency.
    
    Implements a simple rate limiting mechanism to avoid overwhelming
    the target server with too many requests.
    
    Attributes:
        min_delay: Minimum delay between requests in seconds
        last_request_time: Timestamp of the last request
    """
    
    def __init__(self, min_delay: float = 1.0, max_delay: float = 3.0):
        """Initialize the rate limiter.
        
        Args:
            min_delay: Minimum delay between requests
            max_delay: Maximum delay (for random variation)
        """
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.last_request_time: Optional[float] = None
    
    def wait(self) -> None:
        """Wait the appropriate amount of time before the next request."""
        if self.last_request_time is not None:
            elapsed = time.time() - self.last_request_time
            delay = random.uniform(self.min_delay, self.max_delay)
            
            if elapsed < delay:
                sleep_time = delay - elapsed
                logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f}s")
                time.sleep(sleep_time)
        
        self.last_request_time = time.time()
    
    def reset(self) -> None:
        """Reset the rate limiter."""
        self.last_request_time = None


def clean_text(text: Optional[str]) -> Optional[str]:
    """Clean and normalize text content.
    
    Removes extra whitespace, special characters, and normalizes Unicode.
    
    Args:
        text: Input text to clean
    
    Returns:
        Cleaned text or None if input is None/empty
    """
    if not text:
        return None
    
    # Remove extra whitespace
    text = ' '.join(text.split())
    
    # Strip leading/trailing whitespace
    text = text.strip()
    
    return text if text else None


def extract_project_id(url: str) -> Optional[str]:
    """Extract project ID from a project URL.
    
    Args:
        url: Project URL (e.g., "https://www.adb.org/projects/55220-001")
    
    Returns:
        Project ID (e.g., "55220-001") or None if not found
    """
    if not url:
        return None
    
    # Match project ID pattern (e.g., 55220-001)
    pattern = r'/projects/(\d{5}-\d{3})'
    match = re.search(pattern, url)
    
    if match:
        return match.group(1)
    
    # Alternative patterns
    pattern_alt = r'/projects/([A-Z0-9\-]+)'
    match_alt = re.search(pattern_alt, url, re.IGNORECASE)
    
    return match_alt.group(1) if match_alt else None


def parse_date(date_string: Optional[str]) -> Optional[str]:
    """Parse and normalize date strings.
    
    Attempts to parse various date formats and returns ISO format.
    
    Args:
        date_string: Date string in various formats
    
    Returns:
        ISO format date string (YYYY-MM-DD) or original string if parsing fails
    """
    if not date_string:
        return None
    
    date_string = date_string.strip()
    
    # Common date formats to try
    formats = [
        '%Y-%m-%d',
        '%d %b %Y',
        '%d %B %Y',
        '%B %d, %Y',
        '%b %d, %Y',
        '%m/%d/%Y',
        '%d/%m/%Y',
        '%Y',
    ]
    
    for fmt in formats:
        try:
            parsed = datetime.strptime(date_string, fmt)
            return parsed.strftime('%Y-%m-%d')
        except ValueError:
            continue
    
    # Return original if no format matches
    return date_string


def parse_amount(amount_string: Optional[str]) -> Optional[str]:
    """Parse and normalize financial amounts.
    
    Args:
        amount_string: Amount string (e.g., "$500 million", "USD 1.5 billion")
    
    Returns:
        Normalized amount string or original if parsing fails
    """
    if not amount_string:
        return None
    
    return clean_text(amount_string)


def safe_get(dictionary: dict, *keys, default=None) -> Any:
    """Safely get nested dictionary values.
    
    Args:
        dictionary: The dictionary to search
        *keys: Keys to traverse
        default: Default value if key not found
    
    Returns:
        Value at the nested key or default
    
    Example:
        safe_get(data, 'project', 'details', 'title', default='Unknown')
    """
    result = dictionary
    
    for key in keys:
        try:
            result = result[key]
        except (KeyError, TypeError, IndexError):
            return default
    
    return result


def build_url(base_url: str, **params) -> str:
    """Build URL with query parameters.
    
    Args:
        base_url: Base URL
        **params: Query parameters
    
    Returns:
        Complete URL with query string
    """
    from urllib.parse import urlencode, urlparse, urlunparse, parse_qs
    
    parsed = urlparse(base_url)
    existing_params = parse_qs(parsed.query)
    
    # Update with new params
    existing_params.update({k: [str(v)] for k, v in params.items() if v is not None})
    
    # Flatten single-value lists
    flattened = {k: v[0] if len(v) == 1 else v for k, v in existing_params.items()}
    
    new_query = urlencode(flattened, doseq=True)
    
    return urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        parsed.params,
        new_query,
        parsed.fragment
    ))


# User agent rotation for avoiding blocks
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
]


def get_random_user_agent() -> str:
    """Get a random user agent string.
    
    Returns:
        Random user agent from the predefined list
    """
    return random.choice(USER_AGENTS)


def get_default_headers() -> dict:
    """Get default HTTP headers for requests.
    
    Returns:
        Dictionary of HTTP headers
    """
    return {
        'User-Agent': get_random_user_agent(),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1',
        'Cache-Control': 'max-age=0',
    }
