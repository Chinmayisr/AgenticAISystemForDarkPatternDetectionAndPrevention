# config.py

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Dict, List
from functools import lru_cache


class Settings(BaseSettings):
    """
    All configuration comes from environment variables.
    Pydantic validates types automatically.
    """

    # API Keys
    google_api_key: str = Field(..., env="GOOGLE_API_KEY")

    # Models
    orchestrator_model: str = Field("gemini-3.1-pro", env="ORCHESTRATOR_MODEL")
    nlp_agent_model: str    = Field("gemini-3.1-pro", env="NLP_AGENT_MODEL")
    visual_agent_model: str = Field("gemini-3.1-pro", env="VISUAL_AGENT_MODEL")
    prevention_model: str   = Field("gemini-3.1-flash", env="PREVENTION_MODEL")

    # Storage
    redis_url: str      = Field("redis://localhost:6379", env="REDIS_URL")
    qdrant_url: str     = Field("http://localhost:6333", env="QDRANT_URL")
    database_url: str   = Field("sqlite:///./dark_guard.db", env="DATABASE_URL")

    # MCP Server
    mcp_host: str = Field("localhost", env="MCP_HOST")
    mcp_port: int = Field(8765, env="MCP_PORT")

    # Thresholds
    high_confidence_threshold: float   = Field(0.80, env="HIGH_CONFIDENCE_THRESHOLD")
    medium_confidence_threshold: float = Field(0.55, env="MEDIUM_CONFIDENCE_THRESHOLD")
    low_confidence_threshold: float    = Field(0.35, env="LOW_CONFIDENCE_THRESHOLD")

    # App
    environment: str = Field("development", env="ENVIRONMENT")
    log_level: str   = Field("INFO", env="LOG_LEVEL")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    return Settings()


# Dark pattern catalog — single source of truth
DARK_PATTERNS: Dict[str, str] = {
    "DP01": "False Urgency",
    "DP02": "Basket Sneaking",
    "DP03": "Confirm Shaming",
    "DP04": "Forced Action",
    "DP05": "Subscription Trap",
    "DP06": "Interface Interference",
    "DP07": "Bait and Switch",
    "DP08": "Drip Pricing",
    "DP09": "Disguised Ads",
    "DP10": "Nagging",
    "DP11": "Trick Question",
    "DP12": "SaaS Billing",
    "DP13": "Rogue/Malicious Patterns",
}

# Which agent is PRIMARY handler for each pattern
PATTERN_TO_AGENT: Dict[str, str] = {
    "DP01": "nlp",
    "DP02": "behavioral",
    "DP03": "nlp",
    "DP04": "nlp",
    "DP05": "nlp",
    "DP06": "visual",
    "DP07": "pricing",
    "DP08": "pricing",
    "DP09": "visual",
    "DP10": "behavioral",
    "DP11": "nlp",
    "DP12": "nlp",
    "DP13": "visual",
}

# Text-based patterns (NLP agent)
TEXT_PATTERNS: List[str] = ["DP01", "DP03", "DP04", "DP05", "DP10", "DP11", "DP12"]

# Visual patterns (Visual agent)
VISUAL_PATTERNS: List[str] = ["DP06", "DP09", "DP13"]

# Pricing patterns (Pricing agent)
PRICING_PATTERNS: List[str] = ["DP07", "DP08"]

# Behavioral patterns (Behavioral agent)
BEHAVIORAL_PATTERNS: List[str] = ["DP02", "DP10"]