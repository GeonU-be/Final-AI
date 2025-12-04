# app/routers/naver_router.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.uploader.naver.workflow import run_login_upload_workflow


router = APIRouter()


# ---------------------------------------------------------
# 요청 Body 스키마 정의 (Java → FastAPI 요청 형태)
# ---------------------------------------------------------
class NaverUploadRequest(BaseModel):
    login_id: str
    login_pw: str
    session_file: str
    blog_id: str
    title: str
    content: str
    max_retries: int = 3   # 기본값 설정 (선택)


# ---------------------------------------------------------
# 네이버 자동 로그인 + 자동 업로드 라우터
# ---------------------------------------------------------
@router.post("/upload/naver")
async def upload_to_naver(req: NaverUploadRequest):
    """
    기능:
        - Java 백엔드에서 전달된 로그인 정보 및 게시글 정보를 받아
          run_login_upload_workflow() 를 실행한다.

    입력:
        req: NaverUploadRequest
            - login_id: 네이버 ID
            - login_pw: 네이버 PW
            - session_file: 세션 저장 파일명
            - blog_id: 네이버 블로그 ID
            - title: 게시글 제목
            - content: 게시글 본문
            - max_retries: 업로드 재시도 횟수

    반환(JSON):
        {
            "success": bool,
            "message": str,
            "attempts": int
        }
    """

    result = await run_login_upload_workflow(
        login_id=req.login_id,
        login_pw=req.login_pw,
        session_file=req.session_file,
        BLOG_ID=req.blog_id,
        title=req.title,
        content=req.content,
        max_retries=req.max_retries
    )

    # 실패 시 HTTP 400 에러 반환
    if not result["success"]:
        raise HTTPException(
            status_code=400,
            detail={
                "success": False,
                "message": result["message"],
                "attempts": result["attempts"]
            }
        )

    # 성공 시 그대로 반환
    return result