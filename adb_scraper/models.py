"""
Data models for ADB Project information.

This module defines dataclasses representing the structure of project data
extracted from both listing and detail pages.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime
import json


@dataclass
class ProjectListing:
    """Represents project data extracted from the main listing page.
    
    This contains the basic information visible in the project listing,
    including the URL to fetch more detailed information.
    
    Attributes:
        project_id: Unique project identifier (e.g., "55220-001")
        title: Project name/title
        country: Country or region where the project is located
        sector: Primary sector (e.g., "Transport", "Energy")
        status: Current project status (e.g., "Active", "Closed")
        approval_date: Date when the project was approved
        detail_url: URL to the project's detail page
        project_type: Type of project (e.g., "Loan", "Grant", "Technical Assistance")
        region: Geographic region (e.g., "South Asia", "Southeast Asia")
    """
    
    project_id: str
    title: str
    detail_url: str
    country: Optional[str] = None
    sector: Optional[str] = None
    status: Optional[str] = None
    approval_date: Optional[str] = None
    project_type: Optional[str] = None
    region: Optional[str] = None
    
    def __post_init__(self):
        """Validate and clean data after initialization."""
        # Clean whitespace from string fields
        if self.title:
            self.title = self.title.strip()
        if self.country:
            self.country = self.country.strip()
        if self.sector:
            self.sector = self.sector.strip()
        if self.status:
            self.status = self.status.strip()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2, default=str)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProjectListing':
        """Create instance from dictionary."""
        return cls(
            project_id=data.get('project_id', ''),
            title=data.get('title', ''),
            detail_url=data.get('detail_url', ''),
            country=data.get('country'),
            sector=data.get('sector'),
            status=data.get('status'),
            approval_date=data.get('approval_date'),
            project_type=data.get('project_type'),
            region=data.get('region'),
        )


@dataclass
class ProjectDetail:
    """Represents complete project data from the detail page.
    
    This extends the listing information with additional details
    only available on individual project pages.
    
    Attributes:
        project_id: Unique project identifier
        title: Project name/title
        detail_url: URL of the project detail page
        
        # Location information
        country: Primary country
        countries: List of all countries involved (for regional projects)
        region: Geographic region
        
        # Classification
        sector: Primary sector
        sectors: List of all sectors
        themes: List of project themes/focus areas
        project_type: Type of project
        status: Current project status
        
        # Dates
        approval_date: Date of approval
        signing_date: Date of signing
        effectivity_date: Date when project became effective
        closing_date: Expected or actual closing date
        
        # Financial information
        financing_amount: Total financing amount with currency
        adb_financing: ADB's contribution
        cofinancing: Co-financing amounts
        
        # Stakeholders
        borrower: Borrowing entity
        executing_agency: Main executing agency
        implementing_agencies: List of implementing agencies
        
        # Content
        description: Full project description
        objectives: Project objectives
        expected_outcomes: Expected outcomes/results
        
        # Documents and links
        documents: List of associated documents
        related_links: Related URLs
        
        # Metadata
        last_updated: When the page was last updated
        scraped_at: When this data was scraped
    """
    
    # Required fields
    project_id: str
    title: str
    detail_url: str
    
    # Location information
    country: Optional[str] = None
    countries: List[str] = field(default_factory=list)
    region: Optional[str] = None
    
    # Classification
    sector: Optional[str] = None
    sectors: List[str] = field(default_factory=list)
    themes: List[str] = field(default_factory=list)
    project_type: Optional[str] = None
    status: Optional[str] = None
    
    # Dates
    approval_date: Optional[str] = None
    signing_date: Optional[str] = None
    effectivity_date: Optional[str] = None
    closing_date: Optional[str] = None
    
    # Financial information
    financing_amount: Optional[str] = None
    adb_financing: Optional[str] = None
    cofinancing: Optional[str] = None
    
    # Stakeholders
    borrower: Optional[str] = None
    executing_agency: Optional[str] = None
    implementing_agencies: List[str] = field(default_factory=list)
    
    # Content
    description: Optional[str] = None
    objectives: Optional[str] = None
    expected_outcomes: Optional[str] = None
    
    # Documents and links
    documents: List[Dict[str, str]] = field(default_factory=list)
    related_links: List[str] = field(default_factory=list)
    
    # Metadata
    last_updated: Optional[str] = None
    scraped_at: Optional[str] = field(default_factory=lambda: datetime.now().isoformat())
    
    def __post_init__(self):
        """Validate and clean data after initialization."""
        # Clean whitespace from string fields
        for field_name in ['title', 'country', 'sector', 'status', 'description']:
            value = getattr(self, field_name, None)
            if value and isinstance(value, str):
                setattr(self, field_name, value.strip())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)
    
    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=2, default=str)
    
    @classmethod
    def from_listing(cls, listing: ProjectListing) -> 'ProjectDetail':
        """Create a ProjectDetail instance from a ProjectListing.
        
        This is used when enriching listing data with detail page information.
        """
        return cls(
            project_id=listing.project_id,
            title=listing.title,
            detail_url=listing.detail_url,
            country=listing.country,
            sector=listing.sector,
            status=listing.status,
            approval_date=listing.approval_date,
            project_type=listing.project_type,
            region=listing.region,
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ProjectDetail':
        """Create instance from dictionary."""
        return cls(
            project_id=data.get('project_id', ''),
            title=data.get('title', ''),
            detail_url=data.get('detail_url', ''),
            country=data.get('country'),
            countries=data.get('countries', []),
            region=data.get('region'),
            sector=data.get('sector'),
            sectors=data.get('sectors', []),
            themes=data.get('themes', []),
            project_type=data.get('project_type'),
            status=data.get('status'),
            approval_date=data.get('approval_date'),
            signing_date=data.get('signing_date'),
            effectivity_date=data.get('effectivity_date'),
            closing_date=data.get('closing_date'),
            financing_amount=data.get('financing_amount'),
            adb_financing=data.get('adb_financing'),
            cofinancing=data.get('cofinancing'),
            borrower=data.get('borrower'),
            executing_agency=data.get('executing_agency'),
            implementing_agencies=data.get('implementing_agencies', []),
            description=data.get('description'),
            objectives=data.get('objectives'),
            expected_outcomes=data.get('expected_outcomes'),
            documents=data.get('documents', []),
            related_links=data.get('related_links', []),
            last_updated=data.get('last_updated'),
            scraped_at=data.get('scraped_at'),
        )
    
    def merge_with_listing(self, listing: ProjectListing) -> None:
        """Merge data from a listing, filling in any missing fields."""
        if not self.country and listing.country:
            self.country = listing.country
        if not self.sector and listing.sector:
            self.sector = listing.sector
        if not self.status and listing.status:
            self.status = listing.status
        if not self.approval_date and listing.approval_date:
            self.approval_date = listing.approval_date
        if not self.project_type and listing.project_type:
            self.project_type = listing.project_type
        if not self.region and listing.region:
            self.region = listing.region


def serialize_projects(projects: List[ProjectDetail], format: str = 'json') -> str:
    """Serialize a list of projects to the specified format.
    
    Args:
        projects: List of ProjectDetail objects
        format: Output format ('json' or 'csv')
    
    Returns:
        Serialized string in the specified format
    """
    if format == 'json':
        return json.dumps([p.to_dict() for p in projects], indent=2, default=str)
    elif format == 'csv':
        import csv
        import io
        
        if not projects:
            return ""
        
        output = io.StringIO()
        fieldnames = list(projects[0].to_dict().keys())
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        
        for project in projects:
            row = project.to_dict()
            # Convert lists to comma-separated strings for CSV
            for key, value in row.items():
                if isinstance(value, list):
                    row[key] = '; '.join(str(v) for v in value) if value else ''
            writer.writerow(row)
        
        return output.getvalue()
    else:
        raise ValueError(f"Unsupported format: {format}")
