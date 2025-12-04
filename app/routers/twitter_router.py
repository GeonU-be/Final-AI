from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.uploader.twitter.workflow import run_twitter_login_upload_workflow

router = APIRouter()


# ============================================================
# Request Body Schema
# ============================================================

class TwitterUploadRequest(BaseModel):
    user_id: str            # token.json을 저장할 사용자 ID
    client_id: str
    client_secret: str
    redirect_uri: str
    scope: str              # 예: "tweet.read tweet.write users.read offline.access"
    tweet_text: str         # 업로드할 트윗 내용
    port: int = 8080
    timeout: int = 60


# ============================================================
# Twitter 자동 로그인 + 자동 업로드 Endpoint
# ============================================================

@router.post("/upload/twitter")
async def twitter_auto_upload(req: TwitterUploadRequest):
    """
    기능:
        - Java 백엔드에서 요청한 정보를 이용하여
          Twitter 자동 로그인 + 자동 업로드 전체 Workflow 실행.
        - Workflow는 OAuth 인증 URL → Callback 인증 → Token 발행 →
          Token 저장 → Tweet 업로드까지 포함.

    반환(JSON):
        {
            "success": True/False,
            "code": "SUCCESS" or "ERROR_CODE",
            "message": str,
            "data": {
                "tweet_id": "...",
                "auth_url": "..."
            }
        }
    """

    result = await run_twitter_login_upload_workflow(
        user_id=req.user_id,
        client_id=req.client_id,
        client_secret=req.client_secret,
        redirect_uri=req.redirect_uri,
        scope=req.scope,
        tweet_text=req.tweet_text,
        port=req.port,
        timeout=req.timeout
    )

    # 성공 시
    if result["success"]:
        return {
            "success": True,
            "code": "SUCCESS",
            "message": result["message"],
            "data": {
                "tweet_id": result.get("tweet_id"),
                "auth_url": result.get("auth_url")
            }
        }

    # 실패 시 (HTTP 400)
    raise HTTPException(
        status_code=400,
        detail={
            "success": False,
            "code": "TWITTER_UPLOAD_FAILED",
            "message": result["message"],
            "data": {
                "tweet_id": None,
                "auth_url": result.get("auth_url")
            }
        }
    )