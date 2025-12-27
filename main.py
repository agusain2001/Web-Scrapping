#!/usr/bin/env python
"""
ADB Projects Scraper - Command Line Interface

This script provides a command-line interface for scraping project
data from the Asian Development Bank website.

Usage:
    python main.py --pages 5 --output projects.json
    python main.py --pages 2 --include-details --output detailed.json
    python main.py --project-id 55220-001 --output project.json
"""

import argparse
import json
import sys
from pathlib import Path

from adb_scraper import ADBProjectScraper, ProjectListing, ProjectDetail
from adb_scraper.models import serialize_projects
from adb_scraper.utils import logger, setup_logger
from adb_scraper.exceptions import ScraperError


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Scrape project data from the ADB website.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Scrape first 5 pages of listings
  python main.py --pages 5 --output projects.json
  
  # Scrape with detail pages
  python main.py --pages 2 --include-details --output detailed.json
  
  # Scrape a specific project
  python main.py --project-id 55220-001 --output project.json
  
  # Output as CSV
  python main.py --pages 5 --format csv --output projects.csv
        """
    )
    
    # Scraping options
    parser.add_argument(
        '--pages', '-p',
        type=int,
        default=1,
        help='Maximum number of listing pages to scrape (default: 1)'
    )
    
    parser.add_argument(
        '--include-details', '-d',
        action='store_true',
        help='Fetch detail pages for each project (slower)'
    )
    
    parser.add_argument(
        '--project-id',
        type=str,
        help='Scrape a single project by ID (e.g., 55220-001)'
    )
    
    parser.add_argument(
        '--start-page',
        type=int,
        default=1,
        help='Starting page number (default: 1)'
    )
    
    # Output options
    parser.add_argument(
        '--output', '-o',
        type=str,
        default='projects.json',
        help='Output file path (default: projects.json)'
    )
    
    parser.add_argument(
        '--format', '-f',
        type=str,
        choices=['json', 'csv'],
        default='json',
        help='Output format (default: json)'
    )
    
    # Request options
    parser.add_argument(
        '--delay',
        type=float,
        default=1.5,
        help='Minimum delay between requests in seconds (default: 1.5)'
    )
    
    parser.add_argument(
        '--timeout',
        type=int,
        default=30,
        help='Request timeout in seconds (default: 30)'
    )
    
    parser.add_argument(
        '--proxy',
        type=str,
        help='Proxy URL (e.g., http://host:port)'
    )
    
    parser.add_argument(
        '--retries',
        type=int,
        default=3,
        help='Maximum retry attempts (default: 3)'
    )
    
    # Other options
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose logging'
    )
    
    parser.add_argument(
        '--quiet', '-q',
        action='store_true',
        help='Suppress all output except errors'
    )
    
    # Cloudflare bypass options
    parser.add_argument(
        '--no-bypass',
        action='store_true',
        help='Disable Cloudflare bypass (use standard requests only)'
    )
    
    parser.add_argument(
        '--strategy',
        type=str,
        choices=['hybrid', 'cloudscraper', 'playwright'],
        default='hybrid',
        help='Cloudflare bypass strategy: hybrid (recommended), cloudscraper, or playwright'
    )
    
    parser.add_argument(
        '--visible-browser',
        action='store_true',
        default=True,
        help='Use visible browser for Playwright (harder to detect, default: True)'
    )
    
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()
    
    # Configure logging
    import logging
    if args.quiet:
        setup_logger(level=logging.ERROR)
    elif args.verbose:
        setup_logger(level=logging.DEBUG)
    else:
        setup_logger(level=logging.INFO)
    
    # Create scraper
    scraper = ADBProjectScraper(
        request_delay=args.delay,
        timeout=args.timeout,
        max_retries=args.retries,
        proxy=args.proxy,
        bypass_cloudflare=not args.no_bypass,
        fetch_strategy=args.strategy,
    )
    
    try:
        projects = []
        
        if args.project_id:
            # Scrape single project
            logger.info(f"Scraping project: {args.project_id}")
            project = scraper.scrape_single_project(args.project_id)
            
            if project:
                projects = [project]
                logger.info(f"Successfully scraped project: {project.title}")
            else:
                logger.error(f"Could not find project: {args.project_id}")
                sys.exit(1)
        else:
            # Scrape listing pages
            logger.info(f"Starting scrape: max_pages={args.pages}, include_details={args.include_details}")
            
            for project in scraper.scrape_projects(
                max_pages=args.pages,
                include_details=args.include_details,
                start_page=args.start_page,
            ):
                projects.append(project)
                
                if not args.quiet:
                    project_type = type(project).__name__
                    print(f"[{len(projects)}] {project.project_id}: {project.title[:50]}...")
        
        # Output results
        if projects:
            output_path = Path(args.output)
            
            # Serialize based on format
            if args.format == 'csv':
                output = serialize_projects(projects, 'csv')
            else:
                output = serialize_projects(projects, 'json')
            
            # Write to file
            output_path.write_text(output, encoding='utf-8')
            logger.info(f"Saved {len(projects)} projects to {output_path}")
            
            # Print stats
            stats = scraper.get_stats()
            logger.info(f"Stats: {stats}")
        else:
            logger.warning("No projects were scraped")
            
    except KeyboardInterrupt:
        logger.info("Scraping interrupted by user")
        sys.exit(130)
    except ScraperError as e:
        logger.error(f"Scraping error: {e}")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        sys.exit(1)
    finally:
        scraper.close()


if __name__ == '__main__':
    main()
