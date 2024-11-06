# app/main.py

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
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
from app.database import SessionLocal
from app.cruds import *
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

app = FastAPI()

crawler_processes = {}

class ScrapyRequest(BaseModel):
    crawl_name: str
    start_urls: List[str]
    max_links: int = 10
    follow_external: bool = False
    depth_limit: int = 2
    concurrent_requests: int = 16
    delay: float = 0.0  # Delay for content crawling
    user_id: str
    only_child_pages: bool = False
    
class CrawlControlRequest(BaseModel):
    crawl_id: str

class GetAllCrawls(BaseModel):
    user_id: str

class DeleteCrawlSession(BaseModel):
    crawl_session_id: str

@app.post("/crawl-url/")
async def crawl(scrapy_request: ScrapyRequest, request: Request):
    # Generate a unique identifier for this crawl session
    crawl_id = str(uuid4())

    # Create a crawl session in the database
    db = next(database.get_db())
    user_exists = cruds.get_user(db, scrapy_request.user_id)

    # If user doesn't exist, create a new user
    if not user_exists:
        new_user = cruds.create_user(db=db)
        scrapy_request.user_id = new_user.uuid
        headers = {"user-uuid-update": new_user.uuid}  # Set the header with the new UUID
    else:
        headers = {}

    # Prepare the request data
    request_data = {
        "user_id": scrapy_request.user_id,
        "crawl_id": crawl_id,
        "start_urls": scrapy_request.start_urls,
        "max_links": scrapy_request.max_links,
        "follow_external": scrapy_request.follow_external,
        "depth_limit": scrapy_request.depth_limit,
        "concurrent_requests": scrapy_request.concurrent_requests,
        "delay": scrapy_request.delay,
        "only_child_pages": scrapy_request.only_child_pages,
    }

    print("url = ",scrapy_request.start_urls[0])
    favicon_url = get_favicon_url(scrapy_request.start_urls[0])
    crawl_session = schemas.CrawlSessionCreate(
        user_id = scrapy_request.user_id,
        crawl_id=crawl_id,
        crawl_name=scrapy_request.crawl_name,
        spider_name='web_spider',
        crawl_type='url_crawl',  # Can indicate it's a combined crawl
        start_urls=scrapy_request.start_urls,
        max_links=scrapy_request.max_links,
        follow_external=scrapy_request.follow_external,
        depth_limit=scrapy_request.depth_limit,
        concurrent_requests=scrapy_request.concurrent_requests,
        delay=scrapy_request.delay,
        only_child_pages=scrapy_request.only_child_pages,
        favicon_url=favicon_url
    )
    cruds.create_crawl_session(db, crawl_session)
    db.close()

    # Serialize the request data to a JSON string
    serialized_request_data = json.dumps(request_data)

    # Path to run_crawler.py
    script_dir = os.path.dirname(os.path.realpath(__file__))
    script_path = os.path.join(script_dir, 'run_crawler.py')

    # Start the crawler process
    process = subprocess.Popen([sys.executable, script_path, serialized_request_data], cwd=script_dir)
    pid = process.pid

    # Update the CrawlSession with the PID
    db = next(database.get_db())
    cruds.update_crawl_session(db, crawl_id, schemas.CrawlSessionUpdate(pid=pid))
    db.close()

    return JSONResponse(content={"message": "Crawling started", "crawl_id": crawl_id}, headers=headers)

@app.post("/pause-crawl/")
def pause_crawl(request: CrawlControlRequest):
    crawl_id = request.crawl_id
    with next(database.get_db()) as db:  # Use context manager for DB session
        crawl_session = cruds.get_crawl_session(db, crawl_id)

        if crawl_session and crawl_session.pid:
            pid = crawl_session.pid
            try:
                os.kill(pid, signal.SIGTERM)  # Terminate the process
                # Update the crawl session status to 'paused' and clear the PID
                cruds.update_crawl_session(db, crawl_id, schemas.CrawlSessionUpdate(status='paused', pid=None))
                return {"message": f"Crawl {crawl_id} paused"}
            except ProcessLookupError:
                # Handle case where the PID is no longer valid
                cruds.update_crawl_session(db, crawl_id, schemas.CrawlSessionUpdate(status='paused', pid=None))
                return JSONResponse(status_code=200, content={"message": f"Crawl {crawl_id} paused, process not found"})
            except Exception as e:
                raise HTTPException(status_code=500, detail=str(e))
        else:
            raise HTTPException(status_code=404, detail="Crawl not found or PID not available")


