import pickle
import json
from sqlalchemy.orm import Session
from datetime import datetime
from app.models import WebsiteData, CrawlSession, UserData
from app.schemas import WebsiteDataCreate, CrawlSessionCreate, CrawlSessionUpdate, UserCreate
import uuid

# Create a new entry for website data
def create_website_data(db: Session, website_data: WebsiteDataCreate):
    db_website_data = WebsiteData(
        website_url=website_data.website_url,
        title=website_data.title,
        html=website_data.html,
        text=website_data.text,
        status=website_data.status,
        created_at=datetime.now(),
        crawl_session_id= website_data.crawl_session_id,
        favicon_url=website_data.favicon_url
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
        user_id=crawl_session.user_id,
        crawl_id=crawl_session.crawl_id,
        crawl_name=crawl_session.crawl_name,
        spider_name=crawl_session.spider_name,
        crawl_type=crawl_session.crawl_type,
        start_urls=json.dumps(crawl_session.start_urls),  # Ensure start_urls is serialized to JSON
        max_links=crawl_session.max_links,
        status='running',
        visited_links=pickle.dumps([]),  # Initialize as empty
        pending_urls=pickle.dumps(crawl_session.start_urls),
        depth_limit=crawl_session.depth_limit,
        follow_external=crawl_session.follow_external,
        concurrent_requests=crawl_session.concurrent_requests,
        delay=crawl_session.delay,
        only_child_pages=crawl_session.only_child_pages,
        favicon_url=crawl_session.favicon_url
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

# Get a user by UUID
def get_user(db: Session, user_uuid: str):
    return db.query(UserData).filter(UserData.uuid == user_uuid).first()

def create_user(db: Session):
    # Generate a new UUID
    user_uuid = str(uuid.uuid4())
    
    # Create a new user instance
    db_user = UserData(
        uuid=user_uuid,
        # Add any additional fields here if required
    )
    
    db.add(db_user)  # Add the user to the session
    db.commit()      # Commit the transaction
    db.refresh(db_user)  # Refresh to get the latest data from the database
    return db_user   # Return the created user

# Get all crawl sessions for a specific user
def get_crawl_sessions(db: Session, uuid: str):
    return db.query(CrawlSession).filter(CrawlSession.user_id == uuid).all()

# Delete a specific crawl session
def delete_crawl(db: Session, crawl_session_id: int):
    crawl_session = db.query(CrawlSession).filter(CrawlSession.crawl_id == crawl_session_id).first()
    if crawl_session:
        db.delete(crawl_session)
        db.commit()
        return True
    return False