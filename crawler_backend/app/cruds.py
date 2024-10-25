import pickle
import json
from sqlalchemy.orm import Session
from datetime import datetime
from app.models import WebsiteData, CrawlSession
from app.schemas import WebsiteDataCreate, CrawlSessionCreate, CrawlSessionUpdate

# Create a new entry for website data
def create_website_data(db: Session, website_data: WebsiteDataCreate):
    db_website_data = WebsiteData(
        website_url=website_data.website_url,
        status=website_data.status,
        created_at=datetime.now(),
    )
    db.add(db_website_data)
    db.commit()
    db.refresh(db_website_data)
    return db_website_data

# Retrieve a specific website data by ID
def get_website_data(db: Session, website_data_id: int):
    return db.query(WebsiteData).filter(WebsiteData.id == website_data_id).first()

def update_website_data(db: Session, id: int, title: str, text: str, html: str, status: bool):
    data = db.query(WebsiteData).filter(WebsiteData.id == id).first()
    if data:
        data.title = title
        data.text = text
        data.html = html
        data.status = status
        db.commit()
        db.refresh(data)
        return data
    return None

def get_website_data_by_id(db: Session, id: int):
    # Query to get the WebsiteData entry by its ID
    return db.query(WebsiteData).filter(WebsiteData.id == id).first()

def get_crawl_session(db: Session, crawl_id: str):
    return db.query(CrawlSession).filter(CrawlSession.crawl_id == crawl_id).first()

def create_crawl_session(db: Session, crawl_session: CrawlSessionCreate):
    db_crawl_session = CrawlSession(
        crawl_id=crawl_session.crawl_id,
        spider_name=crawl_session.spider_name,
        crawl_type=crawl_session.crawl_type,
        start_urls=json.dumps(crawl_session.start_urls),  # Ensure start_urls is serialized to JSON
        max_links=crawl_session.max_links,
        status='running',
        visited_links=pickle.dumps([]),  # Initialize as empty
        pending_urls=pickle.dumps(crawl_session.start_urls)
    )
    db.add(db_crawl_session)
    db.commit()
    db.refresh(db_crawl_session)
    return db_crawl_session

def update_crawl_session(db: Session, crawl_id: str, crawl_session_update: CrawlSessionUpdate):
    db_crawl_session = db.query(CrawlSession).filter(CrawlSession.crawl_id == crawl_id).first()
    if db_crawl_session:
        update_data = crawl_session_update.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_crawl_session, key, value)
        db.commit()
        db.refresh(db_crawl_session)
        return db_crawl_session
    return None