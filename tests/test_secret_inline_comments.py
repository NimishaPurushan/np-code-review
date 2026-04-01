

from unittest.mock import Mock
from src.services.code_review.code_review_service import CodeReviewService
from src.config.config import Config


def test_parse_diff_line_numbers_with_secrets():
    
    config = Mock(spec=Config)
    service = CodeReviewService(config)
    
    sample_patch = """@@ -10,7 +10,8 @@ def connect_database():
     def get_connection():
         return connection
     
-    password = "oldpass"
+    # Database credentials
+    password = "super_secret_password_123"
+    api_key = "sk-1234567890abcdef"
     
     def close():
         connection.close()"""
    
    # Test the actual method from CodeReviewService
    line_mapping = service._parse_diff_line_numbers(sample_patch)
    
    # Verify the mapping
    # The patch has added lines at:
    # Line 6 in patch: "+    # Database credentials" -> File line 13
    # Line 7 in patch: "+    password = ..." -> File line 14
    # Line 8 in patch: "+    api_key = ..." -> File line 15
    
    assert 6 in line_mapping, "Comment line should be mapped"
    assert 7 in line_mapping, "Password line should be mapped"
    assert 8 in line_mapping, "API key line should be mapped"
    
    assert line_mapping[6] == 13, "Comment line should map to file line 13"
    assert line_mapping[7] == 14, "Password line should map to file line 14"
    assert line_mapping[8] == 15, "API key line should map to file line 15"


def test_parse_diff_line_numbers_multiple_hunks():
    """Test parsing diff with multiple hunks."""
    
    config = Mock(spec=Config)
    service = CodeReviewService(config)
    
    sample_patch = """@@ -5,3 +5,4 @@ def function1():
     line1 = "test"
     line2 = "test"
+    secret1 = "api-key-123"
     line3 = "test"
@@ -20,2 +21,3 @@ def function2():
     another_line = "test"
+    secret2 = "password-456"
     final_line = "test"
"""
    
    line_mapping = service._parse_diff_line_numbers(sample_patch)
    
    # First hunk starts at line 5, added line is at patch line 4
    # which should map to file line 7
    assert 4 in line_mapping
    assert line_mapping[4] == 7
    
    # Second hunk: added line is at patch line 8 which maps to file line 22
    assert 8 in line_mapping
    assert line_mapping[8] == 22
