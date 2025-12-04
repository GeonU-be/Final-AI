import os
from dotenv import load_dotenv

# .env 불러오기
load_dotenv()

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