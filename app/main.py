from dataclasses import asdict
import asyncio
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.services.llm.graph import Graph
from app.classes.models import GraphState

from app.classes.requests import WritePostRequest, UploadPostRequest
from app.config import FASTAPI_ALLOWED_ORIGINS


def create_app() -> FastAPI:
    app = FastAPI(title="AURA Python Server")

    allowed_origins = FASTAPI_ALLOWED_ORIGINS

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.post("/api/write")
    async def write_posts(request: WritePostRequest):
        # asyncio.create_task로 로직 돌리기
        # => 로직은 돌아가는데 응답이 먼저 들어감
        print("글 작성 로직 실행")
        print("입력: \n", request.json())
        # 그래프 굴리는 그 로직

        input = GraphState(
            keyword=request.keyword, settings=request.llmSettings, jobId=request.jobId
        )

        asyncio.create_task(Graph.ainvoke(input))
        return

    @app.get("/api/crawler")
    async def get_keywords():
        # asyncio.create_task로 로직 돌리기
        # => 로직은 돌아가는데 응답을 먼저 제공함
        print("키워드 호출 로직 실행")
        # 크롤링 해서 키워드 리스트 갖다 주는 코드

        return

    @app.post("/api/upload")
    async def upload_post(request: UploadPostRequest):
        # asyncio.create_task로 로직 돌리기
        # => 로직은 돌아가는데 응답을 먼저 제공함
        print("글 업로드 로직 실행")
        print("입력: \n", request.json())
        # 글 내용 받아서 업로드 해주는 코드

        return

    return app


app = create_app()

print("*" * 52)
print("FastAPI is running on http://localhost:8000")
print("Checkout Swagger page on http://localhost:8000/docs")
print("*" * 52)
