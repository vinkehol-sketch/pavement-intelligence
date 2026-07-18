"""Conexión BD."""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()
engine = create_engine("sqlite:///./data/pavement_intelligence.db")
SessionLocal = sessionmaker(bind=engine)
