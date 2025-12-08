"""
Twitter 업로드 최소 기능 모듈

핵심 기능만 제공합니다.
- ENV에서 자격 증명 로드
- Tweepy Client(API v2 write) / API(v1.1 media upload) 생성
- 텍스트 트윗 작성
- 미디어 포함 트윗 작성

필요 환경 변수:
  - TWITTER_API_KEY
  - TWITTER_API_SECRET
  - TWITTER_ACCESS_TOKEN
  - TWITTER_ACCESS_SECRET
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import tweepy

from app.logs import logger
from app.config import (
    TWITTER_API_KEY,
    TWITTER_API_SECRET,
    TWITTER_ACCESS_TOKEN,
    TWITTER_ACCESS_SECRET,
    TWITTER_WAIT_ON_RATE_LIMIT,
)


# --------------------
# Credentials loading
# --------------------
def load_twitter_credentials() -> Tuple[str, str, str, str]:
    """ENV에서 Twitter OAuth1 자격 증명을 읽는다.

    Returns:
        (api_key, api_secret, access_token, access_secret)
    """

    api_key = TWITTER_API_KEY
    api_secret = TWITTER_API_SECRET
    access_token = TWITTER_ACCESS_TOKEN
    access_secret = TWITTER_ACCESS_SECRET
    if not all([api_key, api_secret, access_token, access_secret]):
        raise RuntimeError("트위터 자격 정보가 .env(config) 에 완비되어야 합니다.")
    return api_key, api_secret, access_token, access_secret


# --------------------
# Client/API builders
# --------------------
def build_client(
    *,
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    access_token: Optional[str] = None,
    access_secret: Optional[str] = None,
) -> tweepy.Client:
    """Tweepy v2 Client 생성 (OAuth1 user context)

    Tweepy의 Client는 OAuth1 자격으로 v2 write 엔드포인트 호출이 가능하다.
    인자를 생략하면 ENV에서 자동 로드한다.
    """

    if not all([api_key, api_secret, access_token, access_secret]):
        api_key, api_secret, access_token, access_secret = load_twitter_credentials()

    client = tweepy.Client(
        consumer_key=api_key,
        consumer_secret=api_secret,
        access_token=access_token,
        access_token_secret=access_secret,
        wait_on_rate_limit=TWITTER_WAIT_ON_RATE_LIMIT,
    )
    return client


def build_api(
    *,
    api_key: Optional[str] = None,
    api_secret: Optional[str] = None,
    access_token: Optional[str] = None,
    access_secret: Optional[str] = None,
) -> tweepy.API:
    """Tweepy v1.1 API 생성 (미디어 업로드용)"""

    if not all([api_key, api_secret, access_token, access_secret]):
        api_key, api_secret, access_token, access_secret = load_twitter_credentials()

    auth = tweepy.OAuth1UserHandler(
        api_key, api_secret, access_token, access_secret
    )
    api = tweepy.API(auth, wait_on_rate_limit=TWITTER_WAIT_ON_RATE_LIMIT)
    return api


# --------------------
# Tweet operations
# --------------------
def create_tweet(
    text: str,
    *,
    client: Optional[tweepy.Client] = None,
) -> dict:
    """텍스트 트윗 작성(v2 /2/tweets)

    Args:
        text: 트윗 텍스트
        client: 외부에서 주입받을 경우 사용. 없으면 내부 생성
    Returns:
        Tweepy Response의 핵심 내용을 dict로 반환
    """

    if not client:
        client = build_client()

    logger.info("Create tweet 호출: %s", text)
    resp = client.create_tweet(text=text)
    # tweepy.Response: data(dict-like), errors, meta 보유
    return {
        "data": getattr(resp, "data", None),
        "errors": getattr(resp, "errors", None),
        "meta": getattr(resp, "meta", None),
    }


def create_tweet_with_media(
    text: str,
    media_paths: List[str],
    *,
    api: Optional[tweepy.API] = None,
    client: Optional[tweepy.Client] = None,
) -> dict:
    """미디어 업로드 후 트윗 작성

    v1.1 API로 media_id들을 업로드한 뒤, v2 Client로 트윗을 생성한다.
    """

    if not api:
        api = build_api()
    if not client:
        client = build_client()

    media_ids: List[str] = []
    for path in media_paths:
        logger.info("미디어 업로드 시작: %s", path)
        media = api.media_upload(filename=path)
        media_id = getattr(media, "media_id", None) or getattr(
            media, "media_id_string", None
        )
        if not media_id:
            raise RuntimeError(f"media_id를 얻지 못했습니다: {path}")
        media_ids.append(str(media_id))

    logger.info("Create tweet with media 호출: %s", text)
    resp = client.create_tweet(text=text, media_ids=media_ids)
    return {
        "data": getattr(resp, "data", None),
        "errors": getattr(resp, "errors", None),
        "meta": getattr(resp, "meta", None),
    }
