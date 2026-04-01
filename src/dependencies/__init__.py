from typing import Annotated

from fastapi import Depends

from ..config import config
from ..services.ai import AIClient
from ..services.github import GithubClient


def get_github_client() -> GithubClient:
    return GithubClient(config.GITHUB_APP_ID, config.GITHUB_PRIVATE_KEY)


def get_ai_client() -> AIClient:
    return AIClient(
        azure_endpoint=config.AZURE_OPENAI_ENDPOINT,
        tenant_id=config.AZURE_OPENAI_TENANT_ID,
        client_id=config.AZURE_OPENAI_CLIENT_ID,
        client_secret=config.AZURE_OPENAI_CLIENT_SECRET,
        deployment_name=config.AZURE_OPENAI_DEPLOYMENT_NAME,
        api_version=config.AZURE_OPENAI_API_VERSION,
        token_scope=config.AZURE_OPENAI_TOKEN_SCOPE,
        max_tokens=config.AZURE_OPENAI_MAX_TOKENS,
        temperature=config.AZURE_OPENAI_TEMPERATURE,
    )


GitHubClientDependency = Annotated[GithubClient, Depends(get_github_client)]
