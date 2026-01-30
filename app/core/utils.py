import bcrypt
import hashlib

def get_password_hash(password: str) -> str:
    sha256_hex = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return bcrypt.hashpw(sha256_hex.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    sha256_hex = hashlib.sha256(plain_password.encode("utf-8")).hexdigest()
    return bcrypt.checkpw(sha256_hex.encode('utf-8'), hashed_password.encode('utf-8'))
