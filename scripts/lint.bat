echo "Formatting Python code"
uvx ruff format
uvx ruff check --fix

echo "Checking Python code"
uvx ruff check
uvx ruff format --diff

echo "Formatting Terraform code"
cd infrastructure
terraform fmt -recursive
cd ..
