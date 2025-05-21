
from pydantic_settings import BaseSettings

class PostgresqlSettings(BaseSettings):
    DATABASE_URL: str

    class Config:
        env_file = '.env'
        env_prefix = 'POSTGRESQL_'
        extra = 'ignore'
    

