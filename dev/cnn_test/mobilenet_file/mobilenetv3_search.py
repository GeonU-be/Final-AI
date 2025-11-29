import os
import json
import time
import requests
import numpy as np
from io import BytesIO
from PIL import Image, UnidentifiedImageError

import torch
from torchvision.models import mobilenet_v3_large, MobileNet_V3_Large_Weights
from torchvision import transforms
import faiss



# 0) MobileNetV3 Large 모델 로드

try:
    print("MobileNetV3 Large 모델 로드 중...")

    weights = MobileNet_V3_Large_Weights.IMAGENET1K_V2
    model = mobilenet_v3_large(weights=weights)

    # 960차원 출력으로 변경
    model.classifier = torch.nn.Identity()
    model.eval()

    print("MobileNetV3 Large 준비 완료")

except Exception as e:
    print("모델 로드 실패:", e)
    raise SystemExit(1)



# 1) 이미지 전처리 정의

preprocess = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(
        mean=[0.485, 0.456, 0.406],
        std=[0.229, 0.224, 0.225]
    )
])


def load_and_preprocess(url):
    """이미지 다운로드 + 전처리"""
    try:
        resp = requests.get(url, timeout=(3, 7))
        resp.raise_for_status()

    except requests.exceptions.HTTPError as e:
        print(f"HTTP 오류 발생: {e}")
        return None

    except requests.exceptions.Timeout:
        print("이미지 요청 시간 초과")
        return None

    except requests.exceptions.RequestException as e:
        print(f"이미지 요청 실패: {e}")
        return None

    try:
        img = Image.open(BytesIO(resp.content)).convert("RGB")

    except UnidentifiedImageError:
        print("이미지 포맷이 올바르지 않음")
        return None

    except Exception as e:
        print("이미지 디코딩 실패:", e)
        return None

    try:
        tensor = preprocess(img).unsqueeze(0)
        return tensor

    except Exception as e:
        print("전처리 실패:", e)
        return None



# 2) 임베딩 생성

def get_embedding(url):
    tensor = load_and_preprocess(url)
    if tensor is None:
        return None

    try:
        with torch.no_grad():
            emb = model(tensor).squeeze().numpy().astype("float32")

        # L2 정규화
        norm = np.linalg.norm(emb)
        if norm == 0:
            print("임베딩 정규화 실패: norm=0")
            return None

        emb = emb / (norm + 1e-10)
        return emb

    except Exception as e:
        print("임베딩 생성 실패:", e)
        return None


# 3) 사전 파일 로드

BASE = "/Users/a/IdeaProjects/Final-AI/dev/cnn_test/mobilenet_file"

id_map_path = os.path.join(BASE, "id_map_mobilenet.json")
emb_matrix_path = os.path.join(BASE, "emb_matrix_mobilenet.npy")
faiss_index_path = os.path.join(BASE, "faiss_index_mobilenet.bin")

# 파일 존재 확인
for path in [id_map_path, emb_matrix_path, faiss_index_path]:
    if not os.path.exists(path):
        print(f"필수 파일 누락: {path}")
        raise SystemExit(1)

try:
    with open(id_map_path, "r") as f:
        id_map = json.load(f)

    emb_matrix = np.load(emb_matrix_path)
    index = faiss.read_index(faiss_index_path)

    print("사전 데이터 로드 완료")

except Exception as e:
    print("사전 로드 중 오류:", e)
    raise SystemExit(1)



# 4) 유사 이미지 검색

def search_similar(url, top_k=5):

    print("\n검색 시작:", url)

    start = time.time()
    emb = get_embedding(url)
    if emb is None:
        print("임베딩 실패 → 검색 불가")
        return []

    emb = emb.reshape(1, -1)

    try:
        # FAISS 검색
        top_k = min(top_k, emb_matrix.shape[0])
        D, I = index.search(emb, top_k)

    except Exception as e:
        print("FAISS 검색 실패:", e)
        return []

    print("검색 완료:", round(time.time() - start, 4), "초")

    results = []

    for idx in I[0]:
        key = str(int(idx))

        if key in id_map:
            results.append(id_map[key])
        else:
            # 예상치 못한 키 에러 대응
            results.append({
                "index": key,
                "title": "(정보 없음)",
                "price": "-",
                "product_link": "-"
            })

    return results



# 5) 테스트 실행

if __name__ == "__main__":

    test_url = "https://thumbnail.coupangcdn.com/thumbnails/remote/320x320ex/image/retail/images/6671171604579-e3dec662-3729-4133-8fd9-107e14004798.jpg"

    results = search_similar(test_url, top_k=5)

    print("\n=== 검색 결과 ===")
    for r in results:
        print(f"- #{r['index']} | {r['title']} | ₩{r['price']} | {r['product_link']}")