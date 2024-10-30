import scrapy
from app.database import SessionLocal
from app.schemas import WebsiteDataCreate
from app import cruds, schemas
import pickle
from scrapy import signals
import logging
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup

class WebSpider(scrapy.Spider):
    name = 'web_spider'

    def __init__(self, crawl_id=None, start_urls=None, max_links=10, follow_external=False, depth_limit=2, concurrent_requests=16, *args, **kwargs):
        super(WebSpider, self).__init__(*args, **kwargs)
        self.crawl_id = crawl_id
        self.max_links = int(max_links)
        self.visited_links = set()
        self.pending_urls = list(start_urls) if start_urls else []
        self.link_count = 0
        self.follow_external = follow_external
        self.depth_limit = int(depth_limit)
        self.concurrent_requests = int(concurrent_requests)

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

    def start_requests(self):
        # Ensure base_netloc is set from the first start_url domain
        self.base_netloc = urlparse(self.pending_urls[0]).netloc if self.pending_urls else None

        # Start from the remaining pending URLs
        for url in self.pending_urls:
            if self.link_count < self.max_links and self.should_continue:
                yield scrapy.Request(url, callback=self.parse)

    def parse(self, response):
        if self.link_count >= self.max_links:
            self.logger.info(f"Max links ({self.max_links}) reached. Stopping crawler.")
            self.crawler.engine.close_spider(self, 'finished')
            return

        with SessionLocal() as db:
            if response.url not in self.visited_links:
                self.visited_links.add(response.url)
                
                # Extract and save page data
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
                        
                        # Only follow URLs with HTTP or HTTPS schemes and obey follow_external setting
                        if next_page_url.startswith(("http://", "https://")):
                            if next_page_url not in self.visited_links and next_page_url not in self.pending_urls:
                                if self.follow_external or next_page_netloc == self.base_netloc:
                                    self.pending_urls.append(next_page_url)
                                    yield scrapy.Request(next_page_url, callback=self.parse)
                                else:
                                    print("false ",next_page_netloc,self.base_netloc)

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