@app.post("/resume-crawl/")
def resume_crawl(request: CrawlControlRequest):
    crawl_id = request.crawl_id

    with next(database.get_db()) as db:  # Use context manager for DB session
        crawl_session = cruds.get_crawl_session(db, crawl_id)

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

            try:
                # Start the crawler process
                script_dir = os.path.dirname(os.path.realpath(__file__))
                script_path = os.path.join(script_dir, 'run_crawler.py')
                process = subprocess.Popen([sys.executable, script_path, request_data], cwd=script_dir)
                
                # Update the CrawlSession with the new PID
                cruds.update_crawl_session(db, crawl_id, schemas.CrawlSessionUpdate(pid=process.pid, status="running"))

                return {"message": f"Crawl {crawl_id} resumed"}
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to start crawl: {str(e)}")
        else:
            raise HTTPException(status_code=404, detail="Crawl session not found or not in paused state")

@app.post("/create-user/")  # Specify the response model to return
def create_user_endpoint():
    # Retrieve the session from the database
    db = next(database.get_db())
    db_user = create_user(db=db)
    db.close()
    return db_user  # Return the created user

# API to get all crawl sessions for a specific user
@app.post("/get-all-crawls")
def get_user_crawl_sessions(get_crawl: GetAllCrawls):
    db = next(database.get_db())
    crawl_sessions = get_crawl_sessions(db=db, uuid=get_crawl.user_id)
    db.close()
    if not crawl_sessions:
        raise HTTPException(status_code=404, detail="No crawl sessions found for the given user.")

    # Manually filter out non-serializable fields
    serialized_sessions = [
        {
            "id": session.id,
            "crawl_id": session.crawl_id,
            "crawl_name": session.crawl_name,
            "status": session.status,
            "created_at": session.created_at,
            "favicon": session.favicon_url,
            "link_count": session.link_count
        }
        for session in crawl_sessions
    ]

    return serialized_sessions

# API to delete a specific crawl session
@app.post("/delete-crawl")
def delete_crawl_session(delete_crawl_session: DeleteCrawlSession):
    db = next(database.get_db())
    success = delete_crawl(db=db, crawl_session_id=delete_crawl_session.crawl_session_id)
    db.close()
    if not success:
        raise HTTPException(status_code=404, detail="Crawl session not found")
    return {"success": True, "message": "session deleted successfully."}

@app.post("/create-crawl-session/")
async def create_crawl_session(scrapy_request: ScrapyRequest, request: Request):
    crawl_id = str(uuid4())
    db = next(database.get_db())
    user_exists = cruds.get_user(db, scrapy_request.user_id)

    if not user_exists:
        new_user = cruds.create_user(db=db)
        scrapy_request.user_id = new_user.uuid
        headers = {"user-uuid-update": new_user.uuid}
    else:
        headers = {}

    favicon_url = get_favicon_url(scrapy_request.start_urls[0])
    crawl_session = schemas.CrawlSessionCreate(
        user_id=scrapy_request.user_id,
        crawl_id=crawl_id,
        crawl_name=scrapy_request.crawl_name,
        spider_name='web_spider',
        crawl_type='url_crawl',
        start_urls=scrapy_request.start_urls,
        max_links=scrapy_request.max_links,
        follow_external=scrapy_request.follow_external,
        depth_limit=scrapy_request.depth_limit,
        concurrent_requests=scrapy_request.concurrent_requests,
        delay=scrapy_request.delay,
        only_child_pages=scrapy_request.only_child_pages,
        favicon_url=favicon_url,
        crawl_location='client'  # Indicate client-side crawl
    )
    db_crawl = cruds.create_crawl_session(db, crawl_session)
    db.close()

    return JSONResponse(content={"message": "Crawl session created", "crawl_id": db_crawl.id}, headers=headers)

@app.post("/store-website-data/")
async def store_website_data(website_data: schemas.WebsiteDataCreate):
    db = next(database.get_db())
    try:
        cruds.create_website_data(db, website_data)
        db.close()
        return {"message": "Website data stored"}
    except Exception as e:
        db.close()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/update-crawl-session/")
async def update_crawl_session(update_request: schemas.CrawlSessionUpdate):
    db = next(database.get_db())
    try:
        # Call the CRUD function with the update request directly
        updated_session = cruds.update_crawl_session(db, update_request.crawl_id, update_request)
        
        if updated_session:
            return {"message": "Crawl session updated"}
        else:
            raise HTTPException(status_code=404, detail="Crawl session not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def get_favicon_url(page_url):
    try:
        print("going to get favicon url")
        # Fetch the page content
        response = requests.get(page_url, timeout=10)
        response.raise_for_status()  # Check if the request was successful

        # Parse the HTML content
        soup = BeautifulSoup(response.text, 'html.parser')

        favicon_urls = [
            urljoin(page_url, '/favicon.ico'),
            soup.find("link", rel="icon"),
            soup.find("link", rel="shortcut icon")
        ]

        for icon_link in favicon_urls[1:]:
            if icon_link and 'href' in icon_link.attrs:
                return urljoin(page_url, icon_link['href'])
                
        # Fallback to default favicon location if none found
        return favicon_urls[0]
    
    except requests.RequestException as e:
        print("Error fetching page:", e)
        return None