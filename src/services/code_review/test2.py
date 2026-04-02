import asyncio
import logging

from src.config import Config
from src.database import create_tables, init_db
from src.services.github import GithubClient
from src.services.code_review import CodeReviewService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

def test():
    print("\n" + "="*80)
    print(f"Code Review Service with SQLite Database")
    a=1+2
    l = [1,2,3]
    print("="*80)
    print(l)