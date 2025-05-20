import sqlalchemy as sa
from sqlalchemy import Column, Integer, String
from sqlalchemy.orm import declarative_base, sessionmaker
from app.logging.logger import logger
from datetime import datetime
from app.config.postgresql_config import PostgresqlSettings
from app.config.path_config import PROCESSED_DATA_DIR
from datetime import datetime
from pathlib import Path
import json

settings = PostgresqlSettings()
user_name = settings.KEY
password = settings.PASSWORD
db_name = settings.DB_NAME

Base = declarative_base()
engine = sa.create_engine(f"postgresql://{user_name}:{password}@localhost:5433/{db_name}")
SessionLocal = sessionmaker(bind=engine)
json_path: Path = PROCESSED_DATA_DIR

class EvaluationLogs(Base):
    __tablename__ = 'evaluation_logs'
    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(String)
    query = Column(String)
    context_recall = Column(String)
    faithfulness = Column(String)
    factual_correctness = Column(String)

Base.metadata.create_all(engine)


def get_data_from_json(path: Path):
    if path.is_dir():
        files = path.rglob('*.json')
    elif path.is_file():
        files = [path]
    else:
        logger.info('Required JSON file or directory containing JSON files')
        return []
    for path_file in files:
        try:
            logs = []
            with open(path_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if not isinstance(data, list):
                raise ValueError('Expected a JSON list of strings')
            
            for entry in data:
                timestamp = datetime.utcnow()
                query = entry.get('user_input')
                context_recall = entry.get('context_recall')
                faithfulness = entry.get('faithfulness')
                factual_correctness = entry.get('factual_correctness')
                
                new_log = EvaluationLogs(
                    timestamp=timestamp,
                    query=query,
                    context_recall=context_recall,
                    faithfulness=faithfulness,
                    factual_correctness=factual_correctness
                )
                logs.append(new_log)
            return logs

        except Exception as e:
            logger.error(f'Error reading {path_file}: {e}')

def upsert_logs_to_postgresql(path: Path):
    logs = get_data_from_json(path)

    session = SessionLocal()
    for log in logs:
        try:
            session.add(log)
            session.commit()
        except Exception as e:
            session.rollback()
            logger.info(f"Error: {e}")
        finally:
            session.close()