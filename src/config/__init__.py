from functools import lru_cache

from .config import Config

__all__ = ["config"]


@lru_cache(maxsize=1)
def get_config() -> Config:
    return Config()


config = get_config()
