# NP Code Review Bot

A FastAPI-based GitHub code review bot that automatically reviews pull requests using PyGithub.

## Features

- 🤖 Automated PR review on open, synchronize, and ready_for_review events
- 🔐 Webhook signature verification
- 📝 Configurable review triggers
- 🚀 FastAPI with async support
- 📊 Comprehensive logging

## Setup

### 1. Install Dependencies

```bash
uv sync
```

### 2. Configure Environment Variables

Copy `.env.example` to `.env` and fill in your GitHub credentials:

```bash
cp .env.example .env
```

Update the values:
```env
GITHUB_TOKEN=ghp_your_github_personal_access_token_here
GITHUB_WEBHOOK_SECRET=your_webhook_secret_here
AUTO_REVIEW_ENABLED=true
REVIEW_ON_READY_FOR_REVIEW=true
REVIEW_ON_NEW_COMMITS=true
```

### 3. Create a GitHub Personal Access Token

1. Go to GitHub Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Click "Generate new token (classic)"
3. Select scopes:
   - `repo` (Full control of private repositories)
   - `write:discussion` (Read and write discussions)
4. Generate and copy the token to your `.env` file

### 4. Set Up GitHub Webhook

1. Go to your repository → Settings → Webhooks → Add webhook
2. Configure:
   - **Payload URL**: `https://your-domain.com/webhook/github`
   - **Content type**: `application/json`
   - **Secret**: Generate a random secret and add to `.env`
   - **Events**: Select:
     - Pull requests
     - Pull request reviews
     - Pull request review comments
     - Pushes
3. Click "Add webhook"

## Running the Bot

### Development

```bash
# With hot reload
uv run uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

# Or directly
uv run python src/main.py
```

### Production

```bash
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## API Endpoints

- `GET /` - Root endpoint
- `GET /health` - Health check
- `POST /webhook/github` - GitHub webhook handler

## Testing Webhooks Locally

Use ngrok to expose your local server:

```bash
ngrok http 8000
```

Then use the ngrok URL for your webhook configuration.

## Development

### Code Formatting & Linting

```bash
# Check linting
ruff check .

# Auto-fix
ruff check --fix .

# Format code
ruff format .
```

### Project Structure

```
np-code-review/
├── src/
│   ├── main.py              # FastAPI app with webhook handlers
│   └── config/
│       ├── __init__.py
│       └── config.py        # Configuration with Pydantic
├── .env.example             # Environment variables template
├── pyproject.toml           # Dependencies and tool config
└── README.md
```

## Event Handlers

### Currently Supported

- **pull_request**: Triggered on PR open, synchronize, ready_for_review
- **pull_request_review**: Review submitted
- **pull_request_review_comment**: Review comment added
- **push**: Code pushed to repository
- **ping**: Webhook test event

## Next Steps

1. Implement actual code review logic in `trigger_code_review()`
2. Add AI/LLM integration for intelligent code analysis
3. Add support for review comments on specific lines
4. Implement code quality checks (linting, security scans)
5. Add unit tests
6. Set up CI/CD pipeline

## License

MIT