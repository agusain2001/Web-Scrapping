"""
HTML Parsers for ADB Projects pages.

This module contains the parsing logic for extracting project data
from both listing pages and individual project detail pages.
"""

from typing import List, Optional, Dict, Any
from bs4 import BeautifulSoup, Tag
import re

from .models import ProjectListing, ProjectDetail
from .exceptions import ParseError
from .utils import clean_text, extract_project_id, parse_date, parse_amount, logger


# Base URL for constructing absolute URLs
BASE_URL = 'https://www.adb.org'


class ListingPageParser:
    """Parser for the main projects listing page.
    
    Extracts project entries from the listing page, including
    basic information and links to detail pages.
    """
    
    # CSS selectors for listing page elements (these may need adjustment based on actual HTML)
    SELECTORS = {
        'project_container': '.view-content',
        'project_item': '.views-row',
        'project_title': '.views-field-title a, .project-title a, h3 a, h4 a',
        'project_country': '.views-field-field-countries, .country, .field-country',
        'project_sector': '.views-field-field-sectors, .sector, .field-sector',
        'project_status': '.views-field-field-status, .status, .field-status',
        'project_date': '.views-field-field-approval-date, .date, .approval-date',
        'project_type': '.views-field-field-type, .type, .project-type',
        'pagination_next': '.pager-next a, a.pager-next, .next a, a.next, a[rel="next"]',
        'pagination_last': '.pager-last a, a.pager-last, .last a, a.last',
    }
    
    def __init__(self, html: str, url: str = None):
        """Initialize the parser with HTML content.
        
        Args:
            html: HTML content of the listing page
            url: URL of the page (for error reporting)
        """
        self.html = html
        self.url = url
        self.soup = BeautifulSoup(html, 'lxml')
    
    def parse(self) -> List[ProjectListing]:
        """Parse all project entries from the listing page.
        
        Returns:
            List of ProjectListing objects
        
        Raises:
            ParseError: If parsing fails critically
        """
        projects = []
        
        # Try multiple selectors to find project items
        items = self._find_project_items()
        
        if not items:
            logger.warning(f"No project items found on page: {self.url}")
            return projects
        
        for item in items:
            try:
                project = self._parse_project_item(item)
                if project:
                    projects.append(project)
            except Exception as e:
                logger.warning(f"Failed to parse project item: {e}")
                continue
        
        logger.info(f"Parsed {len(projects)} projects from listing page")
        return projects
    
    def _find_project_items(self) -> List[Tag]:
        """Find all project item elements on the page.
        
        Tries multiple selectors to handle different page layouts.
        """
        # Try primary selector
        container = self.soup.select_one(self.SELECTORS['project_container'])
        if container:
            items = container.select(self.SELECTORS['project_item'])
            if items:
                return items
        
        # Try alternative selectors
        alternative_selectors = [
            '.project-item',
            '.project-row',
            'article.project',
            '.search-result',
            'tr.project',
            '.item-list li',
        ]
        
        for selector in alternative_selectors:
            items = self.soup.select(selector)
            if items:
                return items
        
        # Last resort: look for any element with project links
        project_links = self.soup.select('a[href*="/projects/"]')
        if project_links:
            # Return parent elements of project links
            return [link.parent for link in project_links if link.parent]
        
        return []
    
    def _parse_project_item(self, item: Tag) -> Optional[ProjectListing]:
        """Parse a single project item element.
        
        Args:
            item: BeautifulSoup Tag representing a project item
        
        Returns:
            ProjectListing object or None if parsing fails
        """
        # Extract title and URL
        title_link = item.select_one(self.SELECTORS['project_title'])
        
        if not title_link:
            # Try to find any link to a project page
            title_link = item.select_one('a[href*="/projects/"]')
        
        if not title_link:
            return None
        
        title = clean_text(title_link.get_text())
        href = title_link.get('href', '')
        
        # Build absolute URL
        if href.startswith('/'):
            detail_url = f"{BASE_URL}{href}"
        elif href.startswith('http'):
            detail_url = href
        else:
            detail_url = f"{BASE_URL}/projects/{href}"
        
        # Extract project ID from URL
        project_id = extract_project_id(detail_url)
        
        if not title or not project_id:
            return None
        
        # Extract other fields with safe fallbacks
        country = self._extract_field(item, 'project_country')
        sector = self._extract_field(item, 'project_sector')
        status = self._extract_field(item, 'project_status')
        approval_date = self._extract_field(item, 'project_date')
        project_type = self._extract_field(item, 'project_type')
        
        # Parse and normalize date
        if approval_date:
            approval_date = parse_date(approval_date)
        
        return ProjectListing(
            project_id=project_id,
            title=title,
            detail_url=detail_url,
            country=country,
            sector=sector,
            status=status,
            approval_date=approval_date,
            project_type=project_type,
        )
    
    def _extract_field(self, item: Tag, field_name: str) -> Optional[str]:
        """Extract a field value from a project item.
        
        Args:
            item: Project item element
            field_name: Key in SELECTORS dict
        
        Returns:
            Cleaned text value or None
        """
        selector = self.SELECTORS.get(field_name, '')
        if not selector:
            return None
        
        element = item.select_one(selector)
        if element:
            return clean_text(element.get_text())
        
        return None
    
    def get_next_page_url(self) -> Optional[str]:
        """Get the URL of the next page if available.
        
        Returns:
            Absolute URL of the next page or None
        """
        next_link = self.soup.select_one(self.SELECTORS['pagination_next'])
        
        if next_link:
            href = next_link.get('href', '')
            if href.startswith('/'):
                return f"{BASE_URL}{href}"
            elif href.startswith('http'):
                return href
        
        return None
    
    def has_more_pages(self) -> bool:
        """Check if there are more pages to scrape.
        
        Returns:
            True if more pages exist, False otherwise
        """
        return self.get_next_page_url() is not None


