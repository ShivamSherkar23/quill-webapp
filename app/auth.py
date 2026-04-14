import os

import bcrypt
from itsdangerous import URLSafeTimedSerializer

SECRET_KEY = os.environ["SECRET_KEY"]

serializer = URLSafeTimedSerializer(SECRET_KEY)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def create_session_token(user_id: int) -> str:
    return serializer.dumps({"user_id": user_id})


def decode_session_token(token: str) -> dict | None:
    try:
        return serializer.loads(token, max_age=86400)  # 24h
    except Exception:
        return None
