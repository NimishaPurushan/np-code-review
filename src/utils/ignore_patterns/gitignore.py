from __future__ import annotations

import logging

from pathspec import PathSpec

logger = logging.getLogger(__name__)


def normalize_repo_relative_path(path: str) -> str:
    p = path.replace("\\", "/").strip()
    while p.startswith("./"):
        p = p[2:]
    return p


def parse_gitignore_spec(content: str) -> PathSpec | None:
    if not content or not content.strip():
        return None
    lines = []
    for line in content.splitlines():
        stripped = line.rstrip()
        if not stripped or stripped.lstrip().startswith("#"):
            continue
        lines.append(stripped)
    if not lines:
        return None
    try:
        return PathSpec.from_lines("gitignore", lines)
    except Exception:
        logger.warning("Could not parse .gitignore; ignoring repo rules", exc_info=True)
        return None


def path_is_ignored_by_spec(spec: PathSpec, repo_relative_path: str) -> bool:
    normalized = normalize_repo_relative_path(repo_relative_path)
    if not normalized:
        return False
    return spec.match_file(normalized)
