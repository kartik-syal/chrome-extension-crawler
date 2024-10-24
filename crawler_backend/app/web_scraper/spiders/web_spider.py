import scrapy
from app.database import SessionLocal  # Import the session local
from app.schemas import WebsiteDataCreate  # Import the schema for creating website data
from app import cruds

class UrlSpider(scrapy.Spider):
    name = 'url_spider'

    def __init__(self, start_urls=None, max_links=10, follow_external=False, depth_limit=2, concurrent_requests=16, results = [], *args, **kwargs):
        super(UrlSpider, self).__init__(*args, **kwargs)
        self.start_urls = start_urls if start_urls else []  # Set start URLs
        self.max_links = int(max_links)  # Convert to integer
        self.follow_external = follow_external  # Convert to boolean
        self.depth_limit = int(depth_limit)  # Set depth limit
        self.concurrent_requests = int(concurrent_requests)  # Set concurrent requests
        self.visited_links = set()  # Track visited links
        self.link_count = 0  # Count of links followed
        self.results = results  # To store URLs and IDs
    
        # Set custom settings
        self.custom_settings = {
            'DEPTH_LIMIT': int(depth_limit),  # Set the crawl depth
            'CONCURRENT_REQUESTS': int(concurrent_requests),  # Set the number of concurrent requests
        }

    def parse(self, response):
        # Iterate over all found links and save them
        for next_page in response.css('a::attr(href)'):
            link = response.urljoin(next_page.get())

            if link not in self.visited_links and self.link_count < self.max_links:
                self.visited_links.add(link)
                self.link_count += 1

                # Save the URL in the database without content
                db = SessionLocal()
                website_data = WebsiteDataCreate(
                    website_url=link,
                    status=False  # Indicate this is pending crawling for content
                )
                try:
                    created_data = cruds.create_website_data(db=db, website_data=website_data)
                    self.logger.info(f"Saved URL: {link} with ID: {created_data.id}")
                    # Store the found link and its ID
                    self.results.append({
                        'url': link,
                        'id': created_data.id
                    })
                except Exception as e:
                    self.logger.error(f"Error saving URL to database: {e}")
                finally:
                    db.close()

                # Follow the next link if needed
                if self.follow_external or response.url in link:
                    yield response.follow(next_page, self.parse)

        # Return all found URLs and IDs once parsing is complete
        if self.link_count >= self.max_links or not response.css('a::attr(href)'):
            yield {
                'urls_and_ids': self.results
            }


class ContentSpider(scrapy.Spider):
    name = 'content_spider'
    
    def __init__(self, url=None, id=None, results = [], *args, **kwargs):
        super(ContentSpider, self).__init__(*args, **kwargs)
        self.url_to_crawl = url
        self.id = id
        self.results = results

    def start_requests(self):
        if self.url_to_crawl and self.id:
            yield scrapy.Request(url=self.url_to_crawl, callback=self.parse)
        else:
            self.logger.error("URL or ID missing. Cannot proceed with crawling.")

    def parse(self, response):
        # Extract the title and content
        title = response.css('title::text').get()
        body_text = response.css('body *::text').getall()
        body_text = ' '.join(body_text).strip()
        html_content = response.text
        
        db = SessionLocal()
        # Update the database with the crawled content
        try:
            cruds.update_website_data(
                db=db,
                id=self.id,  # Update the specific record using its ID
                title=title,
                text=body_text,
                html=html_content,
                status=True  # Mark the status as completed
            )
            self.logger.info(f"Successfully updated record ID: {self.id} with content from {response.url}")
        except Exception as e:
            self.logger.error(f"Error updating database: {e}")
        finally:
            db.close()
        
        self.results.append({'id': self.id, 'content': body_text})  # Store the result
        yield {'id': self.id, 'content': body_text}