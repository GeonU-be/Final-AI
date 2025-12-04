from langgraph.graph import StateGraph, END
from langgraph.graph.state import CompiledStateGraph
from typing import TypedDict

from app.services.llm.prompt_builder import build_prompt
from app.services.llm.llm_caller import call_llm
from app.services.llm.postprocess import postprocess


class TwitterState(TypedDict, total=False):
    product_name: str
    keyword: str
    tone: str
    platform: str      # 자동으로 "twitter"
    prompt: str
    generated_content: str
    final_content: str


def build_twitter_graph() -> CompiledStateGraph:
    """
    트위터용 짧은 홍보글 생성 Workflow.
    플랫폼 값은 자동으로 'twitter' 로 지정된다.
    """

    workflow = StateGraph(TwitterState)

    # Node 등록
    workflow.add_node("prompt", build_prompt)
    workflow.add_node("llm", call_llm)
    workflow.add_node("postprocess", postprocess)

    # 실행 시작점
    workflow.set_entry_point("prompt")

    # 실행 순서
    workflow.add_edge("prompt", "llm")
    workflow.add_edge("llm", "postprocess")
    workflow.add_edge("postprocess", END)

    return workflow.compile()



# 사용 예시 (트위터)
"""
최종 출력값

{
  "product_name": "...",
  "keyword": "...",
  "tone": "...",
  "platform": "twitter",
  "prompt": "...",
  "generated_content": "겨울엔 패딩 #핫템...",
  "final_content": "겨울엔 패딩 #핫템..."
}

"""