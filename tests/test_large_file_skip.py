import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.services.code_review.code_review_service import CodeReviewService
from src.services.code_review.constants import MAX_TOKENS_PER_FILE
from src.config import Config


class MockFile:    
    def __init__(self, filename: str, patch: str):
        self.filename = filename
        self.patch = patch
        self.additions = len([l for l in patch.splitlines() if l.startswith("+")])
        self.deletions = len([l for l in patch.splitlines() if l.startswith("-")])


def test_filter_files_skips_large_files():
    config = Config()
    service = CodeReviewService(config)
    
    # Create a small file (under limit)
    small_patch = "def hello():\n    print('hello')\n" * 100  # ~2,400 chars = 600 tokens
    small_file = MockFile("small.py", small_patch)
    
    # Create a large file (over limit)
    large_patch = "def hello():\n    print('hello')\n" * 20000  # ~480,000 chars = 120,000 tokens
    large_file = MockFile("large.py", large_patch)
    
    # Create a medium file (under limit)
    medium_patch = "def hello():\n    print('hello')\n" * 1000  # ~24,000 chars = 6,000 tokens
    medium_file = MockFile("medium.py", medium_patch)
    
    files = [small_file, large_file, medium_file]
    
    reviewable, skipped_patterns, skipped_large, unwanted_files, _gi = service._filter_files(files)
    
    # Verify results
    assert len(reviewable) == 2, f"Expected 2 reviewable files, got {len(reviewable)}"
    assert len(skipped_large) == 1, f"Expected 1 skipped large file, got {len(skipped_large)}"
    assert len(skipped_patterns) == 0, f"Expected 0 skipped by pattern, got {len(skipped_patterns)}"
    assert len(unwanted_files) == 0, f"Expected 0 unwanted files, got {len(unwanted_files)}"
    
    # Verify the correct files
    reviewable_names = [f.filename for f in reviewable]
    assert "small.py" in reviewable_names, "small.py should be reviewable"
    assert "medium.py" in reviewable_names, "medium.py should be reviewable"
    assert "large.py" not in reviewable_names, "large.py should NOT be reviewable"
    
    # Verify skipped large file info
    assert skipped_large[0]['filename'] == "large.py"
    assert skipped_large[0]['tokens'] > MAX_TOKENS_PER_FILE
    
    print("✅ Test passed: Large files are correctly skipped")
    print(f"   - Reviewable: {reviewable_names}")
    print(f"   - Skipped (large): {[f['filename'] for f in skipped_large]} (~{skipped_large[0]['tokens']:,} tokens)")


def test_filter_files_with_ignored_patterns():
    """Test that both pattern and size filtering work together."""
    config = Config()
    service = CodeReviewService(config)
    
    # Create a lock file (should be skipped by pattern)
    lock_file = MockFile("package-lock.json", '{"dependencies": {}}' * 1000)
    
    # Create a large file (should be skipped by size)
    large_file = MockFile("huge.py", "x = 1\n" * 100000)
    
    # Create a normal file
    normal_file = MockFile("app.py", "def main():\n    pass\n")
    
    files = [lock_file, large_file, normal_file]
    
    reviewable, skipped_patterns, skipped_large, unwanted_files, _gi = service._filter_files(files)
    
    # Verify results
    assert len(reviewable) == 1, f"Expected 1 reviewable file, got {len(reviewable)}"
    assert len(skipped_patterns) == 1, f"Expected 1 skipped by pattern, got {len(skipped_patterns)}"
    assert len(skipped_large) == 1, f"Expected 1 skipped large file, got {len(skipped_large)}"
    assert len(unwanted_files) == 0, f"Expected 0 unwanted files, got {len(unwanted_files)}"
    
    assert reviewable[0].filename == "app.py"
    assert "package-lock.json" in skipped_patterns
    assert skipped_large[0]['filename'] == "huge.py"
    
    print("✅ Test passed: Both pattern and size filtering work correctly")
    print(f"   - Reviewable: {[f.filename for f in reviewable]}")
    print(f"   - Skipped (pattern): {skipped_patterns}")
    print(f"   - Skipped (large): {[f['filename'] for f in skipped_large]}")


def test_filter_files_edge_case_at_limit():
    config = Config()
    service = CodeReviewService(config)
    
    # Create a file exactly at the limit
    chars_at_limit = MAX_TOKENS_PER_FILE * 4
    at_limit_file = MockFile("at_limit.py", "x" * chars_at_limit)
    
    # Create a file just over the limit
    over_limit_file = MockFile("over_limit.py", "x" * (chars_at_limit + 100))
    
    # Create a file just under the limit
    under_limit_file = MockFile("under_limit.py", "x" * (chars_at_limit - 100))
    
    files = [at_limit_file, over_limit_file, under_limit_file]
    
    reviewable, skipped_patterns, skipped_large, unwanted_files, _gi = service._filter_files(files)
    
    # At limit should be reviewable, over limit should be skipped
    reviewable_names = [f.filename for f in reviewable]
    
    assert "at_limit.py" in reviewable_names, "File at limit should be reviewable"
    assert "under_limit.py" in reviewable_names, "File under limit should be reviewable"
    assert "over_limit.py" not in reviewable_names, "File over limit should be skipped"
    assert len(skipped_large) == 1
    assert skipped_large[0]['filename'] == "over_limit.py"
    
   