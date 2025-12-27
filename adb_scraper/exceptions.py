"""
Custom exceptions for the ADB Projects Scraper.

This module defines a hierarchy of exceptions for clear error handling
and debugging throughout the scraping process.
"""


class ScraperError(Exception):
    """Base exception for all scraper-related errors.
    
    All custom exceptions in this module inherit from this class,
    allowing for broad exception catching when needed.
    """
    
    def __init__(self, message: str, url: str = None):
        self.message = message
        self.url = url
        super().__init__(self.message)
    
    def __str__(self):
        if self.url:
            return f"{self.message} (URL: {self.url})"
        return self.message


class NetworkError(ScraperError):
    """Exception raised for network-related failures.
    
    This includes connection timeouts, DNS resolution failures,
    and other transport-layer issues.
    
    Attributes:
        status_code: HTTP status code if available
        retry_after: Suggested retry delay in seconds
    """
    
    def __init__(self, message: str, url: str = None, status_code: int = None, retry_after: int = None):
        super().__init__(message, url)
        self.status_code = status_code
        self.retry_after = retry_after
    
    def __str__(self):
        base = super().__str__()
        if self.status_code:
            base = f"{base} [Status: {self.status_code}]"
        return base


class ParseError(ScraperError):
    """Exception raised when HTML parsing fails.
    
    This is raised when the expected HTML structure is not found
    or when data extraction from HTML elements fails.
    
    Attributes:
        element: The CSS selector or element description that failed
    """
    
    def __init__(self, message: str, url: str = None, element: str = None):
        super().__init__(message, url)
        self.element = element
    
    def __str__(self):
        base = super().__str__()
        if self.element:
            base = f"{base} [Element: {self.element}]"
        return base


class RateLimitError(NetworkError):
    """Exception raised when rate limiting is detected.
    
    This is a specific type of NetworkError that indicates the server
    has responded with a 429 Too Many Requests status.
    
    Attributes:
        retry_after: Seconds to wait before retrying (from Retry-After header)
    """
    
    def __init__(self, message: str, url: str = None, retry_after: int = None):
        super().__init__(message, url, status_code=429, retry_after=retry_after)


class CloudflareBlockError(ScraperError):
    """Exception raised when Cloudflare protection is detected.
    
    This indicates that the request was blocked by Cloudflare's
    bot detection mechanism.
    """
    
    def __init__(self, message: str = "Request blocked by Cloudflare protection", url: str = None):
        super().__init__(message, url)


class ValidationError(ScraperError):
    """Exception raised when data validation fails.
    
    This is raised when extracted data doesn't match expected formats
    or when required fields are missing.
    
    Attributes:
        field: The field that failed validation
        value: The invalid value
    """
    
    def __init__(self, message: str, field: str = None, value: any = None):
        super().__init__(message)
        self.field = field
        self.value = value
    
    def __str__(self):
        base = self.message
        if self.field:
            base = f"{base} [Field: {self.field}]"
        if self.value is not None:
            base = f"{base} [Value: {self.value}]"
        return base
