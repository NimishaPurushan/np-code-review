import pytest
from src.utils.secret_scanner import detect_secrets, calculate_shannon_entropy


def test_detect_aws_access_key():
    text = "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE"
    matches = detect_secrets(text)
    
    assert len(matches) == 1
    assert matches[0].type == "aws_access_key"
    assert "AKIA" in matches[0].value
    assert matches[0].confidence == 1.0


def test_detect_aws_secret_key():
    text = "aws_secret_access_key = 'wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'"
    matches = detect_secrets(text)
    
    assert len(matches) >= 1
    assert any(m.type == "aws_secret_key" for m in matches)


def test_detect_github_token():
    text = "token = 'ghp_1234567890abcdefghijklmnopqrstuvwxyz'"
    matches = detect_secrets(text, enable_entropy=False)
    
    assert len(matches) == 1
    assert matches[0].type == "github_token"


def test_detect_slack_webhook():
    text = "url = 'https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX'"
    matches = detect_secrets(text)
    
    assert len(matches) == 1
    assert matches[0].type == "slack_webhook"


def test_detect_private_key():
    text = "-----BEGIN RSA PRIVATE KEY-----"
    matches = detect_secrets(text)
    
    assert len(matches) == 1
    assert matches[0].type == "private_key_header"


def test_detect_jwt():
    text = "token = eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
    matches = detect_secrets(text, enable_entropy=False)
    
    assert len(matches) == 1
    assert matches[0].type == "jwt"


def test_detect_google_api_key():
    text = "GOOGLE_API_KEY=AIzaSyDaGmWKa4JsXZ-HjGw7ISLn_3namBGewQe"
    matches = detect_secrets(text, enable_entropy=False)
    
    assert len(matches) == 1
    assert matches[0].type == "google_api_key"


def test_detect_multiple_secrets():
    text = """
    AWS_KEY = 'AKIAIOSFODNN7EXAMPLE'
    SLACK_URL = 'https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXX'
    """
    matches = detect_secrets(text)
    
    assert len(matches) >= 2
    types = [m.type for m in matches]
    assert "aws_access_key" in types
    assert "slack_webhook" in types


def test_no_secrets():
    text = """
    username = 'test_user'
    email = 'test@example.com'
    port = 8080
    """
    matches = detect_secrets(text)
    
    assert len(matches) == 0


def test_high_entropy_detection():
    text = "token = 'Kj8mNp3Rq5Tv7Wx9Yz2Ab4Cd6Ef8Gh1Ij3Kl5Mn7Op9Qr1St3Uv5'"
    matches = detect_secrets(text, enable_entropy=True)
    
    entropy_matches = [m for m in matches if m.type == "high_entropy"]
    assert len(entropy_matches) > 0


def test_entropy_disabled():
    text = "token = 'Kj8mNp3Rq5Tv7Wx9Yz2Ab4Cd6Ef8Gh1Ij3Kl5Mn7Op9Qr1St3Uv5'"
    matches = detect_secrets(text, enable_entropy=False)
    
    entropy_matches = [m for m in matches if m.type == "high_entropy"]
    assert len(entropy_matches) == 0


def test_calculate_shannon_entropy_uniform():
    data = "aaaaaaaaaaaaaaaaaaaa"
    entropy = calculate_shannon_entropy(data)
    
    assert abs(entropy - 0.0) < 0.001


def test_calculate_shannon_entropy_random():
    data = "aB3dE9fG2hK5mN8pQ1r"
    entropy = calculate_shannon_entropy(data)
    
    assert entropy > 3.0


def test_calculate_shannon_entropy_empty():
    entropy = calculate_shannon_entropy("")
    
    assert entropy == 0.0


def test_line_number_tracking():
    text = """line 1
line 2
AWS_KEY = 'AKIAIOSFODNN7EXAMPLE'
line 4"""
    matches = detect_secrets(text)
    
    assert matches[0].line_number == 3


def test_column_tracking():
    text = "prefix AWS_KEY = 'AKIAIOSFODNN7EXAMPLE' suffix"
    matches = detect_secrets(text)
    
    assert matches[0].column_start > 0
    assert matches[0].column_end > matches[0].column_start


def test_deduplication():
    text = """
    AWS_KEY = 'AKIAIOSFODNN7EXAMPLE'
    AWS_KEY = 'AKIAIOSFODNN7EXAMPLE'
    """
    matches = detect_secrets(text)
    
    assert len(matches) == 2


def test_multiline_secrets():
    text = """
    config = {
        'aws_key': 'AKIAIOSFODNN7EXAMPLE',
        'github': 'ghp_abcdefghijklmnopqrstuvwxyz1234567890',
        'api_key': 'AIzaSyDaGmWKa4JsXZ-HjGw7ISLn_3namBGewQe'
    }
    """
    matches = detect_secrets(text)
    
    assert len(matches) >= 3


def test_custom_entropy_threshold():
    text = "token = 'Kj8mNp3Rq5Tv7Wx9Yz2Ab4Cd6Ef8Gh1Ij3Kl5Mn7Op9Qr1St3Uv5'"
    
    matches_low = detect_secrets(text, entropy_threshold=3.0)
    matches_high = detect_secrets(text, entropy_threshold=6.0)
    
    assert len(matches_low) >= len(matches_high)


def test_empty_text():
    matches = detect_secrets("")
    
    assert len(matches) == 0


def test_whitespace_only():
    matches = detect_secrets("   \n\t\n   ")
    
    assert len(matches) == 0
