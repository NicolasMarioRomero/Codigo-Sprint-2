from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:password@db:5432/cloudcosts"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)
