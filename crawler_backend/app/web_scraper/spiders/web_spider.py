import scrapy
from app.database import SessionLocal
from app import cruds, schemas
import pickle

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

    def start_requests(self):
        # Start from the remaining pending URLs
        for url in self.pending_urls:
            if self.link_count < self.max_links and self.should_continue:
                yield scrapy.Request(url, callback=self.parse)

    def parse(self, response):
        # Check if the maximum link count has been reached
        if self.link_count >= self.max_links or not self.should_continue:
            self.logger.info("Max link count reached or stopped by user. Saving and stopping.")
            self.should_continue = False  # Stop processing
            self.save_current_state()
            return  # Ensure no further processing if limit reached

        db = SessionLocal()

        # Only process the current URL if it hasn't been visited
        if response.url not in self.visited_links:
            self.visited_links.add(response.url)

            # Extract and process page data
            title = response.css('title::text').get()
            body_text = ' '.join(response.css('body *::text').getall()).strip()
            html_content = response.text

            # Save data in the database only if under the link count limit
            if self.link_count < self.max_links:
                website_data = schemas.WebsiteDataCreate(
                    website_url=response.url,
                    title=title,
                    text=body_text,
                    html=html_content,
                    status=True,  # Mark as completed
                    crawl_session_id=self.crawl_session.id
                )
                try:
                    created_data = cruds.create_website_data(db=db, website_data=website_data)
                    self.link_count += 1  # Increment link count after saving successfully
                    self.logger.info(f"Saved content for URL: {response.url} with ID: {created_data.id}")
                except Exception as e:
                    self.logger.error(f"Error saving content to database: {e}")

                # Extract links and add them to the pending list if not visited
                for next_page in response.css('a::attr(href)').getall():
                    next_page_url = response.urljoin(next_page)

                    # Only add new URLs if we haven't reached the max_links limit
                    if (next_page_url not in self.visited_links and 
                        next_page_url not in self.pending_urls and 
                        self.link_count < self.max_links and 
                        self.should_continue):  # Check max_links before queuing new requests
                        self.pending_urls.append(next_page_url)

                        # Only yield a new request if still under max_links
                        if self.link_count < self.max_links and self.should_continue:
                            yield scrapy.Request(next_page_url, callback=self.parse)

        db.close()

        # Save the current state periodically
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
        status = 'completed' if reason == 'finished' else 'paused'
        cruds.update_crawl_session(db, self.crawl_id, schemas.CrawlSessionUpdate(status=status))
        db.close()
