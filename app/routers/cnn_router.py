from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl
from typing import Optional, List

from app.services.cnn.workflow import create_recommender_graph


router = APIRouter(
    prefix="/cnn",
    tags=["CNN Recommender"]
)

# 워크플로우 그래프 (서버 시작 시 1회 생성)
workflow = create_recommender_graph()


# -----------------------------
# 요청/응답 모델 정의
# -----------------------------
class CNNRequest(BaseModel):
    image_url: HttpUrl
    top_k: Optional[int] = 5


class CNNResult(BaseModel):
    index: str
    title: str
    price: str
    product_link: str


class CNNResponse(BaseModel):
    results: List[CNNResult]


# -----------------------------
# 추천 API
# -----------------------------
@router.post("/recommend", response_model=CNNResponse)
async def recommend_similar_products(req: CNNRequest):
    """
    CNN + FAISS 기반 유사 상품 추천 API

    기능:
    - image_url(상품 이미지 주소) 입력받음
    - LangGraph의 CNN 워크플로우 실행
    - MobileNetV3 embedding 생성
    - FAISS top-k 검색
    - 상품 리스트 반환

    입력:
    {
      "image_url": "https://...",
      "top_k": 5
    }

    출력:
    {
      "results": [
        {
          "index": "10",
          "title": "상품명",
          "price": "10000",
          "product_link": "https://..."
        }
      ]
    }
    """

    try:
        # LangGraph workflow 실행
        result_state = workflow.invoke(
            {
                "image_url": req.image_url,
                "top_k": req.top_k,
                "embedding": None,
                "results": None
            }
        )

        # 검색 결과 가져오기
        results = result_state.get("results", [])

        return {"results": results}

    except Exception as e:
        print("[CNN Router] 오류:", e)
        raise HTTPException(status_code=500, detail=str(e))