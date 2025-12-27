#!/usr/bin/env python
"""
Interactive ADB Scraper - Bypass Cloudflare Manually

This script opens a visible browser. When Cloudflare challenges appear,
YOU solve them (click the checkbox), then the scraper takes over automatically.

Usage:
    python scrape_interactive.py                    # Scrape 5 pages
    python scrape_interactive.py 10                 # Scrape 10 pages  
    python scrape_interactive.py 5 --details        # Include detail pages
    python scrape_interactive.py 5 -o output.json   # Custom output file
"""

import argparse
import sys

def main():
    parser = argparse.ArgumentParser(
        description='Interactive ADB scraper - solve Cloudflare manually, then auto-scrape',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
How it works:
  1. A browser window opens
  2. If Cloudflare challenge appears, YOU solve it (click "I am human")
  3. Once through, the scraper automatically extracts project data
  4. Results are saved to JSON file

Example:
  python scrape_interactive.py 5 -o projects.json
        """
    )
    
    parser.add_argument(
        'pages',
        type=int,
        nargs='?',
        default=5,
        help='Number of pages to scrape (default: 5)'
    )
    
    parser.add_argument(
        '--details', '-d',
        action='store_true',
        help='Also fetch detail pages for each project (slower)'
    )
    
    parser.add_argument(
        '--output', '-o',
        type=str,
        default='projects.json',
        help='Output file path (default: projects.json)'
    )
    
    args = parser.parse_args()
    
    print("="*60)
    print("🚀 ADB INTERACTIVE SCRAPER")
    print("="*60)
    print(f"Pages to scrape: {args.pages}")
    print(f"Include details: {args.details}")
    print(f"Output file: {args.output}")
    print("="*60)
    print()
    print("⚠️  A browser window will open.")
    print("⚠️  If you see a Cloudflare challenge, SOLVE IT MANUALLY.")
    print("⚠️  The scraper will continue automatically once you're through.")
    print()
    
    input("Press ENTER to start...")
    
    from adb_scraper.interactive import InteractiveScraper
    
    scraper = InteractiveScraper(delay=2.0)
    projects = scraper.scrape(
        max_pages=args.pages,
        include_details=args.details,
        output_file=args.output
    )
    
    print()
    print("="*60)
    print(f"✅ COMPLETE: Scraped {len(projects)} projects")
    print(f"📁 Results saved to: {args.output}")
    print("="*60)


if __name__ == '__main__':
    main()
