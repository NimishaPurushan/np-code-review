from typing import Annotated

from fastapi import Depends

from services.aws import BedrockClient
from services.github import GithubClient

from ..config import config


def get_github_client() -> GithubClient:
    return GithubClient(config.github_app_id, config.github_private_key)


def get_bedrock_client() -> BedrockClient:
    return BedrockClient(
        model_id=config.bedrock_model_id,
        max_tokens=config.bedrock_max_tokens,
        temperature=config.bedrock_temperature,
    )


GitHubClientDependency = Annotated[GithubClient, Depends(get_github_client)]
