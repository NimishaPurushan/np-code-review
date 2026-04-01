import pytest

from src.utils.ignore_patterns import is_ignored_file
from src.utils.ignore_patterns.patterns import IGNORE_PATTERNS


class TestIgnorePatterns:
    """Test ignore patterns for code review."""

    def test_ignore_patterns_compiled(self):
        """Test that ignore patterns are compiled regex objects."""
        assert len(IGNORE_PATTERNS) > 0
        for pattern in IGNORE_PATTERNS:
            assert hasattr(pattern, "match")

    # Dependencies
    def test_ignore_node_modules(self):
        assert is_ignored_file("node_modules/package/index.js")
        assert is_ignored_file("node_modules/package.json")

    def test_ignore_vendor(self):
        assert is_ignored_file("vendor/lib.php")
        assert is_ignored_file("vendor/autoload.php")

    def test_ignore_packages(self):
        assert is_ignored_file("packages/lib/index.js")

    def test_ignore_bower_components(self):
        assert is_ignored_file("bower_components/jquery/dist/jquery.js")

    # Build outputs
    def test_ignore_dist(self):
        assert is_ignored_file("dist/bundle.js")
        assert is_ignored_file("dist/index.html")

    def test_ignore_dist_nested_monorepo_path(self):
        assert is_ignored_file("apps/web/dist/bundle.js")
        assert is_ignored_file("packages/ui/dist/index.js")

    def test_ignore_build(self):
        assert is_ignored_file("build/main.js")
        assert is_ignored_file("build/output/file.txt")

    def test_ignore_out(self):
        assert is_ignored_file("out/compiled.js")

    def test_ignore_target(self):
        assert is_ignored_file("target/classes/Main.class")

    def test_ignore_bin(self):
        assert is_ignored_file("bin/executable")

    def test_ignore_obj(self):
        assert is_ignored_file("obj/Debug/file.obj")

    def test_ignore_next(self):
        assert is_ignored_file(".next/build-manifest.json")

    def test_ignore_nuxt(self):
        assert is_ignored_file(".nuxt/config.json")

    def test_ignore_output(self):
        assert is_ignored_file(".output/server/index.js")

    # Version control
    def test_ignore_git(self):
        assert is_ignored_file(".git/config")
        assert is_ignored_file(".git/HEAD")

    def test_ignore_svn(self):
        assert is_ignored_file(".svn/entries")

    def test_ignore_hg(self):
        assert is_ignored_file(".hg/store")

    # IDE/Editor
    def test_ignore_vscode(self):
        assert is_ignored_file(".vscode/settings.json")
        assert is_ignored_file(".vscode/launch.json")

    def test_ignore_idea(self):
        assert is_ignored_file(".idea/workspace.xml")

    def test_ignore_vs(self):
        assert is_ignored_file(".vs/config/applicationhost.config")

    def test_ignore_eclipse(self):
        assert is_ignored_file(".eclipse/settings.xml")

    def test_ignore_settings(self):
        assert is_ignored_file(".settings/org.eclipse.core.resources.prefs")

    def test_ignore_swap_files(self):
        assert is_ignored_file("file.swp")
        assert is_ignored_file("src/main.py.swp")
        assert is_ignored_file("test.swo")
        assert is_ignored_file("backup~")

    # Python
    def test_ignore_pycache(self):
        assert is_ignored_file("__pycache__/module.cpython-39.pyc")

    def test_ignore_pytest_cache(self):
        assert is_ignored_file(".pytest_cache/v/cache/lastfailed")

    def test_ignore_mypy_cache(self):
        assert is_ignored_file(".mypy_cache/3.9/module.meta.json")

    def test_ignore_tox(self):
        assert is_ignored_file(".tox/py39/lib/python3.9/site-packages")

    def test_ignore_eggs(self):
        assert is_ignored_file(".eggs/setuptools-1.0.egg")

    def test_ignore_venv(self):
        assert is_ignored_file(".venv/bin/python")
        assert is_ignored_file("venv/lib/python3.9")
        assert not is_ignored_file("env/Scripts/activate")
        assert not is_ignored_file(".env/pyvenv.cfg")

    def test_ignore_python_binary(self):
        assert is_ignored_file(".Python")

    def test_ignore_pip_logs(self):
        assert is_ignored_file("pip-log.txt")
        assert is_ignored_file("pip-delete-this-directory.txt")

    def test_ignore_pyc_files(self):
        assert is_ignored_file("module.pyc")
        assert is_ignored_file("src/utils/helper.pyc")
        assert is_ignored_file("test.pyo")
        assert is_ignored_file("lib.pyd")

    def test_ignore_coverage(self):
        assert is_ignored_file(".coverage")
        assert is_ignored_file(".coverage.linux")
        assert is_ignored_file("htmlcov/index.html")

    def test_ignore_ruff_cache(self):
        assert is_ignored_file(".ruff_cache/file.json")

    # JavaScript/Node
    def test_ignore_lock_files(self):
        assert is_ignored_file("yarn.lock")
        assert is_ignored_file("package-lock.json")
        assert is_ignored_file("npm-shrinkwrap.json")
        assert is_ignored_file("pnpm-lock.yaml")

    def test_ignore_yarn(self):
        assert is_ignored_file(".yarn/cache/package.zip")
        assert is_ignored_file(".pnp.js")
        assert is_ignored_file(".pnp.cjs")

    # Logs
    def test_ignore_logs_folder(self):
        assert is_ignored_file("logs/app.log")
        assert is_ignored_file("logs/error.log")

    def test_ignore_log_files(self):
        assert is_ignored_file("error.log")
        assert is_ignored_file("app.log")
        assert is_ignored_file("npm-debug.log")
        assert is_ignored_file("yarn-debug.log.1234")
        assert is_ignored_file("yarn-error.log")

    # OS
    def test_ignore_os_files(self):
        assert is_ignored_file(".DS_Store")
        assert is_ignored_file("Thumbs.db")
        assert is_ignored_file("desktop.ini")

    # Config files
    def test_ignore_config_files(self):
        assert is_ignored_file(".gitignore")
        assert is_ignored_file(".gitattributes")
        assert is_ignored_file(".editorconfig")
        assert is_ignored_file(".prettierrc")
        assert is_ignored_file(".prettierrc.json")
        assert is_ignored_file(".eslintrc.js")
        assert is_ignored_file(".stylelintrc.yml")

    # Lock files
    def test_ignore_ruby_lock(self):
        assert is_ignored_file("Gemfile.lock")

    def test_ignore_rust_lock(self):
        assert is_ignored_file("Cargo.lock")

    def test_ignore_python_lock_files(self):
        assert is_ignored_file("poetry.lock")
        assert is_ignored_file("Pipfile.lock")
        assert is_ignored_file("uv.lock")

    # Compiled/minified files
    def test_ignore_minified_files(self):
        assert is_ignored_file("app.min.js")
        assert is_ignored_file("styles.min.css")
        assert is_ignored_file("vendor.bundle.js")
        assert is_ignored_file("main.chunk.js")

    # Documentation generated files
    def test_ignore_docs(self):
        assert is_ignored_file("site/index.html")
        assert is_ignored_file("docs/_build/html/index.html")
        assert is_ignored_file(".docusaurus/client-modules.js")

    # Test coverage
    def test_ignore_coverage_folders(self):
        assert is_ignored_file("coverage/lcov-report/index.html")
        assert is_ignored_file(".nyc_output/processinfo/index.json")

    # Temporary files
    def test_ignore_temp_files(self):
        assert is_ignored_file("tmp/upload.txt")
        assert is_ignored_file("temp/cache.json")
        assert is_ignored_file("file.tmp")
        assert is_ignored_file("backup.bak")
        assert is_ignored_file("data.cache")

    # Files that should NOT be ignored
    def test_dont_ignore_source_files(self):
        assert not is_ignored_file("src/main.py")
        assert not is_ignored_file("src/utils/helper.py")
        assert not is_ignored_file("app.js")
        assert not is_ignored_file("index.html")
        assert not is_ignored_file("styles.css")

    def test_dont_ignore_test_files(self):
        assert not is_ignored_file("tests/test_main.py")
        assert not is_ignored_file("test_utils.py")

    def test_dont_ignore_config_source(self):
        assert not is_ignored_file("config.py")
        assert not is_ignored_file("settings.json")

    def test_dont_ignore_readme(self):
        assert not is_ignored_file("README.md")
        assert not is_ignored_file("docs/guide.md")

    def test_dont_ignore_package_files(self):
        assert not is_ignored_file("package.json")
        assert not is_ignored_file("pyproject.toml")
        assert not is_ignored_file("Cargo.toml")
        assert not is_ignored_file("Gemfile")

    # Edge cases
    def test_nested_paths(self):
        assert is_ignored_file("node_modules/package/node_modules/nested/file.js")
        # Nested build folders inside src should NOT be ignored (only root-level)
        assert not is_ignored_file("src/build/output.js")

    def test_deep_nested_source(self):
        assert not is_ignored_file("src/components/ui/Button.tsx")
        assert not is_ignored_file("lib/utils/helpers/format.ts")

    def test_similar_but_not_ignored(self):
        # These start with the pattern but are not at the root
        assert not is_ignored_file("src/node_modules.js")
        assert not is_ignored_file("src/build.py")
        assert not is_ignored_file("my_dist.py")

    def test_empty_string(self):
        assert not is_ignored_file("")

    def test_relative_path_notation(self):
        assert not is_ignored_file("./src/main.py")
        assert not is_ignored_file("../utils/helper.py")
