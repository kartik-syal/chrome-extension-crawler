from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean
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