class DetailPageParser:
    """Parser for individual project detail pages.
    
    Extracts comprehensive project information including
    financial details, stakeholders, and documents.
    """
    
    # CSS selectors for detail page elements
    SELECTORS = {
        'title': 'h1.page-title, .project-title h1, article h1, h1',
        'description': '.field-body, .project-description, .description, .summary',
        'status': '.field-status, .project-status, [class*="status"]',
        'country': '.field-country, .field-countries, [class*="country"]',
        'sector': '.field-sector, .field-sectors, [class*="sector"]',
        'approval_date': '.field-approval-date, [class*="approval"]',
        'signing_date': '.field-signing-date, [class*="signing"]',
        'closing_date': '.field-closing-date, [class*="closing"]',
        'financing': '.field-financing, .financing-amount, [class*="financing"], [class*="amount"]',
        'borrower': '.field-borrower, [class*="borrower"]',
        'executing_agency': '.field-executing-agency, [class*="executing"]',
        'themes': '.field-themes, [class*="theme"]',
        'documents': '.field-documents a, .documents-list a, .project-documents a',
        'project_info_table': '.project-info table, .details-table, table.project-details',
    }
    
    def __init__(self, html: str, url: str = None, listing: ProjectListing = None):
        """Initialize the parser with HTML content.
        
        Args:
            html: HTML content of the detail page
            url: URL of the page
            listing: Optional ProjectListing to merge data with
        """
        self.html = html
        self.url = url
        self.listing = listing
        self.soup = BeautifulSoup(html, 'lxml')
    
    def parse(self) -> ProjectDetail:
        """Parse the project detail page.
        
        Returns:
            ProjectDetail object with all extracted information
        """
        # Start with listing data if available
        if self.listing:
            project = ProjectDetail.from_listing(self.listing)
        else:
            project_id = extract_project_id(self.url) or 'unknown'
            project = ProjectDetail(
                project_id=project_id,
                title=self._extract_title() or 'Unknown Project',
                detail_url=self.url or '',
            )
        
        # Extract and update all fields
        self._populate_basic_info(project)
        self._populate_dates(project)
        self._populate_financial_info(project)
        self._populate_stakeholders(project)
        self._populate_content(project)
        self._populate_documents(project)
        self._extract_from_table(project)
        
        return project
    
    def _extract_title(self) -> Optional[str]:
        """Extract project title."""
        title_elem = self.soup.select_one(self.SELECTORS['title'])
        return clean_text(title_elem.get_text()) if title_elem else None
    
    def _populate_basic_info(self, project: ProjectDetail) -> None:
        """Populate basic project information."""
        # Title - always prefer detail page title as it's more complete
        detail_title = self._extract_title()
        if detail_title:
            project.title = detail_title
        
        # Status
        if not project.status:
            project.status = self._extract_field('status')
        
        # Country/Countries
        countries = self._extract_multiple('country')
        if countries:
            project.countries = countries
            if not project.country:
                project.country = countries[0]
        
        # Sectors
        sectors = self._extract_multiple('sector')
        if sectors:
            project.sectors = sectors
            if not project.sector:
                project.sector = sectors[0]
        
        # Themes
        themes = self._extract_multiple('themes')
        if themes:
            project.themes = themes
    
    def _populate_dates(self, project: ProjectDetail) -> None:
        """Populate date fields."""
        if not project.approval_date:
            date_str = self._extract_field('approval_date')
            project.approval_date = parse_date(date_str) if date_str else None
        
        signing_date = self._extract_field('signing_date')
        project.signing_date = parse_date(signing_date) if signing_date else None
        
        closing_date = self._extract_field('closing_date')
        project.closing_date = parse_date(closing_date) if closing_date else None
    
    def _populate_financial_info(self, project: ProjectDetail) -> None:
        """Populate financial information."""
        financing = self._extract_field('financing')
        if financing:
            project.financing_amount = parse_amount(financing)
    
    def _populate_stakeholders(self, project: ProjectDetail) -> None:
        """Populate stakeholder information."""
        # Borrower
        borrower = self._extract_field('borrower')
        if borrower:
            project.borrower = borrower
        
        # Executing agency
        executing = self._extract_field('executing_agency')
        if executing:
            project.executing_agency = executing
    
    def _populate_content(self, project: ProjectDetail) -> None:
        """Populate content fields like description."""
        description = self._extract_field('description')
        if description:
            project.description = description
    
    def _populate_documents(self, project: ProjectDetail) -> None:
        """Extract document links."""
        doc_links = self.soup.select(self.SELECTORS['documents'])
        
        documents = []
        for link in doc_links:
            href = link.get('href', '')
            title = clean_text(link.get_text()) or 'Document'
            
            if href:
                if href.startswith('/'):
                    href = f"{BASE_URL}{href}"
                
                documents.append({
                    'title': title,
                    'url': href,
                })
        
        project.documents = documents
    
    def _extract_from_table(self, project: ProjectDetail) -> None:
        """Extract information from project info tables.
        
        Many project pages have key-value tables with project details.
        """
        tables = self.soup.select(self.SELECTORS['project_info_table'])
        
        for table in tables:
            rows = table.select('tr')
            
            for row in rows:
                cells = row.select('td, th')
                if len(cells) >= 2:
                    label = clean_text(cells[0].get_text()) or ''
                    value = clean_text(cells[1].get_text())
                    
                    self._assign_table_value(project, label.lower(), value)
    
    def _assign_table_value(self, project: ProjectDetail, label: str, value: Optional[str]) -> None:
        """Assign a value extracted from a table to the appropriate field."""
        if not value:
            return
        
        label_mapping = {
            'project number': 'project_id',
            'project name': 'title',
            'status': 'status',
            'country': 'country',
            'sector': 'sector',
            'approval date': 'approval_date',
            'signing date': 'signing_date',
            'closing date': 'closing_date',
            'total project cost': 'financing_amount',
            'financing': 'financing_amount',
            'amount': 'financing_amount',
            'borrower': 'borrower',
            'executing agency': 'executing_agency',
            'implementing agency': 'executing_agency',
        }
        
        for pattern, field in label_mapping.items():
            if pattern in label:
                current_value = getattr(project, field, None)
                if not current_value:
                    # Special handling for dates
                    if 'date' in field:
                        value = parse_date(value)
                    setattr(project, field, value)
                break
    
    def _extract_field(self, field_name: str) -> Optional[str]:
        """Extract a single field value."""
        selector = self.SELECTORS.get(field_name, '')
        if not selector:
            return None
        
        element = self.soup.select_one(selector)
        return clean_text(element.get_text()) if element else None
    
    def _extract_multiple(self, field_name: str) -> List[str]:
        """Extract multiple values for a field."""
        selector = self.SELECTORS.get(field_name, '')
        if not selector:
            return []
        
        elements = self.soup.select(selector)
        values = []
        
        for elem in elements:
            # Check for list items inside
            items = elem.select('li, .item, span')
            if items:
                for item in items:
                    text = clean_text(item.get_text())
                    if text and text not in values:
                        values.append(text)
            else:
                text = clean_text(elem.get_text())
                if text and text not in values:
                    values.append(text)
        
        return values


def parse_listing_page(html: str, url: str = None) -> tuple[List[ProjectListing], Optional[str]]:
    """Parse a listing page and return projects with next page URL.
    
    This is a convenience function that wraps the ListingPageParser.
    
    Args:
        html: HTML content
        url: Page URL
    
    Returns:
        Tuple of (list of projects, next page URL or None)
    """
    parser = ListingPageParser(html, url)
    projects = parser.parse()
    next_url = parser.get_next_page_url()
    
    return projects, next_url


def parse_detail_page(html: str, url: str = None, listing: ProjectListing = None) -> ProjectDetail:
    """Parse a detail page and return project details.
    
    This is a convenience function that wraps the DetailPageParser.
    
    Args:
        html: HTML content
        url: Page URL
        listing: Optional listing data to merge
    
    Returns:
        ProjectDetail object
    """
    parser = DetailPageParser(html, url, listing)
    return parser.parse()
