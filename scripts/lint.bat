echo "formatting code"
uvx ruff format
uvx ruff check --fix

echo "checking code"
uvx ruff check
uvx ruff format --diff
