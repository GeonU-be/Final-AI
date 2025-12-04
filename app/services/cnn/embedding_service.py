import requests
from io import BytesIO
import numpy as np
from PIL import Image, UnidentifiedImageError
import torch

from app.services.cnn.model_loader import (
    get_model,
    get_preprocess,
    get_embedding_size,
)


def load_and_preprocess(url: str):
    """
    주어진 이미지 URL을 다운로드하고 MobileNetV3에 맞게 텐서로 변환한다.

    기능:
    - URL에서 이미지 다운로드 (timeout 포함)
    - HTTP 오류 처리
    - 이미지 디코딩 오류 처리
    - MobileNet preprocess 변환 수행 (Resize, Normalize)
    - 배치 차원을 포함한 텐서 반환

    Args:
        url (str): 이미지 URL

    Returns:
        torch.Tensor | None
            성공 시 (1, 3, 224, 224) 형태의 텐서 반환
            실패 시 None
    """

    preprocess = get_preprocess()

    try:
        response = requests.get(url, timeout=(3, 7))
        response.raise_for_status()

    except requests.exceptions.Timeout:
        print(f"[Embedding] 이미지 요청 시간 초과: {url}")
        return None

    except requests.exceptions.HTTPError as e:
        print(f"[Embedding] HTTP 오류 발생: {e}")
        return None

    except requests.exceptions.RequestException as e:
        print(f"[Embedding] 네트워크 오류: {e}")
        return None

    # --- 이미지 디코딩 ---
    try:
        img = Image.open(BytesIO(response.content)).convert("RGB")
    except UnidentifiedImageError:
        print(f"[Embedding] 이미지 포맷 오류 (디코딩 불가): {url}")
        return None
    except Exception as e:
        print(f"[Embedding] PIL 디코딩 실패: {e}")
        return None

    # --- 전처리 ---
    try:
        tensor = preprocess(img).unsqueeze(0)  # (1, 3, 224, 224)
        return tensor
    except Exception as e:
        print(f"[Embedding] 전처리 실패: {e}")
        return None



def generate_embedding(url: str):
    """
    주어진 이미지 URL에서 MobileNetV3 feature embedding을 생성한다.
    모델 로드는 model_loader.py에서 자동 처리되므로 여기서는 즉시 사용 가능하다.

    기능:
    - load_and_preprocess()로 이미지 텐서 획득
    - MobileNetV3 Large forward → 960차원 벡터 생성
    - L2 정규화 수행
    - numpy float32 벡터 반환

    Args:
        url (str): 입력 이미지 URL

    Returns:
        np.ndarray | None
            shape = (960,) float32
            실패 시 None
    """

    model = get_model()
    tensor = load_and_preprocess(url)

    if tensor is None:
        return None

    try:
        # MobileNetV3 forward
        with torch.no_grad():
            emb = model(tensor).squeeze().numpy().astype("float32")

        # ---- L2 Normalize ----
        norm = np.linalg.norm(emb)
        if norm == 0:
            print("[Embedding] 임베딩 정규화 실패 (norm=0)")
            return None

        emb = emb / (norm + 1e-10)
        return emb

    except Exception as e:
        print(f"[Embedding] 임베딩 생성 중 오류: {e}")
        return None