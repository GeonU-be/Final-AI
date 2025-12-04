import os
import json
import numpy as np
import faiss

from app.config.settings import (
    ID_MAP_PATH,
    EMB_MATRIX_PATH,
    FAISS_INDEX_PATH,
)

# 캐시용 전역 변수
_id_map = None
_emb_matrix = None
_faiss_index = None


def load_index_files():
    """
    id_map.json, emb_matrix.npy, faiss_index.bin 을 로드하여
    서비스 전체에서 재사용할 수 있도록 캐싱한다.

    기능:
    - JSON → id_map (dict)
    - NPY → emb_matrix (np.ndarray, shape=(N, 960))
    - FAISS index → L2 기반 벡터 검색 엔진
    - FAISS index는 normalize_L2 적용되어 있어야 함
    - 모든 파일 존재 여부 체크 (+ 오류 처리)

    Returns:
        tuple(id_map, emb_matrix, faiss_index)
    """

    global _id_map, _emb_matrix, _faiss_index

    # --- 이미 로드된 경우 그대로 반환 ---
    if _id_map is not None and _emb_matrix is not None and _faiss_index is not None:
        return _id_map, _emb_matrix, _faiss_index

    print("[IndexService] 인덱스 파일 로드 시작")

    # --- 파일 존재 검사 ---
    for path in [ID_MAP_PATH, EMB_MATRIX_PATH, FAISS_INDEX_PATH]:
        if not os.path.exists(path):
            raise FileNotFoundError(f"[IndexService] 파일 누락: {path}")

    # --- id_map 로드 ---
    with open(ID_MAP_PATH, "r") as f:
        _id_map = json.load(f)

    # --- emb_matrix 로드 ---
    _emb_matrix = np.load(EMB_MATRIX_PATH).astype("float32")

    # --- FAISS index 로드 ---
    _faiss_index = faiss.read_index(FAISS_INDEX_PATH)

    print("[IndexService] 모든 인덱스 파일 로드 완료")
    print(f"[IndexService] 임베딩 행 개수: {_emb_matrix.shape[0]}개")

    return _id_map, _emb_matrix, _faiss_index


def get_id_map():
    """
    로딩된 id_map 반환 (없으면 자동 로딩)

    Returns:
        dict: { "index": {...}, ... }
    """
    global _id_map

    if _id_map is None:
        load_index_files()

    return _id_map


def get_emb_matrix():
    """
    로딩된 emb_matrix 반환 (없으면 자동 로딩)

    Returns:
        np.ndarray: shape=(N, 960)
    """
    global _emb_matrix

    if _emb_matrix is None:
        load_index_files()

    return _emb_matrix


def get_faiss_index():
    """
    로드된 FAISS index 객체 반환 (없으면 자동 로딩)

    Returns:
        faiss.Index: 벡터 검색 엔진
    """
    global _faiss_index

    if _faiss_index is None:
        load_index_files()

    return _faiss_index