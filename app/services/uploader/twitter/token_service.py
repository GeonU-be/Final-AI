import os
import json
import requests
import base64


TOKEN_DIR = "tokens/twitter"     # 사용자별 저장 폴더(예: tokens/twitter/{user_id}.json)


# ============================================================
# 1. 사용자별 token.json 경로 생성
# ============================================================

def get_token_file_path(user_id: str) -> str:
    """
    기능:
        - 사용자별 token.json 파일 경로 생성.
        - 폴더가 없으면 자동 생성.

    입력:
        user_id (str): 사용자 고유 식별자

    출력:
        str: token.json 파일 경로
    """
    os.makedirs(TOKEN_DIR, exist_ok=True)
    return os.path.join(TOKEN_DIR, f"{user_id}.json")


# ============================================================
# 2. 토큰 저장
# ============================================================

def save_token(token_info: dict, code_verifier: str, client_id: str, user_id: str):
    """
    기능:
        - token_info + code_verifier + client_id를 하나의 JSON 파일로 저장한다.

    입력:
        token_info: Twitter token response (access_token, refresh_token 등)
        code_verifier: PKCE 인증 시 사용된 verifier
        client_id: Twitter Client ID
        user_id: 사용자 ID

    출력(dict):
        {
            "success": True,
            "message": "저장 완료",
            "path": token_file_path
        }
    """

    token_file_path = get_token_file_path(user_id)

    data = token_info.copy()
    data["code_verifier"] = code_verifier
    data["client_id"] = client_id

    try:
        with open(token_file_path, "w") as f:
            json.dump(data, f, indent=2)

        return {
            "success": True,
            "message": "토큰 저장 완료",
            "path": token_file_path
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"토큰 저장 실패: {e}",
            "path": None
        }


# ============================================================
# 3. 토큰 로드
# ============================================================

def load_token(user_id: str):
    """
    기능:
        - 사용자별 token.json 읽기.

    입력:
        user_id (str)

    출력(dict):
        {
            "success": True/False,
            "token": dict or None,
            "message": "..."
        }
    """

    token_file_path = get_token_file_path(user_id)

    if not os.path.exists(token_file_path):
        return {
            "success": False,
            "token": None,
            "message": "토큰 파일이 존재하지 않습니다"
        }

    try:
        with open(token_file_path) as f:
            token = json.load(f)

        return {
            "success": True,
            "token": token,
            "message": "토큰 로드 성공"
        }

    except Exception as e:
        return {
            "success": False,
            "token": None,
            "message": f"토큰 로드 실패: {e}"
        }


# ============================================================
# 4. Refresh Token 갱신
# ============================================================

def refresh_access_token(user_id: str, client_secret: str):
    """
    기능:
        - refresh_token → 새로운 access_token으로 갱신
        - Twitter OAuth2.0 /token endpoint 사용

    입력:
        user_id: 토큰 파일을 로드할 사용자 ID
        client_secret: Twitter Client Secret

    출력(dict):
        {
            "success": True/False,
            "token": new_token_info or None,
            "message": "..."
        }
    """

    # Step1: 기존 토큰 로드
    token_data = load_token(user_id)
    if not token_data["success"]:
        return {
            "success": False,
            "token": None,
            "message": token_data["message"]
        }

    token_info = token_data["token"]

    refresh_token = token_info.get("refresh_token")
    code_verifier = token_info.get("code_verifier")
    client_id = token_info.get("client_id")

    if not refresh_token:
        return {
            "success": False,
            "token": None,
            "message": "refresh_token이 존재하지 않습니다"
        }

    url = "https://api.twitter.com/2/oauth2/token"

    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
    }

    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
    }

    try:
        res = requests.post(url, headers=headers, data=data, timeout=30)
        new_token_info = res.json()

        # 실패 처리
        if "error" in new_token_info:
            return {
                "success": False,
                "token": None,
                "message": f"Refresh 실패: {new_token_info}"
            }

        # 새 토큰 저장
        save_result = save_token(new_token_info, code_verifier, client_id, user_id)

        return {
            "success": True,
            "token": new_token_info,
            "message": f"Refresh 성공 / {save_result['message']}"
        }

    except Exception as e:
        return {
            "success": False,
            "token": None,
            "message": f"Refresh 요청 중 오류 발생: {e}"
        }