echo "Formatting Python code"
uvx ruff format
uvx ruff check --fix

echo "Checking Python code"
uvx ruff check
uvx ruff format --diff

echo "Formatting Terraform code"
cd terraform
terraform fmt -recursive -check
cd ..