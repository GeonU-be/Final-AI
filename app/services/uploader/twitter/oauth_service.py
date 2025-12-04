import os
import base64
import hashlib
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
import requests


# ============================================================
# 1) Code Verifier / Code Challenge 생성
# ============================================================

def generate_code_verifier():
    """
    기능:
        - OAuth2 PKCE 에서 필요한 code_verifier 생성.
        - 고난도 랜덤 문자열(43~128 bytes)을 Base64 URL Safe 인코딩하여 반환.

    출력:
        str : code_verifier (클라이언트 비밀값)
    """
    return base64.urlsafe_b64encode(os.urandom(40)).rstrip(b"=").decode("utf-8")


def generate_code_challenge(verifier: str):
    """
    기능:
        - code_verifier를 SHA256 해싱하여 code_challenge 생성.
        - OAuth2.0 PKCE 의 표준 방식.

    입력:
        verifier (str)

    출력:
        str : code_challenge (Authorization URL 생성 시 사용)
    """
    digest = hashlib.sha256(verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("utf-8")


# ============================================================
# 2) Authorization URL 생성
# ============================================================

def build_authorization_url(client_id, redirect_uri, scope, state, code_challenge):
    """
    기능:
        - Twitter OAuth 인증 URL을 생성.
        - 사용자 브라우저로 리디렉션하여 수동 인증 유도.

    입력:
        client_id: 트위터 개발자 Client ID
        redirect_uri: Callback URL
        scope: 권한 목록
        state: 요청의 무결성을 위한 난수
        code_challenge: PKCE code_challenge 값

    출력(dict):
        {
            "success": True,
            "auth_url": "...",
            "code_challenge": code_challenge,
            "state": state
        }
    """

    quoted_redirect = urllib.parse.quote(redirect_uri)
    quoted_scope = urllib.parse.quote(scope)

    auth_url = (
        "https://twitter.com/i/oauth2/authorize"
        f"?response_type=code"
        f"&client_id={client_id}"
        f"&redirect_uri={quoted_redirect}"
        f"&scope={quoted_scope}"
        f"&state={state}"
        f"&code_challenge={code_challenge}"
        f"&code_challenge_method=S256"
    )

    return {
        "success": True,
        "auth_url": auth_url,
        "code_challenge": code_challenge,
        "state": state
    }


# ============================================================
# 3) Callback 서버 → Authorization Code 받기
# ============================================================

class OAuthCallbackServer:
    """
    기능:
        - Twitter OAuth 리디렉션을 받아 authorization_code를 획득하는 임시 서버.
        - LangGraph에서는 wait_callback_node 로 활용.
    """

    def __init__(self, host="localhost", port=8080):
        self.host = host
        self.port = port
        self.authorization_code = None
        self.server = None

    class Handler(BaseHTTPRequestHandler):
        parent = None  # 부모 클래스(OAuthCallbackServer)의 참조

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)

            if "code" in params:
                code = params["code"][0]
                self.parent.authorization_code = code

                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                self.wfile.write(
                    b"<h1>Authorization Complete</h1>You can close this tab."
                )
            else:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"<h1>Error: Missing authorization code</h1>")

    def run_once(self, timeout=60):
        """
        기능:
            - Callback 서버를 한 번 실행하여 Authorization Code를 수신한다.

        입력:
            timeout: 서버가 기다리는 최대 시간(초)

        출력(dict):
            {
                "success": True/False,
                "authorization_code": str or None
            }
        """
        OAuthCallbackServer.Handler.parent = self
        self.server = HTTPServer((self.host, self.port), OAuthCallbackServer.Handler)
        self.server.timeout = timeout

        try:
            self.server.handle_request()
        finally:
            self.server.server_close()

        if self.authorization_code:
            return {
                "success": True,
                "authorization_code": self.authorization_code
            }

        return {
            "success": False,
            "authorization_code": None
        }


# ============================================================
# 4) Authorization Code → Access Token 교환
# ============================================================

def exchange_code_for_token(
        client_id,
        client_secret,
        code,
        redirect_uri,
        code_verifier
):
    """
    기능:
        - Authorization Code를 Twitter Access Token + Refresh Token 으로 교환.
        - PKCE의 code_verifier를 함께 전달해야 한다.

    입력:
        client_id
        client_secret
        code: authorization_code
        redirect_uri
        code_verifier

    출력(dict):
        {
            "success": True/False,
            "token_info": { ...API response... },
            "message": "...",
        }
    """

    url = "https://api.twitter.com/2/oauth2/token"

    # ClientID:Secret Base64 encoding
    basic_token = base64.b64encode(
        f"{client_id}:{client_secret}".encode()
    ).decode()

    headers = {
        "Authorization": f"Basic {basic_token}",
        "Content-Type": "application/x-www-form-urlencoded",
    }

    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
    }

    try:
        res = requests.post(url, headers=headers, data=data, timeout=30)
        token_info = res.json()

        # 오류 검사
        if "error" in token_info:
            return {
                "success": False,
                "token_info": None,
                "message": f"Token 교환 실패: {token_info}"
            }

        return {
            "success": True,
            "token_info": token_info,
            "message": "Token 교환 성공"
        }

    except Exception as e:
        return {
            "success": False,
            "token_info": None,
            "message": f"요청 중 오류 발생: {e}"
        }