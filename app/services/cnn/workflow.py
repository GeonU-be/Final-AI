from typing import TypedDict, List, Optional
import numpy as np

from langgraph.graph import StateGraph, END

from app.services.cnn.embedding_service import generate_embedding
from app.services.cnn.search_service import search_similar_products


# -----------------------------
# 1) Workflow State 정의
# -----------------------------
class RecommenderState(TypedDict):
    image_url: str
    embedding: Optional[np.ndarray]
    top_k: int
    results: Optional[List[dict]]


# -----------------------------
# 2) Node: URL 입력 처리
# -----------------------------
def load_input_url_node(state: RecommenderState) -> RecommenderState:
    """
    기능:
    - FastAPI로부터 전달받은 입력값(image_url, top_k)을 상태로 유지

    입력:
        state["image_url"]
        state["top_k"]

    출력:
        변경 없음 (state 그대로 반환)
    """
    print(f"[Workflow] URL 입력 수신: {state['image_url']}")
    return state


# -----------------------------
# 3) Node: 임베딩 생성
# -----------------------------
def generate_embedding_node(state: RecommenderState) -> RecommenderState:
    """
    기능:
    - 이미지 URL을 받아 embedding_service.generate_embedding() 호출
    - 임베딩 벡터를 state["embedding"]에 저장

    출력값:
        state["embedding"] = np.ndarray(shape=(960,))
        실패 시 None
    """
    print("[Workflow] 임베딩 생성 단계 실행")

    emb = generate_embedding(state["image_url"])
    state["embedding"] = emb

    if emb is None:
        print("[Workflow] 임베딩 생성 실패")
    else:
        print("[Workflow] 임베딩 생성 성공")

    return state


# -----------------------------
# 4) Node: 유사 상품 검색
# -----------------------------
def search_similar_node(state: RecommenderState) -> RecommenderState:
    """
    기능:
    - embedding_service → search_service 를 이용하여 top-K 검색 수행
    - 결과 리스트를 state["results"]에 저장

    출력값:
        state["results"] = list[dict]
    """
    print("[Workflow] 유사 상품 검색 단계 실행")

    if state["embedding"] is None:
        print("[Workflow] 검색 불가: embedding 없음")
        state["results"] = []
        return state

    results = search_similar_products(
        state["image_url"],
        top_k=state.get("top_k", 5)
    )

    state["results"] = results
    print(f"[Workflow] 검색 결과 {len(results)}개")

    return state


# -----------------------------
# 5) Node: 결과 반환
# -----------------------------
def return_result_node(state: RecommenderState):
    """
    기능:
    - 최종 결과를 그대로 반환하여 FastAPI Router에서 사용할 수 있게 함.
    """
    print("[Workflow] 최종 결과 반환")
    return state


# -----------------------------
# 6) Workflow Graph 구성
# -----------------------------
def create_recommender_graph():
    """
    LangGraph StateGraph 기반 유사 상품 추천 워크플로우 구성.

    Workflow:
        (1) load_input_url_node
        → (2) generate_embedding_node
        → (3) search_similar_node
        → (4) return_result_node
    """
    graph = StateGraph(RecommenderState)

    graph.add_node("load_input", load_input_url_node)
    graph.add_node("gen_embedding", generate_embedding_node)
    graph.add_node("search", search_similar_node)
    graph.add_node("return", return_result_node)

    # Node 연결
    graph.set_entry_point("load_input")
    graph.add_edge("load_input", "gen_embedding")
    graph.add_edge("gen_embedding", "search")
    graph.add_edge("search", "return")

    graph.add_edge("return", END)

    return graph.compile()


# -----------------------------------------
# Optional: 직접 실행용 테스트 함수
# -----------------------------------------
if __name__ == "__main__":
    graph = create_recommender_graph()

    input_state = {
        "image_url": "https://thumbnail.coupangcdn.com/test.jpg",
        "top_k": 5,
        "results": None,
        "embedding": None,
    }

    result = graph.invoke(input_state)

    print("\n=== 최종 Workflow 출력 ===")
    print(result)