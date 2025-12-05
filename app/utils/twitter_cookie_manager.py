"""
Twitter 쿠키 자동 관리 모듈.

프로덕션 환경에서 쿠키를 자동으로 갱신하고 관리합니다.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Set

from app.services.crawler.keywords.twitter_crawler import (
    save_twitter_cookies,
    get_trend_keywords,
    DEFAULT_COOKIE_FILE,
)

logger = logging.getLogger(__name__)

# 쿠키 만료 시간 (일반적으로 7일, 안전하게 5일로 설정)
COOKIE_EXPIRY_DAYS = 5
# 쿠키 갱신 주기 (일) - 만료 전에 갱신
COOKIE_REFRESH_INTERVAL_DAYS = 3


def get_cookie_file_path(cookie_file: str = DEFAULT_COOKIE_FILE) -> Path:
    """쿠키 파일의 절대 경로를 반환."""
    if os.path.isabs(cookie_file):
        return Path(cookie_file)
    # 프로젝트 루트 기준
    project_root = Path(__file__).parent.parent
    return project_root / cookie_file


def is_cookie_valid(cookie_file: str = DEFAULT_COOKIE_FILE) -> bool:
    """
    쿠키 파일이 존재하고 유효한지 확인.
    
    Returns:
        bool: 쿠키가 유효하면 True, 없거나 만료되었으면 False
    """
    cookie_path = get_cookie_file_path(cookie_file)
    
    if not cookie_path.exists():
        logger.debug("쿠키 파일이 없습니다: %s", cookie_path)
        return False
    
    try:
        # 쿠키 파일 수정 시간 확인
        mtime = cookie_path.stat().st_mtime
        cookie_age = time.time() - mtime
        cookie_age_days = cookie_age / (24 * 3600)
        
        if cookie_age_days > COOKIE_EXPIRY_DAYS:
            logger.warning(
                "쿠키가 만료되었습니다 (생성 후 %d일 경과, 만료: %d일)",
                int(cookie_age_days),
                COOKIE_EXPIRY_DAYS
            )
            return False
        
        # 쿠키 파일 내용 확인
        with open(cookie_path, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        
        if not cookies or len(cookies) == 0:
            logger.warning("쿠키 파일이 비어있습니다")
            return False
        
        logger.debug("쿠키가 유효합니다 (생성 후 %d일 경과)", int(cookie_age_days))
        return True
        
    except Exception as e:
        logger.error("쿠키 파일 확인 중 오류: %s", e)
        return False


def should_refresh_cookie(cookie_file: str = DEFAULT_COOKIE_FILE) -> bool:
    """
    쿠키를 갱신해야 하는지 확인.
    
    Returns:
        bool: 갱신이 필요하면 True
    """
    cookie_path = get_cookie_file_path(cookie_file)
    
    if not cookie_path.exists():
        return True
    
    try:
        mtime = cookie_path.stat().st_mtime
        cookie_age = time.time() - mtime
        cookie_age_days = cookie_age / (24 * 3600)
        
        # 갱신 주기보다 오래되었으면 갱신 필요
        return cookie_age_days > COOKIE_REFRESH_INTERVAL_DAYS
    except Exception:
        return True


def ensure_valid_cookie(
    cookie_file: str = DEFAULT_COOKIE_FILE,
    auto_refresh: bool = True,
) -> bool:
    """
    쿠키가 유효한지 확인하고, 필요시 자동으로 갱신합니다.
    
    Args:
        cookie_file: 쿠키 파일 경로
        auto_refresh: 자동 갱신 여부 (False면 갱신하지 않고 확인만)
    
    Returns:
        bool: 쿠키가 유효하면 True, 없거나 갱신 실패하면 False
    
    Note:
        프로덕션 환경에서는 수동 로그인이 필요하므로,
        자동 갱신은 제한적으로만 작동합니다.
    """
    if is_cookie_valid(cookie_file):
        logger.info("쿠키가 유효합니다")
        return True
    
    if not auto_refresh:
        logger.warning("쿠키가 유효하지 않지만 자동 갱신이 비활성화되어 있습니다")
        return False
    
    # 쿠키 갱신 시도 (프로덕션에서는 제한적)
    logger.warning("쿠키가 만료되었습니다. 수동 갱신이 필요합니다")
    logger.info("쿠키 갱신 방법:")
    logger.info("  1. python dev/save_twitter_cookies.py 실행")
    logger.info("  2. 또는 Twitter API 사용 고려")
    
    return False


def initialize_cookie_if_needed(
    cookie_file: str = DEFAULT_COOKIE_FILE,
    headless: bool = False,
) -> bool:
    """
    쿠키가 없거나 만료된 경우 초기화를 시도합니다.
    
    Args:
        cookie_file: 쿠키 파일 경로
        headless: 헤드리스 모드 여부 (False 권장, 로그인 필요)
    
    Returns:
        bool: 쿠키 초기화 성공 여부
    
    Note:
        프로덕션 환경에서는:
        1. 배포 시점에 한 번만 수동으로 실행: python dev/save_twitter_cookies.py
    """
    if is_cookie_valid(cookie_file):
        logger.info("쿠키가 이미 유효합니다")
        return True
    
    logger.info("쿠키 초기화 시작...")
    logger.info("브라우저가 열리면 X.com에 로그인해주세요")
    
    try:
        success = save_twitter_cookies(cookie_file=cookie_file, headless=headless)
        if success:
            logger.info("쿠키 초기화 완료")
        else:
            logger.error("쿠키 초기화 실패")
        return success
    except Exception as e:
        logger.error("쿠키 초기화 중 오류: %s", e)
        return False


def delete_expired_cookie_file(cookie_file: str = DEFAULT_COOKIE_FILE) -> bool:
    """
    만료된 쿠키 파일을 삭제합니다.
    
    Args:
        cookie_file: 쿠키 파일 경로
    
    Returns:
        bool: 삭제 성공 여부
    """
    cookie_path = get_cookie_file_path(cookie_file)
    
    if not cookie_path.exists():
        logger.debug("쿠키 파일이 없습니다: %s", cookie_path)
        return False
    
    try:
        cookie_path.unlink()
        logger.info("만료된 쿠키 파일 삭제: %s", cookie_path)
        return True
    except Exception as e:
        logger.error("쿠키 파일 삭제 실패: %s", e)
        return False


async def get_trend_keywords_with_auto_cookie(
    *,
    headless: bool = True,
    max_trends: int = 30,
    cookie_file: str = DEFAULT_COOKIE_FILE,
    excluded_texts: Optional[Set[str]] = None,
    page_timeout_ms: int = 60_000,
) -> list[str]:
    """
    쿠키를 자동으로 확인하고 트렌드 키워드를 가져옵니다.
    
    Args:
        headless: 헤드리스 모드 여부
        max_trends: 최대 수집할 트렌드 개수
        cookie_file: 쿠키 파일 경로
        excluded_texts: 제외할 텍스트 목록
        page_timeout_ms: 페이지 타임아웃 (밀리초)
    
    Returns:
        List[str]: 키워드 리스트
    
    Raises:
        FileNotFoundError: 쿠키 파일이 없거나 만료된 경우
    """
    # 쿠키 유효성 확인 (twitter_cookie_manager의 책임)
    if not is_cookie_valid(cookie_file):
        # 쿠키 파일이 없거나 만료된 경우 삭제
        delete_expired_cookie_file(cookie_file)
        raise FileNotFoundError(
            f"쿠키 파일이 없거나 만료되었습니다: {cookie_file}\n"
            f"먼저 쿠키를 저장하세요: python dev/save_twitter_cookies.py"
        )
    
    # 트렌드 크롤링 시도 (twitter_crawler 호출)
    try:
        result = await get_trend_keywords(
            headless=headless,
            max_trends=max_trends,
            cookie_file=cookie_file,
            excluded_texts=excluded_texts,
            page_timeout_ms=page_timeout_ms,
        )
        
        # 빈 결과가 반환된 경우 쿠키 만료로 간주하고 쿠키 파일 삭제
        if not result or len(result) == 0:
            logger.warning("트렌드 키워드가 수집되지 않았습니다. 쿠키가 만료되었을 수 있습니다.")
            delete_expired_cookie_file(cookie_file)
            raise FileNotFoundError(
                f"쿠키가 만료되었습니다: {cookie_file}\n"
                f"쿠키를 갱신하세요: python dev/save_twitter_cookies.py"
            )
        
        return result
    except Exception as e:
        # 크롤링 중 오류 발생 시 쿠키 만료 가능성 확인
        logger.error("트렌드 크롤링 중 오류 발생: %s", e)
        # 쿠키 파일 삭제는 하지 않음 (다른 오류일 수 있으므로)
        raise


async def background_cookie_refresh_task(
    cookie_file: str = DEFAULT_COOKIE_FILE,
    check_interval_hours: int = 24,
) -> None:
    """
    백그라운드에서 주기적으로 쿠키를 확인하고 갱신하는 태스크.
    
    Args:
        cookie_file: 쿠키 파일 경로
        check_interval_hours: 확인 주기 (시간)
    
    Note:
        완전 자동 갱신을 위해서는 Twitter API나 헤드리스 브라우저 자동화가 필요합니다.
        현재는 쿠키 만료만 감지하고 알림만 제공합니다.
    """
    logger.info("쿠키 자동 갱신 태스크 시작 (확인 주기: %d시간)", check_interval_hours)
    
    while True:
        try:
            await asyncio.sleep(check_interval_hours * 3600)  # 시간을 초로 변환
            
            if should_refresh_cookie(cookie_file):
                logger.warning("쿠키 갱신이 필요합니다: %s", cookie_file)
                # TODO: 자동 갱신 로직 (Twitter API 또는 헤드리스 자동화)
                # 현재는 알림만 제공
                
        except asyncio.CancelledError:
            logger.info("쿠키 갱신 태스크 취소됨")
            break
        except Exception as e:
            logger.error("쿠키 갱신 태스크 오류: %s", e)
            await asyncio.sleep(3600)  # 오류 시 1시간 후 재시도


__all__ = [
    "is_cookie_valid",
    "should_refresh_cookie",
    "ensure_valid_cookie",
    "initialize_cookie_if_needed",
    "delete_expired_cookie_file",
    "get_trend_keywords_with_auto_cookie",
    "background_cookie_refresh_task",
    "get_cookie_file_path",
]

