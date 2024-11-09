import sys
import os
import json
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

# Add the project root directory to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.append(project_root)

# Now imports from app should work
from app.web_scraper.spiders.web_spider import WebSpider  # Import the combined spider

def main():
    if len(sys.argv) < 2:
        print("No arguments provided.")
        sys.exit(1)

    # Parse the JSON-encoded request data
    request_data = json.loads(sys.argv[1])
    crawl_id = request_data.get('crawl_id')

    # Initialize the crawler process
    process = CrawlerProcess(get_project_settings())

    # Run the CombinedSpider based on the request data
    if 'start_urls' in request_data:
        process.crawl(
            WebSpider,
            crawl_id=crawl_id,
            start_urls=request_data['start_urls'],
            max_links=request_data.get('max_links', 100),
            follow_external=request_data.get('follow_external', False),
            depth_limit=request_data.get('depth_limit', 1),
            delay=request_data.get('delay', 0.1),
            concurrent_requests=request_data.get('concurrent_requests', 12),
            only_child_pages=request_data.get('only_child_pages', False),
            results=[]
        )
    else:
        print("Invalid request data.")
        sys.exit(1)

    # Start the crawling process
    process.start()

if __name__ == "__main__":
    main()
