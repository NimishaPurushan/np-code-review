import logging
import tomllib
import traceback
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from config import Config
from github import GitHubDependency, get_github_client
from github.types import GitHubEventType
from github.utils import is_supported_github_pull_request_action, verify_github_signature
from routes import ai_routes
from services import CodeReviewService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler that logs all unhandled exceptions."""
    # Log the full exception with traceback
    logger.error(
        f"Unhandled exception: {type(exc).__name__}: {exc}\n"
        f"Path: {request.url.path}\n"
        f"Traceback:\n{traceback.format_exc()}"
    )

    # For HTTPExceptions, preserve the status code and detail
    if isinstance(exc, HTTPException):
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    # For all other exceptions, return 500
    return JSONResponse(
        status_code=500, content={"detail": "Internal server error", "error": str(exc)}
    )


app.include_router(ai_routes.router)

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
        return await handle_pull_request_event(data, github)
    elif x_github_event == GitHubEventType.PULL_REQUEST_REVIEW:
        return await handle_pull_request_review_event(data)
    elif x_github_event == GitHubEventType.PULL_REQUEST_REVIEW_COMMENT:
        return await handle_pull_request_review_comment_event(data)
    elif x_github_event == GitHubEventType.PUSH:
        return await handle_push_event(data)
    elif x_github_event == GitHubEventType.PING:
        return {"message": "pong"}
    else:
        logger.info(f"Unhandled event type: {x_github_event}")
        return {"message": "Event received but not handled"}


async def handle_pull_request_event(data: dict, github: GitHubDependency):
    action = data.get("action")
    pr_data = data.get("pull_request", {})
    repo_full_name = data.get("repository", {}).get("full_name")
    pr_number = pr_data.get("number")

    logger.info(f"PR #{pr_number} action: {action} in {repo_full_name}")

    if is_supported_github_pull_request_action(action):
        await trigger_code_review(repo_full_name, pr_number, pr_data, github)

    return {"message": f"PR event processed: {action}"}


async def handle_pull_request_review_event(data: dict):
    action = data.get("action")
    logger.info(f"PR review action: {action}")
    return {"message": f"PR review event processed: {action}"}


async def handle_pull_request_review_comment_event(data: dict):
    action = data.get("action")
    logger.info(f"PR review comment action: {action}")
    return {"message": f"PR review comment event processed: {action}"}


async def handle_push_event(data: dict):
    ref = data.get("ref")
    logger.info(f"Push event to ref: {ref}")
    return {"message": "Push event processed"}


async def trigger_code_review(
    repo_full_name: str, pr_number: int, pr_data: dict, github: GitHubDependency
):
    """Trigger a code review for the given pull request."""
    await code_review_service.review_pull_request(
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        github=github,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
