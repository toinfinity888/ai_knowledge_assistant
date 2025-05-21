from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

from app.config.postgresql_config import PostgresqlSettings

settings = PostgresqlSettings()

user_name = settings.KEY
password = settings.PASSWORD
db_name = settings.DB_NAME

DATABASE_URL = os.environ('DATABASE_URL')
engine = create_engine(DATABASE_URL)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)