import pytest
from datetime import timedelta
from app.core import security

def test_hash_password():
    password = "secret_password"
    hashed = security.get_hash(password)
    assert hashed != password
    assert security.verify_hash(password, hashed) is True
    assert security.verify_hash("wrong_password", hashed) is False

def test_create_access_token():
    subject = "test_user_id"
    expires_delta = timedelta(minutes=15)
    token = security.create_access_token(subject, expires_delta)
    assert isinstance(token, str)
    
    payload = security.verify_token(token)
    assert payload is not None
    assert payload["sub"] == subject
    assert payload["type"] == "access"

def test_create_refresh_token():
    subject = "test_user_id"
    expires_delta = timedelta(days=7)
    token = security.create_refresh_token(subject, expires_delta)
    assert isinstance(token, str)
    
    payload = security.verify_token(token)
    assert payload is not None
    assert payload["sub"] == subject
    assert payload["type"] == "refresh"

def test_expired_token():
    subject = "test_user_id"
    expires_delta = timedelta(minutes=-1)
    token = security.create_access_token(subject, expires_delta)
    
    payload = security.verify_token(token)
    assert payload is None

def test_invalid_token():
    payload = security.verify_token("invalid_token_string")
    assert payload is None
