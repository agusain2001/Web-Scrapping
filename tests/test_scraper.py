"""
Unit tests for the ADB Projects Scraper.

Run with: python -m pytest tests/ -v
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

# Import modules to test
from adb_scraper.models import ProjectListing, ProjectDetail, serialize_projects
from adb_scraper.parsers import ListingPageParser, DetailPageParser
from adb_scraper.utils import (
    clean_text, extract_project_id, parse_date, parse_amount,
    RateLimiter, retry_with_backoff, get_random_user_agent
)
from adb_scraper.exceptions import (
    ScraperError, NetworkError, ParseError, RateLimitError, CloudflareBlockError
)


# =============================================================================
# Test Data Models
# =============================================================================

class TestProjectListing:
    """Tests for ProjectListing dataclass."""
    
    def test_creation_with_required_fields(self):
        """Test creating a listing with required fields only."""
        listing = ProjectListing(
            project_id="55220-001",
            title="Test Project",
            detail_url="https://www.adb.org/projects/55220-001"
        )
        
        assert listing.project_id == "55220-001"
        assert listing.title == "Test Project"
        assert listing.detail_url == "https://www.adb.org/projects/55220-001"
        assert listing.country is None
    
    def test_creation_with_all_fields(self):
        """Test creating a listing with all fields."""
        listing = ProjectListing(
            project_id="55220-001",
            title="  Test Project  ",  # With whitespace
            detail_url="https://www.adb.org/projects/55220-001",
            country="  India  ",
            sector="Transport",
            status="Active",
            approval_date="2023-05-15",
            project_type="Loan",
            region="South Asia"
        )
        
        # Whitespace should be stripped
        assert listing.title == "Test Project"
        assert listing.country == "India"
    
    def test_to_dict(self):
        """Test converting to dictionary."""
        listing = ProjectListing(
            project_id="55220-001",
            title="Test Project",
            detail_url="https://www.adb.org/projects/55220-001"
        )
        
        data = listing.to_dict()
        
        assert isinstance(data, dict)
        assert data['project_id'] == "55220-001"
        assert data['title'] == "Test Project"
    
    def test_from_dict(self):
        """Test creating from dictionary."""
        data = {
            'project_id': '55220-001',
            'title': 'Test Project',
            'detail_url': 'https://www.adb.org/projects/55220-001',
            'country': 'India'
        }
        
        listing = ProjectListing.from_dict(data)
        
        assert listing.project_id == "55220-001"
        assert listing.country == "India"


class TestProjectDetail:
    """Tests for ProjectDetail dataclass."""
    
    def test_from_listing(self):
        """Test creating detail from listing."""
        listing = ProjectListing(
            project_id="55220-001",
            title="Test Project",
            detail_url="https://www.adb.org/projects/55220-001",
            country="India",
            sector="Transport"
        )
        
        detail = ProjectDetail.from_listing(listing)
        
        assert detail.project_id == "55220-001"
        assert detail.title == "Test Project"
        assert detail.country == "India"
        assert detail.sector == "Transport"
        assert detail.scraped_at is not None
    
    def test_merge_with_listing(self):
        """Test merging with listing data."""
        listing = ProjectListing(
            project_id="55220-001",
            title="Test Project",
            detail_url="https://www.adb.org/projects/55220-001",
            country="India",
            sector="Transport"
        )
        
        detail = ProjectDetail(
            project_id="55220-001",
            title="Test Project",
            detail_url="https://www.adb.org/projects/55220-001"
        )
        
        # Detail has no country, should be filled from listing
        detail.merge_with_listing(listing)
        
        assert detail.country == "India"
        assert detail.sector == "Transport"


class TestSerializeProjects:
    """Tests for serialize_projects function."""
    
    def test_serialize_json(self):
        """Test JSON serialization."""
        projects = [
            ProjectDetail(
                project_id="55220-001",
                title="Test Project",
                detail_url="https://www.adb.org/projects/55220-001"
            )
        ]
        
        output = serialize_projects(projects, 'json')
        
        assert isinstance(output, str)
        assert '55220-001' in output
        assert 'Test Project' in output
    
    def test_serialize_csv(self):
        """Test CSV serialization."""
        projects = [
            ProjectDetail(
                project_id="55220-001",
                title="Test Project",
                detail_url="https://www.adb.org/projects/55220-001",
                themes=["Climate", "Urban"]
            )
        ]
        
        output = serialize_projects(projects, 'csv')
        
        assert isinstance(output, str)
        assert 'project_id' in output  # Header
        assert '55220-001' in output
        # Lists should be joined with semicolons
        assert 'Climate; Urban' in output


# =============================================================================
# Test Utilities
# =============================================================================

class TestCleanText:
    """Tests for clean_text function."""
    
    def test_clean_normal_text(self):
        """Test cleaning normal text."""
        assert clean_text("Hello World") == "Hello World"
    
    def test_clean_whitespace(self):
        """Test cleaning extra whitespace."""
        assert clean_text("  Hello   World  ") == "Hello World"
        assert clean_text("\n\tHello\n\tWorld\t") == "Hello World"
    
    def test_clean_empty(self):
        """Test cleaning empty/None values."""
        assert clean_text("") is None
        assert clean_text(None) is None
        assert clean_text("   ") is None


class TestExtractProjectId:
    """Tests for extract_project_id function."""
    
    def test_extract_from_url(self):
        """Test extracting ID from project URL."""
        url = "https://www.adb.org/projects/55220-001/main"
        assert extract_project_id(url) == "55220-001"
    
    def test_extract_simple_url(self):
        """Test extracting from simple URL."""
        url = "https://www.adb.org/projects/55220-001"
        assert extract_project_id(url) == "55220-001"
    
    def test_extract_invalid_url(self):
        """Test with invalid URL."""
        assert extract_project_id("https://example.com/page") is None
        assert extract_project_id(None) is None
        assert extract_project_id("") is None


class TestParseDate:
    """Tests for parse_date function."""
    
    def test_parse_iso_format(self):
        """Test parsing ISO format date."""
        assert parse_date("2023-05-15") == "2023-05-15"
    
    def test_parse_various_formats(self):
        """Test parsing various date formats."""
        assert parse_date("15 May 2023") == "2023-05-15"
        assert parse_date("May 15, 2023") == "2023-05-15"
    
    def test_parse_invalid(self):
        """Test with invalid/unknown format."""
        assert parse_date("invalid date") == "invalid date"
        assert parse_date(None) is None


class TestRateLimiter:
    """Tests for RateLimiter class."""
    
    def test_first_request_no_wait(self):
        """First request should not wait."""
        limiter = RateLimiter(min_delay=1.0, max_delay=2.0)
        
        import time
        start = time.time()
        limiter.wait()
        elapsed = time.time() - start
        
        assert elapsed < 0.1  # Should be nearly instant
    
    def test_reset(self):
        """Test reset functionality."""
        limiter = RateLimiter(min_delay=1.0, max_delay=2.0)
        limiter.wait()
        
        assert limiter.last_request_time is not None
        
        limiter.reset()
        
        assert limiter.last_request_time is None


class TestUserAgentRotation:
    """Tests for user agent rotation."""
    
    def test_get_random_user_agent(self):
        """Test getting random user agent."""
        ua = get_random_user_agent()
        
        assert isinstance(ua, str)
        assert 'Mozilla' in ua


# =============================================================================
# Test Exceptions
# =============================================================================

class TestExceptions:
    """Tests for custom exceptions."""
    
    def test_scraper_error(self):
        """Test base ScraperError."""
        error = ScraperError("Test error", url="https://example.com")
        
        assert "Test error" in str(error)
        assert "https://example.com" in str(error)
    
    def test_network_error(self):
        """Test NetworkError with status code."""
        error = NetworkError("Connection failed", url="https://example.com", status_code=500)
        
        assert "Connection failed" in str(error)
        assert "500" in str(error)
    
    def test_rate_limit_error(self):
        """Test RateLimitError."""
        error = RateLimitError("Rate limited", retry_after=60)
        
        assert error.status_code == 429
        assert error.retry_after == 60
    
    def test_cloudflare_block_error(self):
        """Test CloudflareBlockError."""
        error = CloudflareBlockError(url="https://example.com")
        
        assert "Cloudflare" in str(error)


# =============================================================================
# Test Parsers
# =============================================================================

class TestListingPageParser:
    """Tests for ListingPageParser."""
    
    # Sample HTML for testing
    SAMPLE_HTML = """
    <html>
    <body>
        <div class="view-content">
            <div class="views-row">
                <h3><a href="/projects/55220-001">Test Project 1</a></h3>
                <div class="views-field-field-countries">India</div>
                <div class="views-field-field-sectors">Transport</div>
                <div class="views-field-field-status">Active</div>
            </div>
            <div class="views-row">
                <h3><a href="/projects/55221-002">Test Project 2</a></h3>
                <div class="views-field-field-countries">Philippines</div>
                <div class="views-field-field-sectors">Energy</div>
                <div class="views-field-field-status">Closed</div>
            </div>
        </div>
        <div class="pager">
            <a class="pager-next" href="/projects?page=2">Next</a>
        </div>
    </body>
    </html>
    """
    
    def test_parse_projects(self):
        """Test parsing project listings."""
        parser = ListingPageParser(self.SAMPLE_HTML, "https://www.adb.org/projects")
        projects = parser.parse()
        
        assert len(projects) == 2
        assert projects[0].project_id == "55220-001"
        assert projects[0].title == "Test Project 1"
        assert projects[0].country == "India"
        assert projects[1].project_id == "55221-002"
    
    def test_get_next_page_url(self):
        """Test getting next page URL."""
        parser = ListingPageParser(self.SAMPLE_HTML, "https://www.adb.org/projects")
        next_url = parser.get_next_page_url()
        
        assert next_url == "https://www.adb.org/projects?page=2"
    
    def test_has_more_pages(self):
        """Test checking for more pages."""
        parser = ListingPageParser(self.SAMPLE_HTML, "https://www.adb.org/projects")
        
        assert parser.has_more_pages() is True
    
    def test_empty_page(self):
        """Test parsing empty page."""
        empty_html = "<html><body><div class='view-content'></div></body></html>"
        parser = ListingPageParser(empty_html, "https://www.adb.org/projects")
        projects = parser.parse()
        
        assert len(projects) == 0


class TestDetailPageParser:
    """Tests for DetailPageParser."""
    
    SAMPLE_DETAIL_HTML = """
    <html>
    <body>
        <h1 class="page-title">Railway Modernization Project</h1>
        <div class="field-body">
            <p>This project aims to modernize the railway infrastructure.</p>
        </div>
        <div class="field-status">Active</div>
        <div class="field-country">India</div>
        <div class="field-sector">Transport</div>
        <div class="field-financing">USD 500 million</div>
        <div class="field-borrower">Government of India</div>
        <table class="project-details">
            <tr><td>Project Number</td><td>55220-001</td></tr>
            <tr><td>Approval Date</td><td>15 May 2023</td></tr>
        </table>
        <div class="field-documents">
            <a href="/documents/project-summary.pdf">Project Summary</a>
        </div>
    </body>
    </html>
    """
    
    def test_parse_detail_page(self):
        """Test parsing detail page."""
        parser = DetailPageParser(
            self.SAMPLE_DETAIL_HTML,
            "https://www.adb.org/projects/55220-001"
        )
        detail = parser.parse()
        
        assert detail.title == "Railway Modernization Project"
        assert "modernize" in detail.description.lower()
        assert detail.status == "Active"
    
    def test_parse_with_listing(self):
        """Test parsing with pre-existing listing data."""
        listing = ProjectListing(
            project_id="55220-001",
            title="Railway Project",
            detail_url="https://www.adb.org/projects/55220-001",
            region="South Asia"
        )
        
        parser = DetailPageParser(
            self.SAMPLE_DETAIL_HTML,
            "https://www.adb.org/projects/55220-001",
            listing
        )
        detail = parser.parse()
        
        # Should use full title from detail page
        assert detail.title == "Railway Modernization Project"
        # Should keep region from listing
        assert detail.region == "South Asia"


# =============================================================================
# Test Retry Decorator
# =============================================================================

class TestRetryDecorator:
    """Tests for retry_with_backoff decorator."""
    
    def test_successful_call(self):
        """Test function that succeeds on first call."""
        call_count = 0
        
        @retry_with_backoff(max_retries=3, base_delay=0.01)
        def successful_func():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = successful_func()
        
        assert result == "success"
        assert call_count == 1
    
    def test_retry_on_failure(self):
        """Test function that fails then succeeds."""
        call_count = 0
        
        @retry_with_backoff(max_retries=3, base_delay=0.01, exceptions=(ValueError,))
        def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary error")
            return "success"
        
        result = flaky_func()
        
        assert result == "success"
        assert call_count == 3
    
    def test_max_retries_exceeded(self):
        """Test function that always fails."""
        @retry_with_backoff(max_retries=2, base_delay=0.01, exceptions=(ValueError,))
        def failing_func():
            raise ValueError("Always fails")
        
        with pytest.raises(ValueError):
            failing_func()


# =============================================================================
# Run tests if executed directly
# =============================================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
