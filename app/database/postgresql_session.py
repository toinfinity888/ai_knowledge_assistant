from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

from app.config.postgresql_config import PostgresqlSettings

settings = PostgresqlSettings()

DATABASE_URL = os.environ('DATABASE_URL')
engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)