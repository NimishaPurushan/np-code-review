from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    ENVIROMENT: str = "development"
    # GitHub Configuration
    GITHUB_APP_ID: str
    GITHUB_PRIVATE_KEY: str

    # AWS Configuration
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_REGION: str = "us-east-1"

    # AWS Bedrock Configuration
    BEDROCK_MODEL_ID: str = "amazon.nova-micro-v1:0"
    BEDROCK_MAX_TOKENS: int = 4096
    BEDROCK_TEMPERATURE: float = 0.7

    # Database Configuration
    DATABASE_URL: str = "sqlite+aiosqlite:///./code_review.db"

    # Bot behavior settings
    AUTO_REVIEW_ENABLED: bool = True
    REVIEW_ON_READY_FOR_REVIEW: bool = True
    REVIEW_ON_NEW_COMMITS: bool = True
    USE_AI_REVIEW: bool = True  # Enable AI-powered code review

    model_config = SettingsConfigDict(env_file=None, extra="ignore", case_sensitive=True)
