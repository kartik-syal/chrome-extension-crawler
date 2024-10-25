# app/main.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import subprocess
import json
import pickle
import os
import sys
from typing import List
from uuid import uuid4
from app import cruds, database, schemas
import signal

app = FastAPI()

crawler_processes = {}

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

class CrawlControlRequest(BaseModel):
    crawl_id: str

@app.post("/crawl-url/")
def crawl_url(scrapy_request: ScrapyRequest):
    # Generate a unique identifier for this crawl session
    crawl_id = str(uuid4())
    
    # Create a crawl session in the database
    db = next(database.get_db())
    crawl_session = schemas.CrawlSessionCreate(
        crawl_id=crawl_id,
        spider_name='url_spider',
        crawl_type='url_crawl',  # Add this line
        start_urls=scrapy_request.start_urls,
        max_links=scrapy_request.max_links
    )
    cruds.create_crawl_session(db, crawl_session)
    db.close()
    
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

    # Start the crawler process
    process = subprocess.Popen([sys.executable, script_path, request_data], cwd=script_dir)
    pid = process.pid

    # Update the CrawlSession with the PID
    db = next(database.get_db())
    cruds.update_crawl_session(db, crawl_id, schemas.CrawlSessionUpdate(pid=pid))
    db.close()

    return {"message": "Crawling started", "crawl_id": crawl_id}

@app.post("/pause-crawl/")
def pause_crawl(request: CrawlControlRequest):
    crawl_id = request.crawl_id
    db = next(database.get_db())
    crawl_session = cruds.get_crawl_session(db, crawl_id)
    if crawl_session and crawl_session.pid:
        pid = crawl_session.pid
        try:
            os.kill(pid, signal.SIGTERM)  # Terminate the process
            # Update the crawl session status to 'paused' and clear the PID
            cruds.update_crawl_session(db, crawl_id, schemas.CrawlSessionUpdate(status='paused', pid=None))
            db.close()
            return {"message": f"Crawl {crawl_id} paused"}
        except Exception as e:
            db.close()
            raise HTTPException(status_code=500, detail=str(e))
    else:
        db.close()
        raise HTTPException(status_code=404, detail="Crawl not found or PID not available")


@app.post("/resume-crawl/")
def resume_crawl(request: CrawlControlRequest):
    crawl_id = request.crawl_id

    # Retrieve the session from the database
    db = next(database.get_db())
    crawl_session = cruds.get_crawl_session(db, crawl_id)
    db.close()

    if crawl_session and crawl_session.status == "paused":
        # Load start_urls as JSON
        start_urls = json.loads(crawl_session.start_urls)  # Should work if stored as JSON
        request_data = json.dumps({
            "crawl_id": crawl_id,
            "start_urls": start_urls,
            "max_links": crawl_session.max_links,
            "visited_links": pickle.loads(crawl_session.visited_links),
            "pending_urls": pickle.loads(crawl_session.pending_urls)
        })

        # Start the crawler process
        script_dir = os.path.dirname(os.path.realpath(__file__))
        script_path = os.path.join(script_dir, 'run_crawler.py')
        process = subprocess.Popen([sys.executable, script_path, request_data], cwd=script_dir)
        
        # Update the CrawlSession with the new PID
        pid = process.pid
        db = next(database.get_db())
        cruds.update_crawl_session(db, crawl_id, schemas.CrawlSessionUpdate(pid=pid, status="running"))
        db.close()

        return {"message": f"Crawl {crawl_id} resumed"}
    else:
        raise HTTPException(status_code=404, detail="Crawl session not found or not in paused state")


# crawler_backend/app/main.py

@app.post("/crawl-content/")
def crawl_content(crawl_request: CrawlContentRequest):
    # Generate a unique identifier for this crawl session
    crawl_id = str(uuid4())

    # Extract URLs and IDs
    urls_and_ids = [item.dict() for item in crawl_request.urls_and_ids]
    urls = [item['url'] for item in urls_and_ids]

    # Create a crawl session in the database
    db = next(database.get_db())
    crawl_session = schemas.CrawlSessionCreate(
        crawl_id=crawl_id,
        spider_name='content_spider',
        crawl_type='content_crawl',
        start_urls=urls,
        max_links=None
    )
    cruds.create_crawl_session(db, crawl_session)
    db.close()

    # Serialize the request data to a JSON string
    request_data = json.dumps({
        "crawl_id": crawl_id,
        "urls_and_ids": urls_and_ids,
        "delay": crawl_request.delay
    })

    # Get the absolute path to run_crawler.py
    script_dir = os.path.dirname(os.path.realpath(__file__))
    script_path = os.path.join(script_dir, 'run_crawler.py')

    # Start the crawler process
    process = subprocess.Popen([sys.executable, script_path, request_data], cwd=script_dir)
    pid = process.pid

    # Update the CrawlSession with the PID
    db = next(database.get_db())
    cruds.update_crawl_session(db, crawl_id, schemas.CrawlSessionUpdate(pid=pid))
    db.close()

    return {"message": "Content crawling started", "crawl_id": crawl_id}
