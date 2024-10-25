from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, PickleType
from datetime import datetime
from app.database import Base

# Define a new model to store website crawling data
class WebsiteData(Base):
    __tablename__ = "website_data"

    id = Column(Integer, primary_key=True, index=True)
    website_url = Column(String, index=True)          # Website URL
    title = Column(String, index=True)                # Title of the website
    status = Column(Boolean, default=False, index=True)  # Success/Failure status
    created_at = Column(DateTime, default=datetime.now, index=True)  # When the data was crawled
    html = Column(Text)                               # Full HTML content
    text = Column(Text)                               # Extracted text content

class CrawlSession(Base):
    __tablename__ = "crawl_session"

    id = Column(Integer, primary_key=True, index=True)
    crawl_id = Column(String, index=True, unique=True)
    pid = Column(Integer, nullable=True)
    status = Column(String, default='running')  # 'running', 'paused', 'completed'
    created_at = Column(DateTime, default=datetime.now)
    spider_name = Column(String)
    crawl_type = Column(String)
    start_urls = Column(Text)  # JSON serialized list
    max_links = Column(Integer, nullable=True)
    request_queue = Column(PickleType)  # Serialized request queue
    visited_links = Column(PickleType)  # Serialized set of visited URLs
    pending_urls = Column(PickleType)
    link_count = Column(Integer, default=0)