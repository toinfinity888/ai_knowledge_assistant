
from pydantic_settings import BaseSettings

class PostgresqlSettings(BaseSettings):
    KEY: str
    PASSWORD: str
    DB_NAME: str
    DATABASE_URL: str

    class Config:
        env_file = '.env'
        env_prefix = 'POSTGRESQL_'
        extra = 'ignore'
    

