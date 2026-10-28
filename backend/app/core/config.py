import os
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "Employee Learning Path Advisory Agent"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api"
    
    # MongoDB
    MONGODB_URI: str = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    MONGODB_DB_NAME: str = os.getenv("MONGODB_DB_NAME", "learning_advisory_agent")
    
    # LLM Multi-Provider Fallback Configuration
    LLM_PRIMARY_PROVIDER: str = os.getenv("LLM_PRIMARY_PROVIDER", "gemini")
    LLM_FALLBACK_ORDER: str = os.getenv("LLM_FALLBACK_ORDER", "gemini,openai,grok")
    LLM_REQUEST_TIMEOUT: float = float(os.getenv("LLM_REQUEST_TIMEOUT", "30.0"))

    # Google Gemini API (Backend only - never expose in frontend)
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", os.getenv("GOOGLE_API_KEY", ""))
    GEMINI_API_KEYS: str = os.getenv("GEMINI_API_KEYS", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    # OpenAI API
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # xAI Grok API
    XAI_API_KEY: str = os.getenv("XAI_API_KEY", os.getenv("GROK_API_KEY", ""))
    XAI_MODEL: str = os.getenv("XAI_MODEL", os.getenv("GROK_MODEL", "grok-3-mini"))
    
    # JWT Authentication
    JWT_SECRET: str = os.getenv("JWT_SECRET", "learning-path-agent-jwt-super-secret-key-2026")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "*"
    ]
    
    # Paths
    BASE_DIR: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    DATA_DIR: str = os.path.join(BASE_DIR, "data")

    def get_gemini_api_keys(self) -> List[str]:
        """
        Parses single or multiple Gemini API keys from GEMINI_API_KEYS and GEMINI_API_KEY.
        Supports comma, semicolon, or newline separated keys for seamless failover/rotation.
        Internal only - never exposed to the frontend.
        """
        raw_keys = []
        mult = self.GEMINI_API_KEYS or os.getenv("GEMINI_API_KEYS", "")
        if mult:
            raw_keys.extend([k.strip() for k in mult.replace(";", ",").replace("\n", ",").split(",") if k.strip()])
            
        single = self.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")
        if single:
            raw_keys.extend([k.strip() for k in single.replace(";", ",").replace("\n", ",").split(",") if k.strip()])

        valid = []
        seen = set()
        for k in raw_keys:
            if k and k not in seen and k not in ("replace_with_your_key", "your_api_key_here", "none"):
                seen.add(k)
                valid.append(k)
        return valid

    def get_provider_order(self) -> List[str]:
        """
        Determines the ordered list of LLM providers to attempt.
        Prioritizes LLM_PRIMARY_PROVIDER followed by LLM_FALLBACK_ORDER without duplicates.
        """
        raw_order = self.LLM_FALLBACK_ORDER or os.getenv("LLM_FALLBACK_ORDER", "gemini,openai,grok")
        providers = [p.strip().lower() for p in raw_order.replace(";", ",").split(",") if p.strip()]
        
        primary = (self.LLM_PRIMARY_PROVIDER or os.getenv("LLM_PRIMARY_PROVIDER", "gemini")).strip().lower()
        if primary:
            if primary in providers:
                providers.remove(primary)
            providers.insert(0, primary)
            
        ordered = []
        for p in providers:
            if p in ("gemini", "openai", "grok") and p not in ordered:
                ordered.append(p)
                
        return ordered or ["gemini", "openai", "grok"]

    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env", "../.env"),
        extra="allow"
    )

settings = Settings()
