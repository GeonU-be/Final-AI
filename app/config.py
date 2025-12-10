import os
from typing import List


def _get_int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} 환경 변수는 정수여야 합니다.") from exc


def _get_float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} 환경 변수는 숫자여야 합니다.") from exc


def _get_list_env(name: str) -> List[str]:
    raw = os.getenv(name, "")
    return [item.strip() for item in raw.split(",") if item.strip()]


# FastAPI CORS 허용 origin
FASTAPI_ALLOWED_ORIGINS: List[str] = _get_list_env("FASTAPI_ALLOWED_ORIGINS")

# 로깅 관련 설정
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO").upper()
JAVA_SERVER_ADDRESS: str | None = os.getenv("JAVA_SERVER_ADDRESS")
LOG_USER_ID: int = _get_int_env("LOG_USER_ID", 1)
LOG_HTTP_TIMEOUT: float = _get_float_env("LOG_HTTP_TIMEOUT", 5.0)

# 네이버 아이디 (임시)
NAVER_ID: str = os.getenv("NAVER_ID")
NAVER_PW: str = os.getenv("NAVER_PW")
SESSION_FILE_DIR = "./naver/login_session.json"

# Twitter 관련 설정
TWITTER_API_KEY: str | None = os.getenv("TWITTER_API_KEY")
TWITTER_API_SECRET: str | None = os.getenv("TWITTER_API_SECRET")
TWITTER_ACCESS_TOKEN: str | None = os.getenv("TWITTER_ACCESS_TOKEN")
TWITTER_ACCESS_SECRET: str | None = os.getenv("TWITTER_ACCESS_SECRET")
TWITTER_BEARER_TOKEN: str | None = os.getenv("TWITTER_BEARER_TOKEN")
TWITTER_CALLBACK_URL: str | None = os.getenv("TWITTER_CALLBACK_URL")

# 레이트리밋 대기 옵션은 환경에서 토글하지 않고 기본 True로 고정
TWITTER_WAIT_ON_RATE_LIMIT: bool = True
TWITTER_MAX_MEDIA_CONCURRENCY: int = _get_int_env(
    "TWITTER_MAX_MEDIA_CONCURRENCY", 2
)
