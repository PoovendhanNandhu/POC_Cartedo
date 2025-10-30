"""Application configuration."""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration."""
    
    # OpenAI Settings
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")  # ← Much faster & cheaper!
    OPENAI_TEMPERATURE: float = float(os.getenv("OPENAI_TEMPERATURE", "0"))
    OPENAI_SEED: int = int(os.getenv("OPENAI_SEED", "42"))
    OPENAI_TIMEOUT: int = 300  # ← Increased to 5 minutes for safety
    
    # App Settings
    APP_NAME: str = os.getenv("APP_NAME", "Scenario Re-Contextualization API")
    APP_VERSION: str = os.getenv("APP_VERSION", "1.0.0")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Workflow Settings
    MAX_RETRIES: int = 2
    CONSISTENCY_THRESHOLD: float = 0.85
    
    # Locked Fields (immutable)
    LOCKED_FIELDS: list[str] = [
        "scenarioOptions",
        "assessmentCriterion",
        "selectedAssessmentCriterion",
        "industryAlignedActivities",
        "selectedIndustryAlignedActivities"
    ]


config = Config()
