from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# Schema for creating website data
class WebsiteDataCreate(BaseModel):
    website_url: str
    title: Optional[str] = None
    status: Optional[bool] = False
    html: Optional[str] = None
    text: Optional[str] = None

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
