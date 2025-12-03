"""
Google Trends 실시간 인기 검색어 크롤러.

Playwright를 사용해 한국(KR) 실시간 트렌드 페이지에서 키워드와 링크를 수집한다.
"""

from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional, Set

from playwright.sync_api import sync_playwright

logger = logging.getLogger(__name__)

TREND_URL = "https://trends.google.co.kr/trending?geo=KR"
EXCLUDED_TEXTS: Set[str] = {
    "Trends",
    "트렌드 상태",
    "트렌드 분석",
    "검색",
    "탐색",
    "실시간 인기",
    "홈",
    "전 세계",
    "지금",
    "에서 무엇을 검색하고 있는지 알아보세요",
    "검색 관심도",
    "지난 24시간",
    "이(가) 인기 있는 이유는 무엇일까요?",
    "상세 데이터 검토",
    "트렌드 데이터팀",
    "선별한 문제와 이벤트",
    "트렌드 활용법",
    "언론사",
    "자선단체",
    "전 세계에서",
    "Google 트렌드를 어떻게 사용하고 있는지",
    "확인해보세요",
    "Google 트렌드란 무엇인가요?",
    "Google 트렌드의 기본사항",
    "데이터에 관해 알아보기",
    "로그인",
    "개인정보처리방침",
    "고급 Google 트렌드",
    "도움말",
    "의견 보내기",
}


def _valid_text(text: str, excluded_texts: Set[str]) -> bool:
    """UI 문구를 제외하고 키워드 후보만 남긴다."""
    if not text or len(text) < 2 or len(text) > 100:
        return False
    if text.startswith("http"):
        return False
    if text in excluded_texts:
        return False
    if any(ex in text for ex in excluded_texts):
        return False
    return True


def _normalize_link(href: Optional[str]) -> str:
    """상대 경로를 절대 URL로 정규화."""
    if not href:
        return ""
    href = href.strip()
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return f"https://trends.google.co.kr{href}"
    return f"https://trends.google.co.kr/{href}"


def crawl_google_trends(
    *,
    headless: bool = True,
    max_trends: int = 80,
    excluded_texts: Optional[Set[str]] = None,
    page_timeout_ms: int = 60_000,
) -> Dict[str, object]:
    """
    구글 트렌드 실시간 인기 검색어를 크롤링한다.

    Returns:
        dict: {"total_trends": int, "trends": [{"keyword": str, "link": str}, ...]}
    """
    excluded = excluded_texts or EXCLUDED_TEXTS
    trends: List[Dict[str, str]] = []
    found: Set[str] = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        logger.info("Google Trends 접속: %s", TREND_URL)

        try:
            page.goto(TREND_URL, wait_until="networkidle", timeout=page_timeout_ms)
        except Exception:
            logger.warning("초기 접속 실패, load 이벤트까지 대기 재시도")
            page.goto(TREND_URL, wait_until="load", timeout=page_timeout_ms)

        # 동적 로딩 대기
        page.wait_for_timeout(8_000)

        # 트렌드 섹션 렌더링 대기
        try:
            page.wait_for_selector("c-wiz, [jsname], [jscontroller]", timeout=20_000)
        except Exception:
            logger.debug("트렌드 섹션 selector 대기 타임아웃")
        page.wait_for_timeout(5_000)

        # 추가 로드를 위해 스크롤
        for idx in range(20):
            page.evaluate("window.scrollBy(0, window.innerHeight)")
            page.wait_for_timeout(2_000)
            if idx % 5 == 0:
                page.wait_for_timeout(3_000)
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(3_000)

        # 방법 0: 테이블 기반 페이지 네비게이션
        page.wait_for_timeout(1_000)
        paged_round = 0
        while len(trends) < max_trends:
            paged_round += 1
            if paged_round > 20:
                break
            rows = page.query_selector_all("tbody tr")
            new_items = 0
            for row in rows:
                keyword_elem = row.query_selector(".mZ3RIc")
                if not keyword_elem:
                    continue
                text = (keyword_elem.inner_text() or "").strip()
                if not _valid_text(text, excluded) or text in found:
                    continue
                link_url = ""
                link_elem = row.query_selector("a")
                if link_elem:
                    link_url = _normalize_link(link_elem.get_attribute("href"))
                found.add(text)
                trends.append({"keyword": text, "link": link_url})
                new_items += 1
                if len(trends) >= max_trends:
                    break
            if len(trends) >= max_trends or new_items == 0:
                break
            next_btn = None
            for selector in (
                "[aria-label*='다음 페이지']",
                "[aria-label*='다음']",
                "[aria-label*='Next page']",
                "[aria-label*='Next']",
            ):
                try:
                    next_btn = page.query_selector(selector)
                except Exception:
                    next_btn = None
                if next_btn:
                    break
            if not next_btn:
                break
            try:
                next_btn.click()
                page.wait_for_timeout(2_000)
            except Exception:
                break

        # 방법 1: 주요 클래스 기반 추출
        if len(trends) < max_trends:
            for elem in page.query_selector_all(".mZ3RIc"):
                try:
                    text = (elem.inner_text() or "").strip()
                except Exception:
                    continue
                if not _valid_text(text, excluded) or text in found:
                    continue
                link_url = ""
                try:
                    parent = elem.evaluate_handle("el => el.closest('a')")
                    if parent:
                        link_url = _normalize_link(parent.get_attribute("href"))
                except Exception:
                    pass
                found.add(text)
                trends.append({"keyword": text, "link": link_url})
                if len(trends) >= max_trends:
                    break

        # 방법 2: 모든 링크에서 추출
        if len(trends) < max_trends:
            for link in page.query_selector_all("a"):
                try:
                    href = link.get_attribute("href") or ""
                    text = (link.inner_text() or "").strip()
                except Exception:
                    continue
                if not _valid_text(text, excluded) or text in found:
                    continue
                found.add(text)
                trends.append({"keyword": text, "link": _normalize_link(href)})
                if len(trends) >= max_trends:
                    break

        # 방법 3: 모든 텍스트 요소에서 추출
        if len(trends) < max_trends:
            for elem in page.query_selector_all("div, span, p, h1, h2, h3, h4, h5, h6"):
                try:
                    raw = (elem.inner_text() or "").strip()
                except Exception:
                    continue
                if not raw:
                    continue
                first_line = raw.split("\n")[0].strip()
                if not _valid_text(first_line, excluded) or first_line in found:
                    continue
                link_elem = elem.query_selector("a")
                link_url = _normalize_link(link_elem.get_attribute("href")) if link_elem else ""
                found.add(first_line)
                trends.append({"keyword": first_line, "link": link_url})
                if len(trends) >= max_trends:
                    break

        browser.close()

    trends = trends[:max_trends]
    logger.info("Google Trends 수집 완료: %s개", len(trends))
    return {"total_trends": len(trends), "trends": trends}


__all__ = ["crawl_google_trends", "TREND_URL", "EXCLUDED_TEXTS"]


def get_trend_keywords(
    *,
    headless: bool = True,
    max_trends: int = 80,
    excluded_texts: Optional[Set[str]] = None,
    page_timeout_ms: int = 60_000,
) -> List[str]:
    """
    Google Trends에서 키워드 텍스트만 리스트로 반환한다.
    """
    result = crawl_google_trends(
        headless=headless,
        max_trends=max_trends,
        excluded_texts=excluded_texts,
        page_timeout_ms=page_timeout_ms,
    )
    return [item["keyword"] for item in result.get("trends", []) if "keyword" in item]
