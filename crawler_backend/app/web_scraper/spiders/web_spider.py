# crawler_backend/app/web_scraper/spiders/web_spider.py

import scrapy
from app.database import SessionLocal
from app.schemas import WebsiteDataCreate
from app import cruds, schemas
import json
import pickle

class UrlSpider(scrapy.Spider):
    name = 'url_spider'

    def __init__(self, crawl_id=None, start_urls=None, max_links=10, *args, **kwargs):
        super(UrlSpider, self).__init__(*args, **kwargs)
        self.crawl_id = crawl_id
        self.max_links = max_links
        self.visited_links = set()
        self.pending_urls = list(start_urls) if start_urls else []
        self.link_count = 0

        # Load state from the database if resuming
        if self.crawl_id:
            db = SessionLocal()
            crawl_session = cruds.get_crawl_session(db, self.crawl_id)
            if crawl_session and crawl_session.status == 'paused':
                self.logger.info(f"Resuming crawl {self.crawl_id}")
                if crawl_session.visited_links:
                    self.visited_links = set(pickle.loads(crawl_session.visited_links))
                if crawl_session.pending_urls:
                    self.pending_urls = pickle.loads(crawl_session.pending_urls)
                self.link_count = crawl_session.link_count or 0
            db.close()

    def start_requests(self):
        for url in self.pending_urls:
            yield scrapy.Request(url, callback=self.parse)

    def parse(self, response):
        db = SessionLocal()

        # Save the current URL if not already visited and within link limits
        if response.url not in self.visited_links and self.link_count < self.max_links:
            self.visited_links.add(response.url)
            self.link_count += 1

            # Save the URL in the database
            website_data = schemas.WebsiteDataCreate(
                website_url=response.url,
                status=False
            )
            try:
                created_data = cruds.create_website_data(db=db, website_data=website_data)
                self.logger.info(f"Saved URL: {response.url} with ID: {created_data.id}")
            except Exception as e:
                self.logger.error(f"Error saving URL to database: {e}")

        db.close()

        # Extract links and add to pending URLs if not visited
        for next_page in response.css('a::attr(href)').getall():
            next_page_url = response.urljoin(next_page)
            if next_page_url not in self.visited_links and next_page_url not in self.pending_urls and self.link_count < self.max_links:
                self.pending_urls.append(next_page_url)
                yield scrapy.Request(next_page_url, callback=self.parse)

        # Save state periodically
        self.save_state()

    def save_state(self):
        # Save the current state to the database
        db = SessionLocal()
        crawl_session_update = schemas.CrawlSessionUpdate(
            visited_links=pickle.dumps(list(self.visited_links)),
            pending_urls=pickle.dumps(self.pending_urls),
            link_count=self.link_count
        )
        cruds.update_crawl_session(db, self.crawl_id, crawl_session_update)
        db.close()

    def closed(self, reason):
        # When the spider is closed, save the state
        self.save_state()
        # Update status in the database
        db = SessionLocal()
        status = 'completed' if reason == 'finished' else 'paused'
        cruds.update_crawl_session(db, self.crawl_id, schemas.CrawlSessionUpdate(status=status))
        db.close()

class ContentSpider(scrapy.Spider):
    name = 'content_spider'

    def __init__(self, crawl_id=None, url=None, id=None, results=[], *args, **kwargs):
        super(ContentSpider, self).__init__(*args, **kwargs)
        self.crawl_id = crawl_id
        self.results = results
        self.pending_requests = []

        # Load state if resuming
        self.visited_ids = set()

        if self.crawl_id:
            db = SessionLocal()
            crawl_session = cruds.get_crawl_session(db, self.crawl_id)
            if crawl_session and crawl_session.status == 'paused':
                self.logger.info(f"Resuming crawl {self.crawl_id}")
                if crawl_session.request_queue:
                    self.pending_requests = pickle.loads(crawl_session.request_queue)
                else:
                    self.pending_requests = []
                if crawl_session.visited_links:
                    self.visited_ids = set(pickle.loads(crawl_session.visited_links))
                else:
                    self.visited_ids = set()
            else:
                # Initialize pending requests from start_urls
                self.pending_requests = [(url, id) for url, id in zip(json.loads(crawl_session.start_urls), [item['id'] for item in kwargs.get('urls_and_ids', [])])]
                self.visited_ids = set()
            db.close()
        else:
            # Handle case where crawl_id is not provided
            self.pending_requests = []
            self.visited_ids = set()

    def start_requests(self):
        for url, id in self.pending_requests:
            if id not in self.visited_ids:
                yield scrapy.Request(url, callback=self.parse, meta={'id': id})

    def parse(self, response):
        id = response.meta['id']
        self.visited_ids.add(id)

        # Extract content as before
        title = response.css('title::text').get()
        body_text = response.css('body *::text').getall()
        body_text = ' '.join(body_text).strip()
        html_content = response.text

        db = SessionLocal()
        try:
            cruds.update_website_data(
                db=db,
                id=id,
                title=title,
                text=body_text,
                html=html_content,
                status=True  # Mark the status as completed
            )
            self.logger.info(f"Successfully updated record ID: {id} with content from {response.url}")
        except Exception as e:
            self.logger.error(f"Error updating database: {e}")
        finally:
            db.close()

        self.results.append({'id': id, 'content': body_text})

        # Save state periodically
        self.save_state()

    def save_state(self):
        # Save the current state to the database
        db = SessionLocal()
        crawl_session_update = schemas.CrawlSessionUpdate(
            request_queue=pickle.dumps(self.pending_requests),
            visited_links=pickle.dumps(list(self.visited_ids))
        )
        cruds.update_crawl_session(db, self.crawl_id, crawl_session_update)
        db.close()

    def closed(self, reason):
        # When the spider is closed, save the state
        self.save_state()
        # Update the status
        db = SessionLocal()
        if reason == 'finished':
            status = 'completed'
        else:
            status = 'stopped'
        cruds.update_crawl_session(db, self.crawl_id, schemas.CrawlSessionUpdate(status=status, pid=None))
        db.close()