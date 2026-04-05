from sqlalchemy import Column, Integer, String, Float, DateTime
from App.db.database import engine
from sqlalchemy.orm import declarative_base
import datetime

Base = declarative_base()

class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    
    company_id = Column(Integer, index=True)
    project_id = Column(Integer, index=True)
    
    service_name = Column(String)   # EC2, S3, etc.
    
    cost = Column(Float)
    usage = Column(Float)
    
    currency = Column(String, default="USD")
    
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)