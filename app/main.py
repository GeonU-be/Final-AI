import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.classes.requests import WritePostRequest, UploadPostRequest


def create_app() -> FastAPI:
    app = FastAPI(title="AURA Python Server")

    origin_env = os.getenv("FASTAPI_ALLOWED_ORIGINS", "")
    allowed_origins = allowed_origins = [
        origin.strip() for origin in origin_env.split(",") if origin.strip()
    ]

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
        return

    @app.get("/api/crawler")
    async def get_keywords():
        # asyncio.create_task로 로직 돌리기
        # => 로직은 돌아가는데 응답을 먼저 제공함
        return

    @app.post("/api/upload")
    async def upload_post(request: UploadPostRequest):
        # asyncio.create_task로 로직 돌리기
        # => 로직은 돌아가는데 응답을 먼저 제공함
        return
