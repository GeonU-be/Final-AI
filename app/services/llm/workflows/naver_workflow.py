# app/services/llm/workflows/naver_graph.py

from langgraph.graph import StateGraph, END
from typing import TypedDict

from app.services.llm.prompt_builder import build_prompt
from app.services.llm.llm_caller import call_llm
from app.services.llm.postprocess import postprocess


class NaverState(TypedDict, total=False):
    product_name: str
    keyword: str
    tone: str
    platform: str      # 자동으로 "naver"
    prompt: str
    generated_content: str
    final_content: str


def build_naver_graph():
    """
    네이버 블로그 홍보글 생성 전용 Workflow 구성.
    플랫폼 값은 자동으로 'naver'로 설정된다.
    """

    workflow = StateGraph(NaverState)

    # Node 등록
    workflow.add_node("prompt", build_prompt)
    workflow.add_node("llm", call_llm)
    workflow.add_node("postprocess", postprocess)

    # 시작 지점
    workflow.set_entry_point("prompt")

    # 실행 순서
    workflow.add_edge("prompt", "llm")
    workflow.add_edge("llm", "postprocess")
    workflow.add_edge("postprocess", END)

    # 그래프 컴파일
    return workflow.compile()

"""
최종 출력값

{
  "product_name": "...",
  "keyword": "...",
  "tone": "...",
  "platform": "naver",
  "prompt": "...",
  "generated_content": "<h3>네이버 본문...</h3>",
  "final_content": "<h3>정리된 네이버 본문...</h3>"
}

"""


