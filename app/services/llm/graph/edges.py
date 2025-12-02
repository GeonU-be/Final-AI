from langgraph.graph import StateGraph

from app.classes.models import GraphState
from app.services.llm.graph.nodes import (
    entry_node,
    crawling_keywords_node,
    make_keyword_node,
    get_keyword_node,
    crawling_items_ssadagu_node,
    crawling_items_coupang_node,
    filter_strange_node,
    product_check,
    job_failed,
    generate_ads,
)

workflow = StateGraph(GraphState)

workflow.add_node("entry_node", entry_node)
workflow.add_node("crawling_keywords_node", crawling_keywords_node)
workflow.add_node("make_keyword_node", make_keyword_node)
workflow.add_node("get_keyword_node", get_keyword_node)
workflow.add_node("crawling_items_ssadagu_node", crawling_items_ssadagu_node)
workflow.add_node("crawling_items_coupang_node", crawling_items_coupang_node)
workflow.add_node("filter_strange_node", filter_strange_node)
workflow.add_node("product_check", product_check)
workflow.add_node("job_failed", job_failed)
workflow.add_node("generate_ads", generate_ads)

# entry_node 이후 keyword 보유 여부에 따라 분기한다.
workflow.add_conditional_edges(
    "entry_node",
    lambda state: "need_keyword" if state.get("need_keyword", False) else "has_keyword",
    {"need_keyword": "crawling_keywords_node", "has_keyword": "get_keyword_node"},
)

workflow.add_edge("crawling_keywords_node", "make_keyword_node")
workflow.add_edge("make_keyword_node", "get_keyword_node")

# 키워드를 확보한 뒤 각 판매처 크롤링을 동시에 진행하고 필터링 노드에서 조인한다.
workflow.add_edge("get_keyword_node", "crawling_items_ssadagu_node")
workflow.add_edge("get_keyword_node", "crawling_items_coupang_node")
workflow.add_edge("crawling_items_ssadagu_node", "filter_strange_node")
workflow.add_edge("crawling_items_coupang_node", "filter_strange_node")
workflow.add_conditional_edges(
    "filter_strange_node",
    lambda state: "wait" if state.get("need_more_products") else "ready",
    {"wait": "get_keyword_node", "ready": "product_check"},
)

workflow.add_conditional_edges(
    "product_check",
    lambda state: (
        "done"
        if not state.get("need_retry", False)
        else "retry" if not state.get("try_count", 0) > 10 else "stop"
    ),
    {"done": "generate_ads", "retry": "get_keyword_node", "stop": "job_failed"},
)

workflow.set_entry_point("entry_node")
workflow.set_finish_point("generate_ads")
workflow.set_finish_point("job_failed")

app = workflow.compile()

print("build graph")
print("=== LangGraph Ready ===")
