import os
import json
import numpy as np
import faiss
from typing import List, Dict

from app.config.settings import CNN_DIR   # ← settings.py 기반
from .embedding_service import generate_embedding
from .model_loader import EMB_SIZE


# ---------------------------------------------------------
# 1) 상품 JSON 로드
# ---------------------------------------------------------
def load_products(json_path: str) -> List[Dict]:
    """
    상품 리스트 JSON을 로드한다.

    Args:
        json_path (str): 상품 메타데이터 JSON 파일 경로

    Returns:
        List[Dict]: 각 상품(item) 정보를 담은 리스트
    """
    with open(json_path, "r") as f:
        data = json.load(f)
    return data["products"]


# ---------------------------------------------------------
# 2) 전체 상품 임베딩 생성
# ---------------------------------------------------------
def build_embeddings(products: List[Dict]):
    """
    전체 상품 이미지에서 MobileNet 임베딩을 생성하고,
    id_map을 구성한다.

    Args:
        products (List[Dict]): 상품 메타데이터 목록

    Returns:
        emb_list (List[np.ndarray]): 각 상품의 960차원 임베딩
        id_map (Dict): 상품 index → 상품 메타데이터
    """

    emb_list = []
    id_map = {}

    for idx, item in enumerate(products):
        url = item["thumbnail_url"]

        # 개별 이미지 임베딩 생성
        emb = generate_embedding(url)
        if emb is None:
            continue

        emb_list.append(emb)

        # id_map 구성
        id_map[idx] = {
            "index": idx,
            "title": item["title"],
            "price": item["price"],
            "product_link": item["product_link"],
            "thumbnail_url": url,
        }

    return emb_list, id_map


# ---------------------------------------------------------
# 3) emb_matrix / id_map / faiss_index 저장
# ---------------------------------------------------------
def save_artifacts(emb_list, id_map):
    """
    임베딩 결과를 파일(emb_matrix, id_map, faiss_index)로 저장한다.

    Args:
        emb_list (List[np.ndarray])
        id_map (Dict)

    Returns:
        Dict:
            {
                "emb_matrix_path": str,
                "id_map_path": str,
                "faiss_index_path": str,
                "total_embeddings": int
            }
    """

    # /data/cnn 디렉토리 생성
    os.makedirs(CNN_DIR, exist_ok=True)

    # 1) emb_matrix.npy 저장
    emb_matrix = np.vstack(emb_list).astype("float32")
    emb_matrix_path = os.path.join(CNN_DIR, "emb_matrix.npy")
    np.save(emb_matrix_path, emb_matrix)

    # 2) id_map.json 저장
    id_map_path = os.path.join(CNN_DIR, "id_map.json")
    with open(id_map_path, "w") as f:
        json.dump(id_map, f, indent=2)

    # 3) faiss index 생성 + 저장
    index = faiss.IndexFlatL2(EMB_SIZE)
    faiss.normalize_L2(emb_matrix)
    index.add(emb_matrix)

    faiss_index_path = os.path.join(CNN_DIR, "faiss_index.bin")
    faiss.write_index(index, faiss_index_path)

    return {
        "emb_matrix_path": emb_matrix_path,
        "id_map_path": id_map_path,
        "faiss_index_path": faiss_index_path,
        "total_embeddings": len(emb_list),
    }