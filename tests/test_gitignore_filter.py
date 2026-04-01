from unittest.mock import Mock

import pytest
from pathspec import PathSpec

from src.services.code_review.code_review_service import CodeReviewService
from src.utils.ignore_patterns.gitignore import (
    normalize_repo_relative_path,
    parse_gitignore_spec,
    path_is_ignored_by_spec,
)


def test_normalize_repo_relative_path():
    assert normalize_repo_relative_path("./src/a.py") == "src/a.py"
    assert normalize_repo_relative_path("x\\y.py") == "x/y.py"


def test_parse_gitignore_spec_skips_comments_and_empty():
    assert parse_gitignore_spec("") is None
    assert parse_gitignore_spec("# only comments\n\n  # x\n") is None


def test_path_is_ignored_by_spec():
    spec = PathSpec.from_lines("gitignore", [".env", "dist/", "!dist/keep.txt"])
    assert path_is_ignored_by_spec(spec, ".env")
    assert path_is_ignored_by_spec(spec, "apps/web/dist/out.js")
    assert not path_is_ignored_by_spec(spec, "dist/keep.txt")
    assert not path_is_ignored_by_spec(spec, "src/main.py")


@pytest.fixture
def filter_service():
    return CodeReviewService(Mock())


def _mock_file(name: str, patch: str = "@@ -0,0 +1 @@\n+a\n"):
    f = Mock()
    f.filename = name
    f.patch = patch
    return f


def test_filter_files_gitignored_tracked_not_reviewed(filter_service):
    spec = PathSpec.from_lines("gitignore", [".env", "*.local"])
    src = _mock_file("src/app.py")
    env = _mock_file(".env")
    local = _mock_file("config.local")

    rev, skipped, large, unwanted, gitignored = filter_service._filter_files(
        [src, env, local], gitignore_spec=spec
    )

    assert [f.filename for f in rev] == ["src/app.py"]
    assert {f.filename for f in gitignored} == {".env", "config.local"}
    assert unwanted == []


def test_filter_files_unwanted_before_gitignore(filter_service):
    spec = PathSpec.from_lines("gitignore", ["*.pyc"])
    pyc = _mock_file("x.pyc", patch="binary\n")

    _rev, _sk, _lg, unwanted, gitignored = filter_service._filter_files(
        [pyc], gitignore_spec=spec
    )

    assert len(unwanted) == 1
    assert gitignored == []
