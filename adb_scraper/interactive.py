"""
Interactive scraper mode for bypassing Cloudflare.

This module provides an interactive mode where the user manually solves
the Cloudflare challenge in a visible browser, then the scraper takes over.
"""

import time
import json
from pathlib import Path
from typing import List, Optional

from .models import ProjectListing, ProjectDetail, serialize_projects
from .parsers import ListingPageParser, DetailPageParser, BASE_URL
from .utils import logger, clean_text, extract_project_id


class InteractiveScraper:
    """Interactive scraper that lets users solve Cloudflare manually.
    
    This opens a visible browser, waits for the user to solve any challenges,
    then automatically scrapes once the page is accessible.
    """
    
    def __init__(self, delay: float = 2.0):
        self.delay = delay
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
    
    def _init_browser(self):
        """Initialize the browser."""
        from playwright.sync_api import sync_playwright
        
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(
            headless=False,  # Always visible
            slow_mo=50,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--start-maximized',
            ]
        )
        self._context = self._browser.new_context(
            viewport={'width': 1400, 'height': 900},
            locale='en-US',
        )
        self._page = self._context.new_page()
        logger.info("Browser initialized - you will need to solve any Cloudflare challenges manually")
    
    def _wait_for_cloudflare(self, timeout: int = 120):
        """Wait for user to solve Cloudflare challenge.
        
        Args:
            timeout: Maximum seconds to wait
        """
        print("\n" + "="*60)
        print("🔒 CLOUDFLARE CHALLENGE DETECTED")
        print("="*60)
        print("Please solve the challenge in the browser window.")
        print("The scraper will continue automatically once you're through.")
        print(f"Timeout: {timeout} seconds")
        print("="*60 + "\n")
        
        start = time.time()
        while time.time() - start < timeout:
            content = self._page.content()
            
            # Check if we're past Cloudflare
            if 'Just a moment' not in content and 'Checking your browser' not in content:
                # Verify we're on the actual page
                if 'projects' in self._page.url.lower() or 'adb.org' in self._page.url:
                    print("✅ Cloudflare challenge solved! Continuing with scrape...")
                    logger.info("Cloudflare challenge solved by user")
                    return True
            
            time.sleep(1)
        
        print("❌ Timeout waiting for Cloudflare challenge to be solved")
        return False
    
    def _is_cloudflare_page(self) -> bool:
        """Check if current page is a Cloudflare challenge."""
        content = self._page.content()
        return 'Just a moment' in content or 'Checking your browser' in content
    
    def _parse_current_listing_page(self) -> tuple[List[ProjectListing], Optional[str]]:
        """Parse the current page for project listings."""
        html = self._page.content()
        url = self._page.url
        
        parser = ListingPageParser(html, url)
        projects = parser.parse()
        next_url = parser.get_next_page_url()
        
        return projects, next_url
    
    def _parse_detail_page(self, listing: ProjectListing) -> ProjectDetail:
        """Navigate to and parse a detail page."""
        self._page.goto(listing.detail_url, wait_until='domcontentloaded')
        self._page.wait_for_timeout(2000)
        
        # Check for Cloudflare on detail page
        if self._is_cloudflare_page():
            self._wait_for_cloudflare()
        
        html = self._page.content()
        parser = DetailPageParser(html, listing.detail_url, listing)
        return parser.parse()
    
    def scrape(
        self,
        max_pages: int = 5,
        include_details: bool = False,
        output_file: str = "projects.json"
    ) -> List:
        """Run the interactive scrape.
        
        Args:
            max_pages: Maximum listing pages to scrape
            include_details: Whether to fetch detail pages
            output_file: Where to save results
        
        Returns:
            List of scraped projects
        """
        self._init_browser()
        
        all_projects = []
        
        try:
            # Navigate to projects page
            print(f"\n🌐 Navigating to {BASE_URL}/projects ...")
            self._page.goto(f"{BASE_URL}/projects", wait_until='domcontentloaded')
            self._page.wait_for_timeout(3000)
            
            # Handle Cloudflare if present
            if self._is_cloudflare_page():
                if not self._wait_for_cloudflare():
                    return all_projects
            
            pages_scraped = 0
            
            while pages_scraped < max_pages:
                print(f"\n📄 Scraping page {pages_scraped + 1}/{max_pages}...")
                
                # Wait for page to load
                self._page.wait_for_timeout(2000)
                
                # Parse current page
                projects, next_url = self._parse_current_listing_page()
                
                if not projects:
                    print("No more projects found.")
                    break
                
                print(f"   Found {len(projects)} projects on this page")
                
                # Optionally fetch details
                for i, project in enumerate(projects):
                    if include_details:
                        print(f"   [{i+1}/{len(projects)}] Fetching details for: {project.title[:40]}...")
                        try:
                            detail = self._parse_detail_page(project)
                            all_projects.append(detail)
                            time.sleep(self.delay)
                        except Exception as e:
                            logger.warning(f"Failed to get details: {e}")
                            all_projects.append(project)
                    else:
                        all_projects.append(project)
                        print(f"   [{i+1}/{len(projects)}] {project.project_id}: {project.title[:50]}")
                
                pages_scraped += 1
                
                # Navigate to next page if available
                if next_url and pages_scraped < max_pages:
                    print(f"\n➡️ Going to next page: {next_url}")
                    self._page.goto(next_url, wait_until='domcontentloaded')
                    
                    # Check for Cloudflare
                    if self._is_cloudflare_page():
                        if not self._wait_for_cloudflare():
                            break
                else:
                    break
            
            # Save results
            if all_projects:
                output_path = Path(output_file)
                output = serialize_projects(all_projects, 'json')
                output_path.write_text(output, encoding='utf-8')
                print(f"\n✅ Saved {len(all_projects)} projects to {output_file}")
            
            return all_projects
            
        finally:
            print("\n🔄 Closing browser...")
            self.close()
    
    def close(self):
        """Close the browser."""
        if self._page:
            self._page.close()
        if self._context:
            self._context.close()
        if self._browser:
            self._browser.close()
        if self._playwright:
            self._playwright.stop()


def run_interactive(max_pages: int = 5, include_details: bool = False, output: str = "projects.json"):
    """Convenience function to run interactive scraper.
    
    Usage:
        python -c "from adb_scraper.interactive import run_interactive; run_interactive(5)"
    """
    scraper = InteractiveScraper()
    return scraper.scrape(max_pages, include_details, output)


if __name__ == "__main__":
    import sys
    
    pages = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    output = sys.argv[2] if len(sys.argv) > 2 else "projects.json"
    
    run_interactive(pages, output_file=output)
