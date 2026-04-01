from re import compile

_DEFAUlT_IGNORE_PATTERNS = [
    # Dependencies
    r"^node_modules/",
    r"^vendor/",
    r"^packages/",
    r"^bower_components/",
    # Build outputs
    r"^dist/",
    r"^build/",
    r"^out/",
    r"^target/",
    r"^bin/",
    r"^obj/",
    r"^\.next/",
    r"^\.nuxt/",
    r"^\.output/",
    # Version control
    r"^\.git/",
    r"^\.svn/",
    r"^\.hg/",
    # IDE/Editor
    r"^\.vscode/",
    r"^\.idea/",
    r"^\.vs/",
    r"^\.eclipse/",
    r"^\.settings/",
    r".*\.swp$",
    r".*\.swo$",
    r".*~$",
    # Python
    r"^__pycache__/",
    r"^\.pytest_cache/",
    r"^\.mypy_cache/",
    r"^\.tox/",
    r"^\.eggs/",
    r"^\.venv/",
    r"^venv/",
    r"^\.Python$",
    r"^pip-log\.txt$",
    r"^pip-delete-this-directory\.txt$",
    r".*\.pyc$",
    r".*\.pyo$",
    r".*\.pyd$",
    r"^\.coverage$",
    r"^\.coverage\..*$",
    r"^htmlcov/",
    r"^\.pytest_cache/",
    r"^\.ruff_cache/",
    # JavaScript/Node
    r"^yarn\.lock$",
    r"^package-lock\.json$",
    r"^pnpm-lock\.yaml$",
    r"^\.yarn/",
    r"^\.pnp\..*$",
    # Logs
    r"^logs/",
    r".*\.log$",
    r"^npm-debug\.log.*$",
    r"^yarn-debug\.log.*$",
    r"^yarn-error\.log.*$",
    # OS
    r"^\.DS_Store$",
    r"^Thumbs\.db$",
    r"^desktop\.ini$",
    # Config files (typically don't need code review)
    r"^\.gitignore$",
    r"^\.gitattributes$",
    r"^\.editorconfig$",
    r"^\.prettierrc.*$",
    r"^\.eslintrc.*$",
    r"^\.stylelintrc.*$",
    # Lock files
    r"^Gemfile\.lock$",
    r"^Cargo\.lock$",
    r"^poetry\.lock$",
    r"^Pipfile\.lock$",
    # Compiled/minified files
    r".*\.min\.js$",
    r".*\.min\.css$",
    r".*\.bundle\.js$",
    r".*\.chunk\.js$",
    # Documentation generated files
    r"^site/",
    r"^docs/_build/",
    r"^\.docusaurus/",
    # Test coverage
    r"^coverage/",
    r"^\.nyc_output/",
    # Temporary files
    r"^tmp/",
    r"^temp/",
    r".*\.tmp$",
    r".*\.bak$",
    r".*\.cache$",
]

IGNORE_PATTERNS = [compile(pattern) for pattern in _DEFAUlT_IGNORE_PATTERNS]
