from fastapi import APIRouter
from pydantic import BaseModel

from app.services.llm.workflows.router_workflow import build_router_graph


router = APIRouter()

# 요청 Body 정의
class SNSRequest(BaseModel):
    product_name: str
    keyword: str
    tone: str
    platform: str  # "naver" or "twitter"


@router.post("/llm/generate-sns")
def generate_sns_content(body: SNSRequest) -> dict[str, str]:

    graph = build_router_graph()

    # LangGraph 실행
    result = graph.invoke({
        "product_name": body.product_name,
        "keyword": body.keyword,
        "tone": body.tone,
        "platform": body.platform
    })

    return {
        "platform": result["platform"],
        "content": result["final_content"]
    }