import scrapy
from app.database import SessionLocal
from app.schemas import WebsiteDataCreate
from app import cruds, schemas
import pickle
from scrapy import signals
import logging
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import os
import re
from scrapy.spiders import CrawlSpider, Rule
from scrapy.linkextractors import LinkExtractor

class WebSpider(CrawlSpider):
    name = 'web_spider'

    def __init__(self, crawl_id=None, start_urls=None, max_links=10, follow_external=False, depth_limit=2,
                 concurrent_requests=16, child_only_pages=False, search_strategy='dfs', *args, **kwargs):
        super(WebSpider, self).__init__(*args, **kwargs)
        self.crawl_id = crawl_id
        self.max_links = int(max_links)
        self.visited_links = set()
        self.pending_urls = list(start_urls) if start_urls else []
        self.link_count = 0
        self.follow_external = follow_external
        self.depth_limit = int(depth_limit)
        self.concurrent_requests = int(concurrent_requests)
        self.child_only_pages = child_only_pages
        self.search_strategy = search_strategy.lower()  # Set the search strategy

        # Set the full base URL to filter by domain and path
        if start_urls:
            print(start_urls[0])
            self.base_url, self.domain = self.remove_extension_from_url(start_urls[0])
            self.base_path = self.base_url
            # Create a regex for the base path
            self.path_regex = self.create_path_regex(self.base_path)

        else:
            self.base_url = None
            self.path_regex = None

        print("basics domain=>", self.domain)
        print("base path =>", self.base_path)
        print(f"path regex =>{self.path_regex}")
        print("self.base_url =>", self.base_url)

        # Custom settings
        self.custom_settings = {
            'DEPTH_LIMIT': self.depth_limit,
            'CONCURRENT_REQUESTS': self.concurrent_requests,
        }

        # Load state if resuming
        if self.crawl_id:
            self.load_state()

        # Flag to control crawling state
        self.should_continue = True

        if self.child_only_pages:
            # Allow all URLs starting with the base path without explicitly including file extensions
            self.rules = (
                Rule(
                    LinkExtractor(allow=(self.path_regex,), allow_domains=self.domain),
                    callback='parse_item',
                    follow=True
                ),
            )
            self._compile_rules()

    def remove_extension_from_url(self, url):
        # Parse the URL
        parsed_url = urlparse(url)
        
        # Split the path and remove the extension
        path_parts = parsed_url.path.rsplit('.', 1)
        if len(path_parts) > 1:
            path_without_extension = path_parts[0]
        else:
            path_without_extension = parsed_url.path

        # Construct the new URL without the extension
        new_url = f"{parsed_url.scheme}://{parsed_url.netloc}{path_without_extension}"
        
        # Return the URL without its extension
        return new_url, parsed_url.netloc

    def load_state(self):
        db = SessionLocal()
        self.crawl_session = cruds.get_crawl_session(db, self.crawl_id)
        if self.crawl_session and self.crawl_session.status == 'paused':
            self.logger.info(f"Resuming crawl {self.crawl_id}")
            if self.crawl_session.visited_links:
                self.visited_links = set(pickle.loads(self.crawl_session.visited_links))
            if self.crawl_session.pending_urls:
                loaded_pending_urls = pickle.loads(self.crawl_session.pending_urls)
                # Filter pending URLs to exclude already visited links
                self.pending_urls = [url for url in loaded_pending_urls if url not in self.visited_links]
            self.link_count = self.crawl_session.link_count or 0
        db.close()

    def extract_text_content(self, response):
        soup = BeautifulSoup(response.body, 'html.parser')

        # Remove script and style elements
        for script in soup(["script", "style", "noscript", "iframe"]):
            script.decompose()

        # Get text and clean it
        text = soup.get_text(separator=' ', strip=True)
        # Remove extra whitespace
        text = ' '.join(text.split())
        return text

    def extract_favicon(self, response):
        # Try common favicon locations
        favicon_urls = [
            response.urljoin('/favicon.ico'),
            response.css('link[rel*="icon"]::attr(href)').get(),
            response.css('link[rel*="shortcut icon"]::attr(href)').get()
        ]

        # Return first valid favicon URL found
        for url in favicon_urls:
            if url:
                return response.urljoin(url)
        return None
    
    def create_path_regex(self, base_url):
        path_regex = rf"^{base_url}"

        return path_regex

    def start_requests(self):
        # Start from the remaining pending URLs
        if self.search_strategy == 'bfs':
            # BFS: Use a queue to manage pending URLs
            self.queue = self.pending_urls.copy()
            self.pending_urls = []  # Clear the list as we will use the queue

            while self.queue:
                url = self.queue.pop(0)  # Get the next URL
                if self.link_count < self.max_links and self.should_continue:
                    if re.match(self.path_regex, url):
                        yield scrapy.Request(url, self.parse)
        elif self.search_strategy == 'dfs':
            # DFS: Use a stack to manage pending URLs
            self.stack = self.pending_urls.copy()
            self.pending_urls = []  # Clear the list as we will use the stack

            while self.stack:
                url = self.stack.pop()  # Get the next URL
                if self.link_count < self.max_links and self.should_continue:
                    if re.match(self.path_regex, url):
                        yield scrapy.Request(url, self.parse)

    def parse(self, response):
        if self.link_count >= self.max_links:
            self.logger.info(f"Max links ({self.max_links}) reached. Stopping crawler.")
            self.crawler.engine.close_spider(self, 'finished')
            return

        with SessionLocal() as db:
            if response.url not in self.visited_links:
                self.visited_links.add(response.url)

                title = response.css('title::text').get()
                body_text = self.extract_text_content(response)
                html_content = response.text
                favicon_url = self.extract_favicon(response)

                if self.link_count < self.max_links:
                    website_data = schemas.WebsiteDataCreate(
                        website_url=response.url,
                        title=title,
                        text=body_text,
                        html=html_content,
                        status=True,
                        crawl_session_id=self.crawl_session.id,
                        favicon_url=favicon_url
                    )
                    try:
                        cruds.create_website_data(db=db, website_data=website_data)
                        self.link_count += 1
                        self.logger.info(f"Saved content for URL: {response.url}. Links processed: {self.link_count}/{self.max_links}")

                        cruds.update_crawl_session(
                            db, 
                            self.crawl_id,
                            schemas.CrawlSessionUpdate(link_count=self.link_count)
                        )

                        if self.link_count >= self.max_links:
                            self.logger.info("Max links reached after saving. Closing spider.")
                            self.crawler.engine.close_spider(self, 'finished')
                            return
                    except Exception as e:
                        self.logger.error(f"Error saving content: {e}")

                if self.link_count < self.max_links:
                    for next_page in response.css('a::attr(href)').getall():
                        next_page_url = response.urljoin(next_page)
                        next_page_netloc = urlparse(next_page_url).netloc

                        # Check if URL is within the allowed base URL
                        if next_page_url.startswith(self.base_url):
                            if self.child_only_pages and not re.match(self.path_regex, next_page_url):
                                self.logger.info(f"Skipping URL due to path restriction: {next_page_url} {re.match(self.path_regex, next_page_url)} {self.child_only_pages}")
                                continue

                            if next_page_url not in self.visited_links and next_page_url not in self.pending_urls:
                                if self.follow_external or next_page_netloc == self.domain:
                                    # Add next page URL to the appropriate collection
                                    if self.search_strategy == 'bfs':
                                        self.queue.append(next_page_url)  # Use queue for BFS
                                    elif self.search_strategy == 'dfs':
                                        self.stack.append(next_page_url)  # Use stack for DFS

                                    yield scrapy.Request(next_page_url, callback=self.parse)
                                else:
                                    print("Skipping external link: ", next_page_netloc)

        self.save_state()

    def save_state(self):
        # Save the current state to the database
        db = SessionLocal()
        crawl_session_update = schemas.CrawlSessionUpdate(
            visited_links=pickle.dumps(list(self.visited_links)),
            pending_urls=pickle.dumps(self.pending_urls),  # Save remaining pending URLs
            link_count=self.link_count
        )
        cruds.update_crawl_session(db, self.crawl_id, crawl_session_update)
        db.close()

    def save_current_state(self):
        self.save_state()
        self.logger.info("Current state saved.")

    def closed(self, reason):
        self.save_state()
        db = SessionLocal()
        # Update status based on reason
        status = 'completed' if reason in ['finished', 'max_links_reached'] else 'paused'
        cruds.update_crawl_session(db, self.crawl_id, schemas.CrawlSessionUpdate(status=status))
        db.close()

logger = logging.getLogger(__name__)

class StopSpiderMiddleware:
    def __init__(self):
        self.crawler = None

    @classmethod
    def from_crawler(cls, crawler):
        obj = cls()
        obj.crawler = crawler
        crawler.signals.connect(obj.spider_opened, signal=signals.spider_opened)
        crawler.signals.connect(obj.spider_closed, signal=signals.spider_closed)
        return obj

    def process_response(self, request, response, spider):
        if hasattr(spider, 'link_count') and hasattr(spider, 'max_links'):
            if spider.link_count >= spider.max_links:
                spider.crawler.engine.close_spider(spider, 'finished')
                return response
        
        if response.status in [403, 404]:
            spider.logger.warning(f"Received {response.status} for URL: {response.url}")
            return response
            
        return response

    def spider_opened(self, spider):
        logger.info(f'Spider opened: {spider.name}')

    def spider_closed(self, spider):
        logger.info(f'Spider closed: {spider.name}')