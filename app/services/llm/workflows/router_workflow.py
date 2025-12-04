from langgraph.graph import StateGraph, END
from typing import TypedDict

from app.services.llm.workflows.naver_workflow import build_naver_graph
from app.services.llm.workflows.twitter_workflow import build_twitter_graph


class RouterState(TypedDict, total=False):
    # 사용자 입력
    product_name: str
    keyword: str
    tone: str
    platform: str   # "naver" 또는 "twitter"

    # 내부 Workflow 에서 생성될 값
    prompt: str
    generated_content: str
    final_content: str


def router_decision(state: RouterState):
    """
    platform 값에 따라 workflow 다음 경로를 결정하는 Router Node.
    """
    platform = state.get("platform")

    if platform == "naver":
        return "NAVER_FLOW"
    elif platform == "twitter":
        return "TWITTER_FLOW"
    else:
        raise ValueError(f"지원하지 않는 플랫폼: {platform}")


def build_router_graph():
    """
    네이버 + 트위터 통합 Router 그래프 생성
    """
    graph = StateGraph(RouterState)

    # Router Node
    graph.add_node("router", router_decision)

    # 플랫폼별 Workflow를 서브그래프로 연결
    graph.add_conditional_edges(
        source="router",
        condition=router_decision,
        path_map={
            "NAVER_FLOW": "naver_workflow",
            "TWITTER_FLOW": "twitter_workflow"
        }
    )

    # 네이버 Workflow 추가
    naver = build_naver_graph()
    graph.add_node("naver_workflow", naver)

    # 트위터 Workflow 추가
    twitter = build_twitter_graph()
    graph.add_node("twitter_workflow", twitter)

    # 종료
    graph.add_edge("naver_workflow", END)
    graph.add_edge("twitter_workflow", END)

    graph.set_entry_point("router")

    return graph.compile()