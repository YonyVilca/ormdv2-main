import bcrypt
from typing import Union

def hash_password(password: str, rounds: int = 12) -> str:
    salt = bcrypt.gensalt(rounds=rounds)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: Union[str, bytes, memoryview]) -> bool:
    if isinstance(hashed_password, memoryview):
        hp_bytes = bytes(hashed_password)
    elif isinstance(hashed_password, bytes):
        hp_bytes = hashed_password
    elif isinstance(hashed_password, str):
        hp_bytes = hashed_password.encode("utf-8")  # "$2b$..." → bytes
    else:
        return False
    return bcrypt.checkpw(plain_password.encode("utf-8"), hp_bytes)
