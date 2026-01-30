import json
import bcrypt
import hashlib
from pyseto import Key, Paseto
from typing import Any, Optional
from datetime import datetime, timedelta, timezone
from app.core.config import settings

def get_hash(text: str) -> str:
    pre_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return bcrypt.hashpw(pre_hash.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_hash(plain_text: str, hashed_text: str) -> bool:
    pre_hash = hashlib.sha256(plain_text.encode("utf-8")).hexdigest()
    return bcrypt.checkpw(pre_hash.encode('utf-8'), hashed_text.encode('utf-8'))

def _get_paseto_key() -> Key:
    key_material = hashlib.sha256(settings.SECRET_KEY.encode('utf-8')).digest()
    return Key.new(version=4, purpose="local", key=key_material)

def create_token(subject: str, expires_delta: timedelta, token_type: str) -> str:
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {
        "exp": expire.isoformat(), 
        "sub": str(subject), 
        "type": token_type,
        "iat": datetime.now(timezone.utc).isoformat()
    }
    key = _get_paseto_key()
    return Paseto.new().encode(key, payload).decode('utf-8')

def verify_token(token: str) -> Optional[dict[str, Any]]:
    key = _get_paseto_key()
    try:
        decoded = Paseto.new().decode(key, token)
        payload_dict = json.loads(decoded.payload)
        
        if "exp" in payload_dict:
            exp = datetime.fromisoformat(payload_dict["exp"])
            if datetime.now(timezone.utc) > exp:
                return None
                
        return payload_dict
    except Exception:
        return None

def create_access_token(subject: str | Any, expires_delta: timedelta) -> str:
    return create_token(str(subject), expires_delta, "access")

def create_refresh_token(subject: str | Any, expires_delta: timedelta) -> str:
    return create_token(str(subject), expires_delta, "refresh")
