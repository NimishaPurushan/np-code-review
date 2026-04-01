import hashlib
import hmac

import pytest

from src.services.github.utils import verify_github_signature


def test_verify_valid_signature():
    payload = b'{"test": "data"}'
    secret = "my_secret_key"
    
    hash_object = hmac.new(secret.encode(), msg=payload, digestmod=hashlib.sha256)
    valid_signature = "sha256=" + hash_object.hexdigest()
    
    assert verify_github_signature(payload, valid_signature, secret) is True


def test_verify_invalid_signature():
    payload = b'{"test": "data"}'
    secret = "my_secret_key"
    invalid_signature = "sha256=invalid_hash_string"
    
    assert verify_github_signature(payload, invalid_signature, secret) is False


def test_verify_wrong_secret():
    payload = b'{"test": "data"}'
    secret = "correct_secret"
    wrong_secret = "wrong_secret"
    
    hash_object = hmac.new(secret.encode(), msg=payload, digestmod=hashlib.sha256)
    signature = "sha256=" + hash_object.hexdigest()
    
    assert verify_github_signature(payload, signature, wrong_secret) is False


def test_verify_empty_payload():
    payload = b''
    secret = "my_secret_key"
    
    hash_object = hmac.new(secret.encode(), msg=payload, digestmod=hashlib.sha256)
    signature = "sha256=" + hash_object.hexdigest()
    
    assert verify_github_signature(payload, signature, secret) is True


def test_verify_missing_sha256_prefix():
    payload = b'{"test": "data"}'
    secret = "my_secret_key"
    
    hash_object = hmac.new(secret.encode(), msg=payload, digestmod=hashlib.sha256)
    signature_without_prefix = hash_object.hexdigest()
    
    assert verify_github_signature(payload, signature_without_prefix, secret) is False


def test_verify_different_payload():
    payload1 = b'{"test": "data1"}'
    payload2 = b'{"test": "data2"}'
    secret = "my_secret_key"
    
    hash_object = hmac.new(secret.encode(), msg=payload1, digestmod=hashlib.sha256)
    signature = "sha256=" + hash_object.hexdigest()
    
    assert verify_github_signature(payload2, signature, secret) is False


def test_verify_real_world_example():
    payload = b'{"action":"opened","number":123,"pull_request":{"id":1}}'
    secret = "webhook_secret_123"
    
    hash_object = hmac.new(secret.encode(), msg=payload, digestmod=hashlib.sha256)
    signature = "sha256=" + hash_object.hexdigest()
    
    assert verify_github_signature(payload, signature, secret) is True
    assert verify_github_signature(payload, signature, "different_secret") is False
