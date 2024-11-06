from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

# Schema for creating website data
class WebsiteDataCreate(BaseModel):
    website_url: str
    title: Optional[str] = None
    status: Optional[bool] = False
    html: Optional[str] = None
    text: Optional[str] = None
    crawl_session_id: int
    favicon_url: str
    class Config:
        from_attributes = True

# Schema for updating website data
class WebsiteDataUpdate(BaseModel):
    website_url: Optional[str] = None
    title: Optional[str] = None
    status: Optional[bool] = None
    html: Optional[str] = None
    text: Optional[str] = None

    class Config:
        from_attributes = True

# Schema for reading website data
class WebsiteData(BaseModel):
    id: int
    website_url: str
    title: Optional[str] = None
    status: bool
    created_at: datetime
    html: Optional[str] = None
    text: Optional[str] = None

    class Config:
        from_attributes = True

class CrawlSessionBase(BaseModel):
    crawl_id: str
    status: str
    spider_name: str
    start_urls: List[str]
    created_at: datetime
    link_count: int
    max_links: int
    depth_limit: int
    follow_external: bool
    concurrent_requests: int
    delay: Optional[float] = None

    class Config:
        from_attributes = True

class CrawlSessionCreate(BaseModel):
    user_id: str
    crawl_id: str
    crawl_name: str
    spider_name: str
    crawl_type: str
    start_urls: List[str]
    max_links: Optional[int] = Field(default=None)
    depth_limit: int
    follow_external: bool
    concurrent_requests: int
    delay: float
    only_child_pages: bool = False
    favicon_url: str
    crawl_location: str = 'server'  # Options: 'server', 'client'

class CrawlSessionUpdate(BaseModel):
    crawl_id: Optional[str] = None
    status: Optional[str] = None
    pid: Optional[int] = None
    request_queue: Optional[bytes] = None
    visited_links: Optional[bytes] = None
    link_count: Optional[int] = None

class UserCreate(BaseModel):
    pass

    class Config:
        from_attributes = True


class CrawlSessionResponse(BaseModel):
    id: int
    crawl_id: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True

class UserDataResponse(BaseModel):
    uuid: str
    user_data: List[CrawlSessionResponse] = []

    class Config:
        from_attributes = True