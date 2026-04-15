import logging
import tomllib
import traceback
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from .config import Config
from .database import create_tables
from .dependencies import GitHubDependency, get_github_client
from .services import CodeReviewService
from .services.github.types import GitHubEventType
from .services.github.utils import verify_github_signature

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
#print("hello")

def load_project_metadata():
    pyproject_path = Path(__file__).parent.parent / "pyproject.toml"

    try:
        with pyproject_path.open("rb") as f:
            pyproject_data = tomllib.load(f)
            project_info = pyproject_data.get("project", {})
            return {
                "title": project_info.get("name", "np-code-review"),
                "description": project_info.get("description", "Code Review GitHub Bot"),
                "version": project_info.get("version", "0.1.0"),
            }
    except Exception as e:
        logger.warning(f"Could not load pyproject.toml: {e}")
        return {
            "title": "np-code-review",
            "description": "Code Review GitHub Bot",
            "version": "0.1.0",
        }


metadata = load_project_metadata()

app = FastAPI(
    title=metadata["title"],
    description=metadata["description"],
    version=metadata["version"],
)


@app.on_event("startup")
async def startup_event():
    logger.info("Initializing application...")
    try:
        await create_tables()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}", exc_info=True)
        raise


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(
        f""""Unhandled exception: {type(exc).__name__}: {exc}
        Path: {request.url.path}
        Traceback:\n{traceback.format_exc()}"""
    )

    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


config = Config()
code_review_service = CodeReviewService(config)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/webhook/github")
async def github_webhook(
    request: Request,
    x_github_event: str | None = Header(None),
    x_hub_signature_256: str | None = Header(None),
    github: GitHubDependency = Depends(get_github_client),  # noqa: B008
):
    payload = await request.body()

    if not verify_github_signature(payload, x_hub_signature_256, config.github_webhook_secret):
        raise HTTPException(status_code=401, detail="Invalid signature")

    data = await request.json()
    logger.info(f"Received GitHub event: {x_github_event}")

    if x_github_event == GitHubEventType.PULL_REQUEST:
        return await trigger_code_review(data, github)
    elif x_github_event == GitHubEventType.PULL_REQUEST_REVIEW:
        return await trigger_code_review(data)
    else:
        logger.info(f"Unhandled event type: {x_github_event}")
        return {"message": "Event received but not handled"}


async def trigger_code_review(
    repo_full_name: str,
    pr_number: int,
    pr_data: dict,
    github: GitHubDependency,
    installation_id: int,
):
    await code_review_service.review_pull_request(
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        github=github,
        installation_id=installation_id,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
