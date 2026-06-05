from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional, List

class Settings(BaseSettings):
    PROJECT_NAME: str = "VoiceJournal API"
    API_V1_STR: str = "/api/v1"
    
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ENCRYPTION_KEY: str = ""
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7
    
    # Database
    DATABASE_URL: str = "postgresql+psycopg2://postgres.lmokacduzaspzxikbrra:Ankitk24%40123@aws-1-ap-northeast-2.pooler.supabase.com:6543/postgres"
    
    @property
    def SQLALCHEMY_DATABASE_URI(self) -> str:
        return self.DATABASE_URL
        
    # Celery / Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # CORS
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    
    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]
    
    # AWS S3 (mock local for now)
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # S3 Storage Configuration
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_BUCKET_NAME: str = "voicejournal-audio"
    AWS_REGION: str = "us-east-1"
    
    # AI Configuration
    GROQ_API_KEY: str = ""

    # Test settings
    TESTING: bool = False
    
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

settings = Settings()
