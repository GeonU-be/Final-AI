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

# 프로젝트 루트 디렉토리
# settings.py → app/config → app → PROJECT_ROOT
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))

# /data 디렉토리
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

# CNN 추천 시스템 파일 디렉토리
CNN_DIR = os.path.join(DATA_DIR, "cnn")

# 파일 경로
ID_MAP_PATH = os.path.join(CNN_DIR, "id_map.json")
EMB_MATRIX_PATH = os.path.join(CNN_DIR, "emb_matrix.npy")
FAISS_INDEX_PATH = os.path.join(CNN_DIR, "faiss_index.bin")

# 모델 파일 디렉토리 (optional)
MODEL_DIR = os.path.join(DATA_DIR, "models")

# 환경 변수 예시
NAVER_LOGIN_ID = os.getenv("NAVER_LOGIN_ID")
TWITTER_CLIENT_ID = os.getenv("TWITTER_CLIENT_ID")