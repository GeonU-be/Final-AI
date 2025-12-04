from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Literal

from app.services.llm.workflows.router_workflow import build_router_graph
from app.logs import logger

router = APIRouter()

# 그래프를 모듈 로드 시 한 번만 빌드
ROUTER_GRAPH = build_router_graph()

# 요청 Body 정의
class SNSRequest(BaseModel):
    product_name: str
    keyword: str
    tone: str
    platform: Literal["naver","twitter"] = Field(
        description="SNS 플랫폼 선택"
    )


@router.post("/llm/generate-sns")
def generate_sns_content(body: SNSRequest) -> dict[str, str]:

    graph = build_router_graph()

    try:
        # LangGraph 실행
        result = graph.invoke({
            "product_name": body.product_name,
            "keyword": body.keyword,
            "tone": body.tone,
            "platform": body.platform
        })
    except Exception as e:
        logger.error(f"SNS 콘텐츠 생성 실패: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="콘텐츠 생성 중 오류가 발생했습니다.")

    return {
        "platform": result["platform"],
        "content": result["final_content"]
    }