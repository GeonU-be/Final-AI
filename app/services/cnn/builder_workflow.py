from langgraph.graph import StateGraph, START, END
from langgraph.types import StateDict

from .index_builder import (
    load_products,
    build_embeddings,
    save_artifacts,
)


# ---------------------------------------------------------
# 1) LangGraph 상태 정의
# ---------------------------------------------------------
class BuilderState(StateDict):
    json_path: str        # 입력 상품 JSON 파일 경로
    products: list = []   # load_products 결과
    emb_list: list = []   # build_embeddings 결과 (임베딩 리스트)
    id_map: dict = {}     # id_map
    result: dict = {}     # save_artifacts 결과


# ---------------------------------------------------------
# 2) 노드 정의
# ---------------------------------------------------------
def node_load_products(state: BuilderState):
    """
    상품 메타데이터 JSON을 로드한다.
    Returns: {"products": List[Dict]}
    """
    products = load_products(state.json_path)
    return {"products": products}


def node_build_embeddings(state: BuilderState):
    """
    전체 상품 이미지 → 임베딩 생성 + id_map 생성.
    Returns: {"emb_list": List, "id_map": Dict}
    """
    emb_list, id_map = build_embeddings(state.products)
    return {"emb_list": emb_list, "id_map": id_map}


def node_save_artifacts(state: BuilderState):
    """
    emb_matrix / id_map / faiss_index 파일 저장.
    Returns: {"result": Dict}
    """
    result = save_artifacts(state.emb_list, state.id_map)
    return {"result": result}


# ---------------------------------------------------------
# 3) LangGraph 그래프 컴파일
# ---------------------------------------------------------
def build_cnn_builder_graph():
    graph = StateGraph(BuilderState)

    graph.add_node("load_products", node_load_products)
    graph.add_node("build_embeddings", node_build_embeddings)
    graph.add_node("save_artifacts", node_save_artifacts)

    graph.add_edge(START, "load_products")
    graph.add_edge("load_products", "build_embeddings")
    graph.add_edge("build_embeddings", "save_artifacts")
    graph.add_edge("save_artifacts", END)

    return graph.compile()