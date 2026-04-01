import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.services.code_review.code_review_service import CodeReviewService
from src.config import Config


class MockFile:    
    def __init__(self, filename: str, patch: str):
        self.filename = filename
        self.patch = patch
        self.additions = len([l for l in patch.splitlines() if l.startswith("+")])
        self.deletions = len([l for l in patch.splitlines() if l.startswith("-")])


def test_filter_files_detects_pyc_files():
    """Test that .pyc files are detected as unwanted."""
    config = Config()
    service = CodeReviewService(config)
    
    # Create a normal Python source file
    source_file = MockFile("module.py", "def hello():\n    print('hello')\n")
    
    # Create a .pyc file (compiled Python)
    pyc_file = MockFile("module.pyc", "binary content here")
    
    # Create a .pyo file (optimized Python)
    pyo_file = MockFile("utils.pyo", "binary content here")
    
    files = [source_file, pyc_file, pyo_file]
    
    reviewable, skipped_patterns, skipped_large, unwanted_files, _gi = service._filter_files(files)
    
    # Verify results
    assert len(reviewable) == 1, f"Expected 1 reviewable file, got {len(reviewable)}"
    assert len(unwanted_files) == 2, f"Expected 2 unwanted files, got {len(unwanted_files)}"
    assert len(skipped_patterns) == 0, f"Expected 0 skipped by pattern, got {len(skipped_patterns)}"
    assert len(skipped_large) == 0, f"Expected 0 skipped large files, got {len(skipped_large)}"
    
    # Verify the correct files
    assert reviewable[0].filename == "module.py", "Source file should be reviewable"
    
    unwanted_names = [f.filename for f in unwanted_files]
    assert "module.pyc" in unwanted_names, ".pyc file should be unwanted"
    assert "utils.pyo" in unwanted_names, ".pyo file should be unwanted"
    
    print("✅ Test passed: .pyc and .pyo files are correctly detected as unwanted")
    print(f"   - Reviewable: {[f.filename for f in reviewable]}")
    print(f"   - Unwanted: {unwanted_names}")


def test_filter_files_detects_compiled_files():
    """Test that various compiled/binary files are detected as unwanted."""
    config = Config()
    service = CodeReviewService(config)
    
    # Create source files
    js_source = MockFile("app.js", "console.log('hello');")
    java_source = MockFile("Main.java", "public class Main {}")
    
    # Create compiled/minified files
    minified_js = MockFile("app.min.js", "console.log('hello');")
    bundle_js = MockFile("app.bundle.js", "// webpack bundle")
    class_file = MockFile("Main.class", "binary content")
    dll_file = MockFile("library.dll", "binary content")
    
    files = [js_source, java_source, minified_js, bundle_js, class_file, dll_file]
    
    reviewable, skipped_patterns, skipped_large, unwanted_files, _gi = service._filter_files(files)
    
    # Verify results
    assert len(reviewable) == 2, f"Expected 2 reviewable files, got {len(reviewable)}"
    assert len(unwanted_files) == 4, f"Expected 4 unwanted files, got {len(unwanted_files)}"
    
    # Verify source files are reviewable
    reviewable_names = [f.filename for f in reviewable]
    assert "app.js" in reviewable_names, "JavaScript source should be reviewable"
    assert "Main.java" in reviewable_names, "Java source should be reviewable"
    
    # Verify compiled files are unwanted
    unwanted_names = [f.filename for f in unwanted_files]
    assert "app.min.js" in unwanted_names, "Minified JS should be unwanted"
    assert "app.bundle.js" in unwanted_names, "Bundle JS should be unwanted"
    assert "Main.class" in unwanted_names, "Java class file should be unwanted"
    assert "library.dll" in unwanted_names, "DLL file should be unwanted"
    
    print("✅ Test passed: Compiled and minified files are correctly detected as unwanted")
    print(f"   - Reviewable: {reviewable_names}")
    print(f"   - Unwanted: {unwanted_names}")


def test_filter_files_mixed_scenario():
    """Test a realistic scenario with normal, skipped, large, and unwanted files."""
    config = Config()
    service = CodeReviewService(config)
    
    # Normal reviewable file
    normal_file = MockFile("src/app.py", "def main():\n    pass\n")
    
    # Unwanted file (.pyc)
    pyc_file = MockFile("src/__pycache__/app.cpython-39.pyc", "binary content")
    
    # Skipped by pattern (lock file)
    lock_file = MockFile("package-lock.json", '{"dependencies": {}}')
    
    # Large file
    large_file = MockFile("big.py", "x = 1\n" * 100000)
    
    # Another unwanted file (.pyd)
    pyd_file = MockFile("extension.pyd", "binary content")
    
    files = [normal_file, pyc_file, lock_file, large_file, pyd_file]
    
    reviewable, skipped_patterns, skipped_large, unwanted_files, _gi = service._filter_files(files)
    
    # Verify each category
    assert len(reviewable) == 1, f"Expected 1 reviewable file"
    assert len(unwanted_files) == 2, f"Expected 2 unwanted files"
    assert len(skipped_patterns) == 1, f"Expected 1 skipped by pattern"
    assert len(skipped_large) == 1, f"Expected 1 large file"
    
    assert reviewable[0].filename == "src/app.py"
    
    unwanted_names = [f.filename for f in unwanted_files]
    assert "src/__pycache__/app.cpython-39.pyc" in unwanted_names
    assert "extension.pyd" in unwanted_names
    
    assert "package-lock.json" in skipped_patterns
    assert skipped_large[0]['filename'] == "big.py"
    
    print("✅ Test passed: All file categories are correctly handled")
    print(f"   - Reviewable: {[f.filename for f in reviewable]}")
    print(f"   - Unwanted: {unwanted_names}")
    print(f"   - Skipped (pattern): {skipped_patterns}")
    print(f"   - Skipped (large): {[f['filename'] for f in skipped_large]}")


