import requests


# ============================================================
# 1. 트윗 업로드 함수
# ============================================================

def post_tweet(access_token: str, text: str) -> dict:
    """
    기능:
        - Twitter API 를 이용해 트윗을 작성한다.
        - OAuth2 Bearer Token 인증 방식 사용. -> access_token = Bearer 인증

    입력:
        access_token (str): 발급받은 access_token
        text (str): 업로드할 트윗 내용

    출력(dict):
        {
            "success": True/False,
            "message": "업로드 결과 메시지",
            "tweet_id": "...",
            "raw_response": {...API response...}
        }
    """

    url = "https://api.twitter.com/2/tweets"

    headers = {
        "Authorization": f"Bearer {access_token.strip()}",
        "Content-Type": "application/json"
    }

    data = {"text": text}

    try:
        response = requests.post(url, headers=headers, json=data, timeout=30)

        # HTTP 상태 코드 검증
        if response.status_code != 200:
            error_detail = response.json() if response.text else {}
            return {
                "success": False,
                "message": f"트위터 업로드 실패 (HTTP {response.status_code}): {error_detail}",
                "tweet_id": None,
                "raw_response": error_detail
            }

        result = response.json()

        # 트위터 특성상 실패 시 'errors' 키 포함
        if "errors" in result:
            return {
                "success": False,
                "message": f"트윗 업로드 실패: {result['errors']}",
                "tweet_id": None,
                "raw_response": result
            }

        # 성공한 경우 'data': { 'id': "..." }
        tweet_id = result.get("data", {}).get("id")

        return {
            "success": True,
            "message": "트윗 업로드 성공",
            "tweet_id": tweet_id,
            "raw_response": result
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"요청 예외 발생: {e}",
            "tweet_id": None,
            "raw_response": None
        }