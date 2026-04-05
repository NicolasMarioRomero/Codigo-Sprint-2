from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = "postgresql://postgres:1597@localhost:5432/cloudcosts"

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)