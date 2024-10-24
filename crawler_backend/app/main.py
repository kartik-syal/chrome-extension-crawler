# app/main.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from scrapy.utils.project import get_project_settings
from pydantic import BaseModel
from concurrent.futures import ThreadPoolExecutor
from scrapy.crawler import CrawlerProcess
from .web_scraper.spiders.web_spider import UrlSpider, ContentSpider
import time

app = FastAPI()

class ScrapyRequest(BaseModel):
    start_urls: list
    max_links: int = 10
    follow_external: bool = False
    depth_limit: int = 2
    concurrent_requests: int = 16

from typing import List

process = CrawlerProcess(get_project_settings())

class UrlAndId(BaseModel):
    url: str
    id: int

class CrawlContentRequest(BaseModel):
    urls_and_ids: List[UrlAndId]
    delay: float = 0.0  # Delay in seconds between concurrent runs


@app.post("/crawl-url/")
async def crawl_url(scrapy_request: ScrapyRequest):
    results = []  # List to store results from the spider

    process.crawl(UrlSpider,
                   start_urls=scrapy_request.start_urls,
                   max_links=scrapy_request.max_links,
                   follow_external=scrapy_request.follow_external,
                   depth_limit=scrapy_request.depth_limit,
                   concurrent_requests=scrapy_request.concurrent_requests,
                   results=results)

    process.start()  # The script will block here until the crawling is finished

    return {"message": "Crawling completed", "results": results}

@app.post("/crawl-content/")
def crawl_content(crawl_request: CrawlContentRequest):
    results = []  # List to store results from the spider
    urls = [item.url for item in crawl_request.urls_and_ids]
    ids = [item.id for item in crawl_request.urls_and_ids]
    

    def run_spider(url, id, delay):
        process.crawl(ContentSpider, url=url, id=id, results=results)
        process.start()  # This blocks until the crawling is finished
        time.sleep(delay)  # Adding delay before starting the crawl

    with ThreadPoolExecutor() as executor:
        futures = [executor.submit(run_spider, url, id, crawl_request.delay) for url, id in zip(urls, ids)]

    # Wait for all threads to complete
    for future in futures:
        future.result()

    return {"message": "Content crawling completed", "results": results}
