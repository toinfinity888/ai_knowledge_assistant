
from pydantic_settings import BaseSettings

class PostgresqlSettings(BaseSettings):
    DATABASE_URL: str

    class Config:
        env_file = '.env'
        extra = 'ignore'
    

