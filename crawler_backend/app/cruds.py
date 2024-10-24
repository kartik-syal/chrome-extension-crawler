from sqlalchemy.orm import Session
from datetime import datetime
from app.models import WebsiteData
from app.schemas import WebsiteDataCreate

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