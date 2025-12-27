# ADB Projects Web Scraper

A robust Python web scraper for extracting project data from the Asian Development Bank (ADB) projects website.

## Features

- **Comprehensive data extraction** from listing and detail pages
- **Pagination handling** with configurable page limits
- **Error resilience** with retry logic and exponential backoff
- **Rate limiting** to respect server resources
- **Structured output** in JSON format
- **Proxy support** for enhanced reliability

## Installation

```bash
cd "e:\Web Scrapping"
pip install -r requirements.txt
```

## Usage

### Basic Usage

```python
from adb_scraper import ADBProjectScraper

# Create scraper instance
scraper = ADBProjectScraper()

# Scrape projects (returns generator)
for project in scraper.scrape_projects(max_pages=5):
    print(f"Project: {project.title}")
    print(f"Country: {project.country}")
    print(f"Status: {project.status}")
```

### Command Line

```bash
# Scrape first 5 pages and save to JSON
python main.py --pages 5 --output projects.json

# Include detail page data (slower but more comprehensive)
python main.py --pages 2 --include-details --output projects_detailed.json

# Use custom delay between requests
python main.py --pages 5 --delay 2.0 --output projects.json
```

### Export Options

```bash
# JSON output
python main.py --pages 5 --output projects.json

# CSV output
python main.py --pages 5 --output projects.csv --format csv
```

## Configuration

Create a `.env` file for optional configuration:

```env
# Request settings
REQUEST_TIMEOUT=30
REQUEST_DELAY=1.5
MAX_RETRIES=3

# Proxy settings (optional)
HTTP_PROXY=http://proxy:port
HTTPS_PROXY=https://proxy:port

# User agent rotation
ROTATE_USER_AGENT=true
```

## Cloudflare Protection

The ADB website uses **advanced Cloudflare protection**. This scraper includes multiple bypass strategies:

### Bypass Strategies

| Strategy | Speed | Reliability | Resources |
|----------|-------|-------------|-----------|
| `cloudscraper` | Fast | Medium | Low |
| `playwright` | Slow | High | High |
| `hybrid` (default) | Medium | High | Medium |

### Usage Examples

```bash
# Default hybrid mode (tries cloudscraper, falls back to playwright)
python main.py --pages 1 --output projects.json

# Force playwright with visible browser
python main.py --pages 1 --strategy playwright --output projects.json

# Use cloudscraper only
python main.py --pages 1 --strategy cloudscraper --output projects.json

# Disable bypass, use standard requests
python main.py --pages 1 --no-bypass --output projects.json
```

### If All Bypass Strategies Fail

If Cloudflare blocks all automated attempts, consider these alternatives:

1. **Use a Residential Proxy Service**
   ```bash
   python main.py --proxy http://user:pass@residential-proxy:port --output projects.json
   ```

2. **Use ADB's Official Data API**
   The ADB provides official data exports at [data.adb.org](https://data.adb.org):
   - CSV/XLSX downloads available
   - SDMX API for structured access
   - No Cloudflare protection

3. **Manual Cookie Injection**
   - Access the site manually in a browser
   - Extract `cf_clearance` cookie
   - Pass to the scraper via session

4. **CAPTCHA Solving Services**
   Integration with 2captcha or anti-captcha services can solve Cloudflare challenges.

## Data Structure

### Project Listing
```json
{
    "project_id": "55220-001",
    "title": "Example Project Title",
    "country": "India",
    "sector": "Transport",
    "status": "Active",
    "approval_date": "2023-05-15",
    "detail_url": "https://www.adb.org/projects/55220-001"
}
```

### Project Detail (with --include-details)
```json
{
    "project_id": "55220-001",
    "title": "Example Project Title",
    "country": "India",
    "sector": "Transport",
    "status": "Active",
    "approval_date": "2023-05-15",
    "detail_url": "https://www.adb.org/projects/55220-001",
    "description": "Full project description...",
    "financing_amount": "USD 500 million",
    "borrower": "Government of India",
    "implementing_agency": "Ministry of Railways",
    "themes": ["Climate Change", "Urban Development"],
    "documents": [...]
}
```

## Error Handling

The scraper handles the following edge cases:
- **Missing fields**: Returns `None` for optional fields
- **Network failures**: Retries with exponential backoff
- **Rate limiting**: Detects 429 responses and waits
- **Invalid HTML**: Logs warning and continues
- **Pagination end**: Detects empty results automatically

## License

MIT License
