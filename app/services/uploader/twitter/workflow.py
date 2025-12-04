import asyncio
import os
import uuid

from app.logs import logger

from app.services.uploader.twitter.oauth_service import (
    generate_code_verifier,
    generate_code_challenge,
    build_authorization_url,
    OAuthCallbackServer,
    exchange_code_for_token,
)

from app.services.uploader.twitter.token_service import (
    save_token,
    load_token,
    refresh_access_token,
)

from app.services.uploader.twitter.publish_service import post_tweet


# ============================================================
# 1) 인증 URL 생성
# ============================================================

def workflow_create_auth_url(client_id, redirect_uri, scope):
    """
    기능:
        - PKCE 인증에 필요한 code_verifier, code_challenge 생성
        - Twitter OAuth 인증 URL 생성
        - 사용자에게 auth_url 반환 → 브라우저에서 로그인하도록 안내

    출력(dict):
        {
            "success": True,
            "auth_url": "...",
            "code_verifier": "...",
            "state": "...",
            "message": "인증 URL 생성 완료"
        }
    """

    code_verifier = generate_code_verifier()
    code_challenge = generate_code_challenge(code_verifier)
    state = str(uuid.uuid4())

    url_info = build_authorization_url(
        client_id=client_id,
        redirect_uri=redirect_uri,
        scope=scope,
        state=state,
        code_challenge=code_challenge,
    )

    url_info["code_verifier"] = code_verifier
    url_info["message"] = "인증 URL 생성 완료"

    return url_info



# ============================================================
# 2) Callback 서버에서 Authorization Code 수신
# ============================================================

def workflow_wait_for_callback(port=8080, timeout=60):
    """
    기능:
        - Callback 서버를 열어 Twitter OAuth 인증 이후 redirect 를 기다림
        - Authorization Code 획득

    출력(dict):
        {
            "success": True/False,
            "authorization_code": "...",
            "message": "..."
        }
    """
    server = OAuthCallbackServer(port=port)
    result = server.run_once(timeout=timeout)

    if result["success"]:
        return {
            "success": True,
            "authorization_code": result["authorization_code"],
            "message": "Authorization Code 수신 성공"
        }

    return {
        "success": False,
        "authorization_code": None,
        "message": "Authorization Code 수신 실패"
    }



# ============================================================
# 3) Authorization Code → Token 교환
# ============================================================

def workflow_exchange_token(
        client_id, client_secret, authorization_code, redirect_uri, code_verifier
) -> dict:
    """
    기능:
        - Authorization Code를 AccessToken + RefreshToken으로 교환

    출력(dict):
        {
            "success": True/False,
            "token_info": {...},
            "message": "...",
        }
    """

    result = exchange_code_for_token(
        client_id=client_id,
        client_secret=client_secret,
        code=authorization_code,
        redirect_uri=redirect_uri,
        code_verifier=code_verifier,
    )

    return result



# ============================================================
# 4) 토큰 저장
# ============================================================

def workflow_save_token(token_info, code_verifier, client_id, user_id) -> dict:
    """
    기능:
        - 사용자별 token.json 저장

    출력(dict):
        {
            "success": True/False,
            "message": "...",
            "path": "..."
        }
    """
    return save_token(token_info, code_verifier, client_id, user_id)



# ============================================================
# 5) Tweet 업로드
# ============================================================

def workflow_post_tweet(access_token, tweet_text) -> dict:
    """
    기능:
        - Twitter API로 트윗 업로드 수행

    출력(dict):
        {
            "success": True/False,
            "tweet_id": "...",
            "message": "..."
        }
    """
    return post_tweet(access_token=access_token, text=tweet_text)



# ============================================================
# 6) 전체 Workflow: 자동 로그인 + 자동 업로드
# ============================================================

async def run_twitter_login_upload_workflow(
        user_id: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
        scope: str,
        tweet_text: str,
        port: int = 8080,
        timeout: int = 60,
):
    """
    기능:
        1) 인증 URL 생성 → 사용자 로그인 유도
        2) Callback에서 Authorization Code 획득
        3) Token 교환
        4) Token 저장
        5) 트윗 업로드

    출력(dict):
        {
            "success": True/False,
            "message": "...",
            "tweet_id": "...",
            "auth_url": "..."
        }
    """

    # 1. 인증 URL 생성
    step1 = workflow_create_auth_url(client_id, redirect_uri, scope)
    auth_url = step1["auth_url"]
    code_verifier = step1["code_verifier"]

    logger.info(f"[OAuth] 다음 URL에서 로그인하세요: {auth_url}")

    # 2. Authorization Code 수신
    step2 = workflow_wait_for_callback(port=port, timeout=timeout)
    if not step2["success"]:
        return {
            "success": False,
            "message": step2["message"],
            "auth_url": auth_url
        }

    authorization_code = step2["authorization_code"]

    # 3. Token 교환
    step3 = workflow_exchange_token(
        client_id,
        client_secret,
        authorization_code,
        redirect_uri,
        code_verifier
    )

    if not step3["success"]:
        return {
            "success": False,
            "message": step3["message"],
            "auth_url": auth_url
        }

    token_info = step3["token_info"]
    access_token = token_info["access_token"]

    # 4. Token 저장
    save_result = workflow_save_token(token_info, code_verifier, client_id, user_id)
    if not save_result["success"]:
        logger.warning(f"토큰 저장 실패 (user_id={user_id}): {save_result['message']}")
        # 저장 실패해도 트윗 업로드는 진행 ( access_token 은 메모리에 있음 )

    # 5. Tweet 업로드
    step5 = workflow_post_tweet(access_token, tweet_text)

    if not step5["success"]:
        return {
            "success": False,
            "message": step5["message"],
            "tweet_id": None,
            "auth_url": auth_url
        }

    return {
        "success": True,
        "message": "트위터 자동 로그인 + 자동 업로드 성공",
        "tweet_id": step5["tweet_id"],
        "auth_url": auth_url
    }