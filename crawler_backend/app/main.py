# app/main.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
import json
import os
import sys
from typing import List
from uuid import uuid4

app = FastAPI()

class ScrapyRequest(BaseModel):
    start_urls: list
    max_links: int = 10
    follow_external: bool = False
    depth_limit: int = 2
    concurrent_requests: int = 16

class UrlAndId(BaseModel):
    url: str
    id: int

class CrawlContentRequest(BaseModel):
    urls_and_ids: List[UrlAndId]
    delay: float = 0.0  # Delay in seconds between concurrent runs

@app.post("/crawl-url/")
def crawl_url(scrapy_request: ScrapyRequest):
    # Generate a unique identifier for this crawl session
    crawl_id = str(uuid4())
    
    # Serialize the request data to a JSON string
    request_data = json.dumps({
        "crawl_id": crawl_id,
        "start_urls": scrapy_request.start_urls,
        "max_links": scrapy_request.max_links,
        "follow_external": scrapy_request.follow_external,
        "depth_limit": scrapy_request.depth_limit,
        "concurrent_requests": scrapy_request.concurrent_requests
    })

    # Path to run_crawler.py
    script_dir = os.path.dirname(os.path.realpath(__file__))
    script_path = os.path.join(script_dir, 'run_crawler.py')

    # Use sys.executable to ensure the correct Python interpreter is used
    subprocess.Popen([sys.executable, script_path, request_data], cwd=script_dir)

    return {"message": "Crawling started", "crawl_id": crawl_id}

@app.post("/crawl-content/")
def crawl_content(crawl_request: CrawlContentRequest):
    # Generate a unique identifier for this crawl session
    crawl_id = str(uuid4())

    # Serialize the request data to a JSON string
    request_data = json.dumps({
        "crawl_id": crawl_id,
        "urls_and_ids": [item.dict() for item in crawl_request.urls_and_ids],
        "delay": crawl_request.delay
    })

    # Get the absolute path to run_crawler.py
    script_dir = os.path.dirname(os.path.realpath(__file__))
    script_path = os.path.join(script_dir, 'run_crawler.py')  # <-- Update here

    # Use sys.executable to ensure the correct Python interpreter is used
    subprocess.Popen([sys.executable, script_path, request_data], cwd=script_dir)

    return {"message": "Content crawling started", "crawl_id": crawl_id}

