import time
import numpy as np

from app.services.cnn.embedding_service import generate_embedding
from app.services.cnn.index_service import (
    get_faiss_index,
    get_id_map,
    get_emb_matrix,
)


def search_similar_products(url: str, top_k: int = 5):
    """
    주어진 이미지 URL을 기반으로 유사 상품을 검색한다.

    기능:
    - 이미지 URL에서 960차원 임베딩 생성
    - emb_matrix + FAISS index 로드
    - L2 기반 유사도 검색 (top_k)
    - id_map에서 메타데이터 매핑
    - 상품 정보 List 반환

    Args:
        url (str): 입력 이미지 URL
        top_k (int): 상위 몇 개를 반환할지

    Returns:
        list[dict]: 검색된 상품 정보 목록
    """

    print(f"\n[SearchService] 검색 시작: {url}")
    start = time.time()

    # --- 이미지 임베딩 생성 ---
    emb = generate_embedding(url)
    if emb is None:
        print("[SearchService] 임베딩 생성 실패 → 검색 중단")
        return []

    # --- reshape ---
    query_vec = emb.reshape(1, -1).astype("float32")

    # --- 인덱스 데이터 가져오기 ---
    id_map = get_id_map()
    emb_matrix = get_emb_matrix()
    faiss_index = get_faiss_index()

    top_k = min(top_k, emb_matrix.shape[0])

    try:
        # --- FAISS 검색 ---
        D, I = faiss_index.search(query_vec, top_k)
    except Exception as e:
        print("[SearchService] FAISS 검색 실패:", e)
        return []

    print(f"[SearchService] 검색 완료: {round(time.time() - start, 4)}초")

    # --- 결과 조립 ---
    results = []
    for idx in I[0]:
        key = str(int(idx))

        if key in id_map:
            results.append(id_map[key])
        else:
            # missing fallback
            results.append(
                {
                    "index": key,
                    "title": "정보 없음",
                    "price": "-",
                    "product_link": "-",
                }
            )

    return results