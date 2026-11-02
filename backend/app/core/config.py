import os
from typing import List
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    ENABLE_DEMO_SEEDING: bool = os.getenv("ENABLE_DEMO_SEEDING", "true").lower() in ("true", "1", "yes")
    PROJECT_NAME: str = "HotelOS"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "hotelos-super-secret-key-change-in-production-2026")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "sqlite+aiosqlite:///./hotelos.db"
    )
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://*.vercel.app",
        "*"
    ]
    
    # External APIs (Optional / Mockable when unconfigured)
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    SUPABASE_JWT_SECRET: str = os.getenv("SUPABASE_JWT_SECRET", "")
    WHATSAPP_API_TOKEN: str = os.getenv("WHATSAPP_API_TOKEN", "")
    WHATSAPP_PHONE_NUMBER_ID: str = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")
    
    # AI Operations Assistant Configuration
    AI_PROVIDER: str = os.getenv("AI_PROVIDER", "auto") # "gemini", "openai", "auto", "deterministic"
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
    AI_MAX_TOKENS: int = int(os.getenv("AI_MAX_TOKENS", "1000"))
    
    # Hotel Default
    DEFAULT_TIMEZONE: str = "Asia/Kolkata"
    DEFAULT_CURRENCY: str = "INR"

    # Proxy Trust Configuration
    TRUSTED_PROXIES: List[str] = [
        ip.strip() for ip in os.getenv("TRUSTED_PROXIES", "127.0.0.1,::1,localhost,testclient").split(",") if ip.strip()
    ]
    TRUST_ALL_PROXIES: bool = os.getenv("TRUST_ALL_PROXIES", "false").lower() in ("true", "1", "yes")

    # AI Quota Defaults
    DEFAULT_TENANT_DAILY_AI_LIMIT: int = int(os.getenv("DEFAULT_TENANT_DAILY_AI_LIMIT", "500"))
    DEFAULT_TENANT_MONTHLY_AI_LIMIT: int = int(os.getenv("DEFAULT_TENANT_MONTHLY_AI_LIMIT", "5000"))
    DEFAULT_TENANT_MONTHLY_AI_BUDGET_USD: float = float(os.getenv("DEFAULT_TENANT_MONTHLY_AI_BUDGET_USD", "20.00"))

    class Config:
        case_sensitive = True
        env_file = ".env"

    def model_post_init(self, __context):
        # Auto-detect Google Gemini credentials if placed in OPENAI fields
        if not self.GEMINI_API_KEY and self.OPENAI_API_KEY:
            if self.OPENAI_API_KEY.startswith("AQ.") or self.OPENAI_API_KEY.startswith("AIza"):
                self.GEMINI_API_KEY = self.OPENAI_API_KEY
                if self.AI_PROVIDER == "openai":
                    self.AI_PROVIDER = "gemini"
        if not self.OPENAI_API_KEY and self.GEMINI_API_KEY:
            if not self.OPENAI_API_KEY:
                self.OPENAI_API_KEY = self.GEMINI_API_KEY
        if self.GEMINI_MODEL in ["gemini-1.5-flash", "gemini-2.5-flash", "gemini-1.5-pro", "gemini-2.0-flash", "gemini-3-flash-preview"]:
            self.GEMINI_MODEL = "gemini-3.5-flash-lite"

settings = Settings()

