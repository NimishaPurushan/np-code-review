import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    ENVIROMENT: str = "development"
    GITHUB_APP_ID: str
    GITHUB_PRIVATE_KEY: str

    AZURE_OPENAI_ENDPOINT: str
    AZURE_OPENAI_TENANT_ID: str
    AZURE_OPENAI_CLIENT_ID: str
    AZURE_OPENAI_CLIENT_SECRET: str
    AZURE_OPENAI_API_VERSION: str = "2024-08-01-preview"
    AZURE_OPENAI_DEPLOYMENT_NAME: str
    AZURE_OPENAI_TOKEN_SCOPE: str = "https://cognitiveservices.azure.com/.default"

    AZURE_OPENAI_MAX_TOKENS: int = 4096
    AZURE_OPENAI_TEMPERATURE: float = 0.7

    DATABASE_URL: str = "sqlite+aiosqlite:///./code_review.db"

    AUTO_REVIEW_ENABLED: bool = True
    REVIEW_ON_READY_FOR_REVIEW: bool = True
    REVIEW_ON_NEW_COMMITS: bool = True

    model_config = SettingsConfigDict(
        **dict(env_file=".env", extra="ignore", case_sensitive=True)
        if os.environ.get("ENVIRONMENT", "development") == "development"
        else dict(extra="ignore", env_file=None, case_sensitive=True)
    )
