from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, PickleType, ForeignKey, Float
from datetime import datetime
from app.database import Base
from sqlalchemy.orm import relationship

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
    crawl_session_id = Column(Integer, ForeignKey('crawl_session.id'), index=True)  # Foreign key reference
    favicon_url = Column(Text)

    # Relationship to access CrawlSession from WebsiteData
    crawl_session = relationship("CrawlSession", back_populates="website_data")

class CrawlSession(Base):
    __tablename__ = "crawl_session"

    id = Column(Integer, primary_key=True, index=True)
    crawl_id = Column(String, index=True, unique=True)
    crawl_name = Column(String)
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
    # Relationship to access WebsiteData from CrawlSession
    website_data = relationship("WebsiteData", back_populates="crawl_session", cascade="all, delete-orphan")
    depth_limit = Column(Integer, nullable=True)
    follow_external = Column(Boolean, nullable=True, default=False)
    concurrent_requests = Column(Integer, nullable=True)
    delay = Column(Float, nullable=True)
    only_child_pages = Column(Boolean, default=False)
    user_id = Column(String, ForeignKey('user_data.uuid'), index=True)  # Foreign key reference

    # Relationship to access CrawlSession from WebsiteData
    user = relationship("UserData", back_populates="user_data")
    favicon_url = Column(Text)


class UserData(Base):
    __tablename__ = "user_data"

    uuid = Column(String, primary_key=True, index=True)
    # Relationship to access CrawlSession from WebsiteData
    user_data = relationship("CrawlSession", back_populates="user", cascade="all, delete-orphan")
    