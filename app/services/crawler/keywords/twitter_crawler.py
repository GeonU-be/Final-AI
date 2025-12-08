"""
Twitter(X.com) 실시간 트렌드 키워드 크롤러.

Playwright를 사용해 X.com 트렌딩 페이지에서 키워드를 수집한다.
로그인이 필요하므로 쿠키 파일을 사용한다.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Dict, List, Optional, Set

from playwright.async_api import async_playwright
from playwright.sync_api import sync_playwright  # save_twitter_cookies에서 사용

logger = logging.getLogger(__name__)

TREND_URL = "https://x.com/explore/tabs/trending"
LOGIN_URL = "https://x.com/i/flow/login"
DEFAULT_COOKIE_FILE = "twitter_cookies.json"

# UI 텍스트 제외 목록
EXCLUDED_TEXTS: Set[str] = {
    "Home",
    "Explore",
    "Notifications",
    "Messages",
    "Grok",
    "Lists",
    "Bookmarks",
    "Communities",
    "Premium",
    "Profile",
    "More",
    "Post",
    "Trending",
    "For You",
    "Following",
    "Search",
    "News",
    "Sports",
    "Entertainment",
    "See new posts",
    "To view keyboard shortcuts",
    "View keyboard shortcuts",
    "Promoted by",
    "Only on X",
    "Trending in",
    "posts",
    "게시물",
    "트윗",
    "·",
    "1",
    "2",
    "3",
    "4",
    "5",
    "홈",
    "탐색",
    "알림",
    "메시지",
    "검색",
    "더보기",
    "게시",
    "트렌드",
    "Log in",
    "Sign up",
    "Don't miss what's happening",
    "People on X are the first to know",
    "New to X?",
}


def _valid_text(text: str, excluded_texts: Set[str]) -> bool:
    """UI 문구를 제외하고 키워드 후보만 남긴다."""
    if not text or len(text) < 2 or len(text) > 100:
        return False
    if text.startswith("http"):
        return False
    if text.startswith("@"):
        return False
    if text.isdigit():
        return False
    if text == "·":
        return False
    if len(text.split()) > 15:  # 너무 긴 텍스트 제외
        return False
    if text in excluded_texts:
        return False
    if any(excluded in text for excluded in excluded_texts):
        return False
    return True


def save_twitter_cookies(
    cookie_file: str = DEFAULT_COOKIE_FILE,
    headless: bool = False,
) -> bool:
    """
    트위터(X.com) 로그인 후 쿠키를 저장합니다.

    Args:
        cookie_file: 쿠키 파일 경로
        headless: 헤드리스 모드 여부 (False 권장, 로그인 필요)

    Returns:
        bool: 쿠키 저장 성공 여부
    """
    logger.info("트위터 쿠키 저장 시작: %s", cookie_file)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ],
        )

        # 봇 감지 우회를 위한 컨텍스트 설정
        viewport_size = {"width": 1920, "height": 1080}
        headers_dict = {
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        }
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport=viewport_size,
            java_script_enabled=True,
            bypass_csp=True,
            ignore_https_errors=False,
            extra_http_headers=headers_dict,
        )

        page = context.new_page()

        # 봇 감지 우회 스크립트 주입
        anti_bot_script = (
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined }); "
            "window.chrome = { runtime: {} }; "
            "Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] }); "
            "Object.defineProperty(navigator, 'languages', { get: () => ['ko-KR', 'ko', 'en-US', 'en'] }); "
            "const originalQuery = window.navigator.permissions.query; "
            "window.navigator.permissions.query = (parameters) => "
            "(parameters.name === 'notifications' ? Promise.resolve({ state: Notification.permission }) : originalQuery(parameters)); "
            "const getParameter = WebGLRenderingContext.getParameter; "
            "WebGLRenderingContext.prototype.getParameter = function(parameter) { "
            "if (parameter === 37445) { return 'Intel Inc.'; } "
            "if (parameter === 37446) { return 'Intel Iris OpenGL Engine'; } "
            "return getParameter(parameter); };"
        )
        page.add_init_script(anti_bot_script)

        # 로그인 페이지로 이동
        logger.info("로그인 페이지 접속: %s", LOGIN_URL)
        try:
            page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
            time.sleep(5)  # 페이지 완전 로드 대기
        except Exception as e:
            logger.error("로그인 페이지 접속 실패: %s", e)
            browser.close()
            return False

        # 로그인 완료 대기 (최대 5분)
        logger.info("로그인 완료를 기다립니다...")
        max_wait_time = 300  # 5분
        check_interval = 3  # 3초마다 확인
        start_time = time.time()
        login_completed = False

        while time.time() - start_time < max_wait_time:
            elapsed = int(time.time() - start_time)
            time.sleep(check_interval)

            try:
                current_url = page.url
                page_content = page.content()

                # 로그인 완료 확인 조건
                is_not_login_page = "login" not in current_url.lower() and "flow" not in current_url.lower()
                has_no_login_ui = "Log in" not in page_content and "Sign up" not in page_content

                if is_not_login_page and has_no_login_ui:
                    # 추가 확인: 홈 피드나 트렌드 관련 요소가 있는지
                    if (
                        "explore" in current_url.lower()
                        or "home" in current_url.lower()
                        or len(page.query_selector_all("nav")) > 0
                    ):
                        logger.info("로그인 완료 감지! (%d초 경과)", elapsed)
                        login_completed = True
                        break

                # 진행 상황 표시 (30초마다)
                if elapsed % 30 == 0 and elapsed > 0:
                    logger.info("로그인 대기 중... (%d초 경과, 최대 %d초)", elapsed, max_wait_time)
            except Exception:
                # 페이지 접근 오류는 무시하고 계속 대기
                pass

        if not login_completed:
            logger.warning("로그인 자동 감지 실패 (%d초 경과)", max_wait_time)
            browser.close()
            return False

        # 로그인 상태 확인: 트렌드 페이지로 이동 시도
        logger.info("로그인 상태 확인 중...")
        try:
            page.goto(TREND_URL, wait_until="domcontentloaded", timeout=60000)
            time.sleep(5)
        except Exception as e:
            logger.warning("트렌드 페이지 이동 중 오류: %s", e)

        # 로그인 페이지로 리다이렉트되었는지 확인
        current_url = page.url
        page_content = page.content()

        if "login" in current_url.lower() or "flow" in current_url.lower():
            logger.error("로그인이 완료되지 않은 것 같습니다. (현재 URL: %s)", current_url)
            browser.close()
            return False

        if "Log in" in page_content or "Sign up" in page_content:
            logger.error("로그인 페이지가 여전히 표시되고 있습니다.")
            browser.close()
            return False

        # 쿠키 저장
        cookies = context.cookies()
        with open(cookie_file, "w", encoding="utf-8") as f:
            json.dump(cookies, f, ensure_ascii=False, indent=2)

        logger.info("쿠키 저장 완료: %s (%d개)", cookie_file, len(cookies))
        browser.close()
        return True


async def crawl_twitter_trends(
    *,
    headless: bool = True,
    max_trends: int = 30,
    cookie_file: str = DEFAULT_COOKIE_FILE,
    excluded_texts: Optional[Set[str]] = None,
    page_timeout_ms: int = 60_000,
) -> Dict[str, object]:
    """
    트위터(X.com) 트렌드 키워드를 크롤링한다.

    Args:
        headless: 헤드리스 모드 여부
        max_trends: 최대 수집할 트렌드 개수
        cookie_file: 쿠키 파일 경로
        excluded_texts: 제외할 텍스트 목록
        page_timeout_ms: 페이지 타임아웃 (밀리초)

    Returns:
        dict: {"total_trends": int, "source": str, "collected_at": str, "trends": [{"keyword": str}, ...]}
    """
    excluded = excluded_texts or EXCLUDED_TEXTS
    trends: List[Dict[str, str]] = []
    found_keywords: Set[str] = set()

    # 최종 필터링에서 일부가 제외될 수 있으므로 여유분을 두고 수집
    target_collect_count = max_trends + 10

    # 쿠키 파일 존재 여부 확인 (유효성 확인은 twitter_cookie_manager에서 처리)
    if not os.path.exists(cookie_file):
        raise FileNotFoundError(
            f"❌ 쿠키 파일을 찾을 수 없습니다: {cookie_file}\n"
            f"   먼저 save_twitter_cookies()를 실행하여 쿠키를 저장하세요."
        )

    async with async_playwright() as p:
        # 봇 감지 우회를 위한 브라우저 설정
        browser = await p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ],
        )

        # 봇 감지 우회를 위한 컨텍스트 설정
        viewport_size = {"width": 1920, "height": 1080}
        headers_dict = {
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        }
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport=viewport_size,
            java_script_enabled=True,
            bypass_csp=True,
            ignore_https_errors=False,
            extra_http_headers=headers_dict,
        )

        # 저장된 쿠키 로드
        logger.info("쿠키 파일 로드 중: %s", cookie_file)
        with open(cookie_file, "r", encoding="utf-8") as f:
            cookies = json.load(f)
        await context.add_cookies(cookies)
        logger.info("%d개의 쿠키를 로드했습니다.", len(cookies))

        page = await context.new_page()

        # 봇 감지 우회 스크립트 주입
        anti_bot_script = (
            "Object.defineProperty(navigator, 'webdriver', { get: () => undefined }); "
            "window.chrome = { runtime: {} }; "
            "Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] }); "
            "Object.defineProperty(navigator, 'languages', { get: () => ['ko-KR', 'ko', 'en-US', 'en'] }); "
            "const originalQuery = window.navigator.permissions.query; "
            "window.navigator.permissions.query = (parameters) => "
            "(parameters.name === 'notifications' ? Promise.resolve({ state: Notification.permission }) : originalQuery(parameters)); "
            "const getParameter = WebGLRenderingContext.getParameter; "
            "WebGLRenderingContext.prototype.getParameter = function(parameter) { "
            "if (parameter === 37445) { return 'Intel Inc.'; } "
            "if (parameter === 37446) { return 'Intel Iris OpenGL Engine'; } "
            "return getParameter(parameter); };"
        )
        await page.add_init_script(anti_bot_script)

        # 트위터 트렌딩 페이지 접속
        logger.info("트위터 트렌드 페이지 접속: %s", TREND_URL)

        try:
            try:
                await page.goto(TREND_URL, wait_until="domcontentloaded", timeout=page_timeout_ms)
            except Exception:
                logger.warning("초기 접속 실패, load 이벤트까지 대기 재시도")
                try:
                    await page.goto(TREND_URL, wait_until="load", timeout=page_timeout_ms)
                except Exception as e:
                    logger.error(f"페이지 로드 실패: {e}")
                    await browser.close()
                    return {
                        "total_trends": 0,
                        "source": TREND_URL,
                        "collected_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                        "trends": [],
                    }
            
            await asyncio.sleep(5)  # JavaScript 실행 대기

            # 쿠키 만료 확인 (실제 페이지 접속 후 확인)
            page_content = await page.content()
            if "Log in" in page_content or "Sign up" in page_content or "login" in page.url.lower():
                logger.warning("쿠키가 만료되었거나 로그인이 필요합니다.")
                logger.warning("쿠키 갱신이 필요합니다. 다음 명령을 실행하세요:")
                logger.warning("  python dev/save_twitter_cookies.py")
                # 쿠키 파일 삭제는 twitter_cookie_manager에서 처리해야 함
                await browser.close()
                return {
                    "total_trends": 0,
                    "source": TREND_URL,
                    "collected_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "trends": [],
                }

            # 트렌드 콘텐츠가 로드될 때까지 대기
            logger.info("트렌드 콘텐츠 로드 대기 중...")
            try:
                # 트렌드 항목이 나타날 때까지 대기
                await page.wait_for_selector("span.css-1jxf684", timeout=20000)
                logger.info("트렌드 페이지 로드 완료")
            except Exception:
                logger.debug("기본 선택자 대기 실패, 계속 진행...")

            # 추가 대기 (동적 콘텐츠 로드)
            await asyncio.sleep(3)

            # 스크롤하여 더 많은 트렌드 로드
            logger.info("스크롤하여 더 많은 트렌드 로드 중...")
            for scroll_idx in range(10):
                await page.evaluate("window.scrollBy(0, window.innerHeight)")
                await asyncio.sleep(2)
                if scroll_idx % 3 == 0:
                    await asyncio.sleep(2)

            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(3)

            # 방법 1: data-testid="trend" 요소에서 추출
            logger.info("트렌드 추출 중...")
            trend_elements = await page.query_selector_all('[data-testid="trend"]')

            for trend_elem in trend_elements:
                try:
                    # span.css-1jxf684.r-bcqeeo.r-1ttztb7.r-qvutc0.r-poiln3 클래스를 가진 모든 요소 찾기
                    spans = await trend_elem.query_selector_all(
                        "span.css-1jxf684.r-bcqeeo.r-1ttztb7.r-qvutc0.r-poiln3"
                    )

                    for span in spans:
                        text = (await span.inner_text()).strip()

                        if _valid_text(text, excluded) and text not in found_keywords:
                            found_keywords.add(text)
                            trends.append({"keyword": text})

                            if len(trends) >= target_collect_count:
                                break

                        if len(trends) >= target_collect_count:
                            break

                    if len(trends) >= target_collect_count:
                        break
                except Exception:
                    continue

            # 방법 2: 추가 추출 (백업)
            if len(trends) < target_collect_count:
                logger.info(
                    "추가 트렌드 추출 중... (현재 %d개, 목표: %d개)", len(trends), target_collect_count
                )

                trend_containers = await page.query_selector_all('[data-testid="trend"]')
                for container in trend_containers:
                    try:
                        spans = await container.query_selector_all(
                            "span.css-1jxf684.r-bcqeeo.r-1ttztb7.r-qvutc0.r-poiln3"
                        )

                        for span in spans:
                            text = (await span.inner_text()).strip()

                            if _valid_text(text, excluded) and text not in found_keywords:
                                found_keywords.add(text)
                                trends.append({"keyword": text})

                                if len(trends) >= target_collect_count:
                                    break

                            if len(trends) >= target_collect_count:
                                break

                        if len(trends) >= target_collect_count:
                            break
                    except Exception:
                        continue

            # 최종 필터링
            filtered_trends = []
            for trend in trends:
                keyword = trend.get("keyword", "")
                if keyword and _valid_text(keyword, excluded):
                    filtered_trends.append({"keyword": keyword})

            # 최종 필터링 후에도 max_trends 개수만큼 확보
            trends = filtered_trends[:max_trends]

            if len(trends) == 0:
                logger.warning("실제 트렌드를 찾을 수 없습니다. 쿠키가 만료되었을 수 있습니다.")
            else:
                logger.info("총 %d개 트렌드 키워드 수집 완료", len(trends))

        except Exception as e:
            logger.error("크롤링 오류: %s", e)
            import traceback

            traceback.print_exc()

        finally:
            await browser.close()

    # 결과 반환
    return {
        "total_trends": len(trends),
        "source": TREND_URL,
        "collected_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "trends": trends,
    }


async def get_trend_keywords(
    *,
    headless: bool = True,
    max_trends: int = 30,
    cookie_file: str = DEFAULT_COOKIE_FILE,
    excluded_texts: Optional[Set[str]] = None,
    page_timeout_ms: int = 60_000,
) -> List[str]:
    """
    Twitter(X.com)에서 키워드 텍스트만 리스트로 반환한다.

    Args:
        headless: 헤드리스 모드 여부
        max_trends: 최대 수집할 트렌드 개수
        cookie_file: 쿠키 파일 경로
        excluded_texts: 제외할 텍스트 목록
        page_timeout_ms: 페이지 타임아웃 (밀리초)

    Returns:
        List[str]: 키워드 리스트
    """
    result = await crawl_twitter_trends(
        headless=headless,
        max_trends=max_trends,
        cookie_file=cookie_file,
        excluded_texts=excluded_texts,
        page_timeout_ms=page_timeout_ms,
    )
    return [item["keyword"] for item in result.get("trends", []) if "keyword" in item]


__all__ = [
    "crawl_twitter_trends",
    "get_trend_keywords",
    "save_twitter_cookies",
    "TREND_URL",
    "LOGIN_URL",
    "DEFAULT_COOKIE_FILE",
    "EXCLUDED_TEXTS",
]

