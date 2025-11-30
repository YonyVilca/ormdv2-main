'''from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config.settings import Config

if not Config.DATABASE_URL:
    raise ValueError("DATABASE_URL no está definida en .env")

# Add explicit client encoding for PostgreSQL
engine = create_engine(
    Config.DATABASE_URL, 
    future=True,
    connect_args={"client_encoding": "utf8"}
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()'''

import os
import re
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from config.settings import Config  


if not hasattr(Config, 'DATABASE_URL') or not Config.DATABASE_URL:
    raise ValueError("DATABASE_URL no está definida en .env o Config.")

ssl_match = re.search(r'sslmode=([^&]*)', Config.DATABASE_URL)
ssl_mode = ssl_match.group(1) if ssl_match else 'prefer' 

db_url_base = re.sub(r'\?.*', '', Config.DATABASE_URL)

engine = create_engine(
    db_url_base, 
    future=True,
    connect_args={
        "client_encoding": "utf8", 
        "sslmode": ssl_mode 
    }
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
