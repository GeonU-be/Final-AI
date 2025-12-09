"""
네이버 쇼핑 상품 크롤러 (비동기 버전).

undetected-chromedriver와 Selenium을 사용해 네이버 쇼핑 검색 페이지에서 상품 정보를 수집한다.
Selenium은 동기 라이브러리이므로 ThreadPoolExecutor로 감싸서 비동기 처리.
"""

from __future__ import annotations

import asyncio
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional
from urllib.parse import quote

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

logger = logging.getLogger(__name__)

# 공통 검색 URL 템플릿
NAVER_SEARCH_URL = "https://search.shopping.naver.com/ns/search?query={query}"
NAVER_BASE_URL = "https://www.naver.com"
NAVER_SHOPPING_BASE = "https://shopping.naver.com"


def build_search_url(keyword: str) -> str:
    """검색 키워드를 URL에 맞게 인코딩해 반환."""
    return NAVER_SEARCH_URL.format(query=quote(keyword))


def extract_url_from_text(text: str) -> str:
    """텍스트에서 URL 추출."""
    if not text:
        return ""
    match = re.search(r"(https?://[^\s]+)", text)
    return match.group(1).strip() if match else ""


def normalize_product_url(raw_url: str) -> str:
    """상품 URL 정규화."""
    if not raw_url:
        return ""
    
    bad_domains = ["help.pay.naver.com", "nid.naver.com"]
    
    candidate = raw_url.strip()
    if not candidate or candidate.startswith("javascript"):
        return ""
    if "http" not in candidate:
        embedded = extract_url_from_text(candidate)
        if embedded:
            candidate = embedded
    if candidate.startswith("//"):
        candidate = "https:" + candidate
    elif candidate.startswith("/"):
        candidate = f"{NAVER_SHOPPING_BASE}{candidate}"
    if any(domain in candidate for domain in bad_domains):
        return ""
    if "smartstore.naver.com/inflow/outlink/url" in candidate:
        return ""
    return candidate if candidate.startswith("http") else ""


def normalize_image_url(raw_url: str) -> str:
    """이미지 URL 정규화."""
    if not raw_url:
        return ""
    candidate = raw_url.strip().strip("'").strip('"')
    if not candidate or candidate.startswith("data:"):
        return ""
    if candidate.startswith("//"):
        candidate = "https:" + candidate
    elif candidate.startswith("/"):
        candidate = "https://shopping-phinf.pstatic.net" + candidate
    return candidate if candidate.startswith("http") else ""


def first_from_srcset(value: str) -> str:
    """srcset에서 첫 번째 URL 추출."""
    if not value:
        return ""
    for part in value.split(","):
        url_part = part.strip().split(" ")[0]
        if url_part:
            return url_part
    return ""


def extract_detail_specs(detail_driver) -> Dict[str, str]:
    """
    상품 상세 페이지에서 상품 정보를 추출합니다.
    attribute_wrapper div 클래스 내의 테이블 구조를 파싱합니다.

    Args:
        detail_driver: Selenium WebDriver 인스턴스

    Returns:
        dict: 상품 상세 정보 딕셔너리
    """
    specs = {}
    try:
        # 에러 페이지 확인
        page_title = detail_driver.title
        page_source = detail_driver.page_source
        
        if "상품이 존재하지 않습니다" in page_source or "상품이 존재하지 않습니다" in page_title:
            logger.debug("상품이 존재하지 않음 - 에러 페이지 감지")
            return specs
        
        # attribute_wrapper 클래스를 찾기
        try:
            attribute_wrapper = detail_driver.find_element(
                By.CSS_SELECTOR, "div[class*='attribute_wrapper']"
            )
        except NoSuchElementException:
            # 다른 가능한 선택자 시도
            try:
                attribute_wrapper = detail_driver.find_element(
                    By.CSS_SELECTOR, "div.attribute_wrapper"
                )
            except NoSuchElementException:
                return specs

        # 테이블 행(tr) 찾기
        rows = attribute_wrapper.find_elements(By.CSS_SELECTOR, "tr")

        for row in rows:
            try:
                # 각 행에서 th(제목)와 td(값) 찾기
                th_elem = row.find_element(By.CSS_SELECTOR, "th")
                td_elem = row.find_element(By.CSS_SELECTOR, "td")

                th_text = th_elem.text.strip().rstrip(":")
                td_text = td_elem.text.strip()

                if th_text and td_text:
                    specs[th_text] = td_text
            except NoSuchElementException:
                continue
            except Exception as e:
                logger.debug(f"행 파싱 중 오류: {e}")
                continue

        # 만약 위 방법으로 정보를 못 찾았다면, 다른 구조 시도
        if not specs:
            try:
                tds = attribute_wrapper.find_elements(By.CSS_SELECTOR, "td")
                for i, td in enumerate(tds):
                    if i % 2 == 0:
                        if i + 1 < len(tds):
                            title = td.text.strip().rstrip(":")
                            value = tds[i + 1].text.strip()
                            if title and value:
                                specs[title] = value
            except Exception as e:
                logger.debug(f"대체 테이블 구조 파싱 실패: {e}")

    except Exception as e:
        logger.debug(f"상품 상세 정보 추출 실패: {e}")

    return specs


def _crawl_naver_sync(
    keyword: str,
    max_products: int = 30,
    headless: bool = False,
) -> List[Dict[str, str]]:
    """
    네이버 쇼핑 검색 결과에서 상품을 수집 (동기 버전).
    
    주의: 이 함수는 내부적으로만 사용되며, ThreadPoolExecutor를 통해 비동기로 실행됩니다.
    외부에서는 async 함수인 crawl_naver_products()를 사용하세요.
    
    Args:
        keyword: 검색어
        max_products: 최대 수집 상품 수
        headless: 브라우저 헤드리스 여부
    
    Returns:
        List[Dict[str, str]]: 수집된 상품 리스트
    """
    products: List[Dict[str, str]] = []
    skipped_count = 0
    product_items = []
    driver = None

    search_url = build_search_url(keyword)
    logger.info("네이버 쇼핑 크롤링 시작: '%s' (%s)", keyword, search_url)

    try:
        # undetected-chromedriver 설정 (봇 감지 우회)
        options = uc.ChromeOptions()

        if headless:
            options.add_argument("--headless=new")
            # 헤드리스 모드에서 봇 감지 우회를 위한 추가 옵션
            options.add_argument("--disable-gpu")
            options.add_argument("--disable-software-rasterizer")

        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-infobars")
        options.add_argument("--disable-extensions")
        # 더 최신 User-Agent 사용
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

        logger.debug("브라우저 시작 중...")
        driver = uc.Chrome(options=options, version_main=None)

        logger.debug("접속 중: %s", search_url)

        # 먼저 네이버 메인 페이지로 접속 (쿠키/세션 초기화)
        logger.debug("네이버 메인 페이지 접속 중...")
        driver.get(NAVER_BASE_URL)
        time.sleep(1.5)  # 3초 -> 1.5초로 단축

        if not headless:
            time.sleep(3)  # 5초 -> 3초로 단축

        # 검색 페이지로 이동
        logger.debug("검색 페이지로 이동 중: %s", search_url)
        driver.get(search_url)

        # 페이지 로드 대기 (속도 개선)
        logger.debug("페이지 로딩 대기 중...")
        if not headless:
            time.sleep(5)  # 8초 -> 5초로 단축
        else:
            time.sleep(5)  # 8초 -> 5초로 단축
        
        # 페이지가 완전히 로드될 때까지 명시적 대기 (타임아웃 단축)
        try:
            WebDriverWait(driver, 10).until(  # 15초 -> 10초로 단축
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except Exception:
            logger.debug("페이지 로딩 완료 대기 중 타임아웃 (계속 진행)")
        
        # 추가 대기 (동적 콘텐츠 로드를 위해) - 단축
        time.sleep(1)  # 2초 -> 1초로 단축

        # 접속 제한 체크 및 재시도 (속도 개선)
        page_title = driver.title
        page_source = driver.page_source
        access_restricted = False

        if "접속이 일시적으로 제한" in page_source or "Access Denied" in page_title:
            logger.warning("⚠ 접속 제한 페이지가 감지되었습니다.")
            access_restricted = True
            if not headless:
                logger.warning("⚠ 브라우저 창에서 직접 새로고침을 시도해보세요.")
                time.sleep(8)  # 15초 -> 8초로 단축
            else:
                # 헤드리스 모드에서는 더 긴 대기 후 재시도
                logger.warning("⚠ 헤드리스 모드: 접속 제한 대기 중...")
                time.sleep(5)  # 10초 -> 5초로 단축
                # 페이지 새로고침 시도
                try:
                    driver.refresh()
                    time.sleep(3)  # 5초 -> 3초로 단축
                    page_source = driver.page_source
                    page_title = driver.title
                    if "접속이 일시적으로 제한" not in page_source and "Access Denied" not in page_title:
                        logger.info("✅ 접속 제한 해제됨")
                        access_restricted = False
                except Exception as e:
                    logger.debug(f"페이지 새로고침 실패: {e}")

        # 접속 제한이 해제되지 않았으면 경고만 하고 계속 진행
        if access_restricted:
            logger.warning("⚠ 접속 제한이 감지되었지만 계속 진행합니다...")

        # 페이지가 완전히 로드될 때까지 대기 (중복 제거 - 이미 위에서 대기했으므로)
        # 추가 대기 (동적 콘텐츠 로드를 위해) - 단축
        time.sleep(1)  # 3초 -> 1초로 단축

        # 스크롤하여 동적 콘텐츠 로드 (속도 개선)
        logger.debug("상품 로딩 중...")
        scroll_attempts = 0
        max_scroll_attempts = 10  # 15 -> 10으로 단축
        while scroll_attempts < max_scroll_attempts:
            driver.execute_script("window.scrollBy(0, window.innerHeight * 0.5)")
            time.sleep(1.5)  # 2초 -> 1.5초로 단축
            scroll_attempts += 1

            if scroll_attempts % 2 == 0:  # 3 -> 2로 변경하여 더 자주 체크
                try:
                    current_count = len(
                        driver.find_elements(
                            By.CSS_SELECTOR, "div[class*='basicProductCardInformation']"
                        )
                    )
                    if current_count >= max_products * 1.2:  # 1.5 -> 1.2로 변경하여 더 빨리 중단
                        logger.debug(
                            "충분한 상품 로드 완료: %s개 (목표: %s개)",
                            current_count,
                            max_products,
                        )
                        break
                except Exception as e:
                    logger.debug(f"스크롤 중 상품 수 확인 실패: {e}")
                    pass

        time.sleep(2)  # 3초 -> 2초로 단축

        # 상품 리스트 찾기
        product_selectors = [
            "div[class*='basicProductCard_basic_product_card']",
            "li[class*='productCardList_item']",
            "div[class*='basicProductCardInformation']",
            "div[class*='productCardInfo']",
            "div[class*='productCard_wrap']",
            "div[class*='productCardThumbnail']",
        ]

        for selector in product_selectors:
            try:
                items = driver.find_elements(By.CSS_SELECTOR, selector)
                if items and len(items) > 0:
                    product_items = items
                    logger.debug("발견된 상품 수: %s개 (셀렉터: %s)", len(items), selector)
                    break
            except Exception as selector_error:
                logger.debug("셀렉터 '%s' 처리 중 오류: %s", selector, selector_error)
                continue

        # 기본 셀렉터로 찾지 못했으면 더 넓은 범위로 재검색
        if not product_items:
            logger.warning("기본 셀렉터로 찾지 못함. 넓은 범위로 재검색 중...")
            try:
                # 더 일반적인 셀렉터 시도
                fallback_selectors = [
                    "div[class*='product']",
                    "li[class*='item']",
                    "div[class*='card']",
                ]
                for selector in fallback_selectors:
                    try:
                        items = driver.find_elements(By.CSS_SELECTOR, selector)
                        # 너무 많은 요소는 제외 (노이즈)
                        if items and 5 <= len(items) <= 200:
                            product_items = items
                            logger.debug("넓은 범위 검색으로 %s개 요소 발견 (셀렉터: %s)", len(items), selector)
                            break
                    except Exception:
                        continue
            except Exception as e:
                logger.warning("넓은 범위 검색 중 오류: %s", e)

        if not product_items:
            logger.warning("⚠ 상품 리스트를 찾을 수 없습니다.")
            logger.warning("현재 URL: %s", driver.current_url)
            logger.warning("페이지 제목: %s", driver.title)
            # 디버깅을 위해 페이지 소스 일부 출력
            try:
                page_source_preview = driver.page_source[:500]
                logger.debug("페이지 소스 미리보기: %s", page_source_preview)
            except Exception:
                pass
        else:
            # ============================================================
            # 1단계: 검색 결과 페이지에서 모든 상품의 기본 정보 수집
            # ============================================================
            logger.debug("📋 1단계: 검색 결과 페이지에서 기본 정보 수집 중...")
            basic_products = []  # 기본 정보만 담을 리스트

            for idx, item_elem in enumerate(product_items[:max_products]):
                try:
                    if idx > 0:
                        time.sleep(0.2)  # 짧은 대기

                    search_scope = item_elem
                    try:
                        search_scope = item_elem.find_element(
                            By.XPATH,
                            ".//ancestor::li[contains(@class,'productCardList_item')]",
                        )
                    except Exception as e:
                        logger.debug(f"카드 스코프 찾기 실패: {e}")
                        pass

                    try:
                        driver.execute_script(
                            "arguments[0].scrollIntoView({block: 'center', inline: 'nearest'})",
                            search_scope,
                        )
                        time.sleep(0.2)
                    except Exception as e:
                        logger.debug(f"스크롤 뷰 이동 실패: {e}")
                        pass

                    # 상품명 추출
                    title = ""
                    title_selectors = [
                        "span[class*='basicProductCard_title']",
                        "strong[class*='basicProductCard_title']",
                        "div[class*='basicProductCardInformation'] strong[class*='title']",
                        "div[class*='basicProductCardInformation'] span[class*='title']",
                        "a[class*='basicProductCard_link'] strong",
                        "a[class*='basicProductCard_link'] span",
                        "a[class*='basicProductCard_link']",
                        "strong[class*='productCardTitle']",
                        "a[class*='productCardTitle']",
                        "div[class*='productCardInformation'] strong",
                        "span[class*='productTitle']",
                    ]

                    disallowed_titles = {
                        "디지털/가전",
                        "패션",
                        "뷰티",
                        "식품",
                        "생활",
                        "가구",
                        "도서",
                        "스포츠",
                        "완구",
                        "반려동물",
                    }
                    warning_keywords = [
                        "출발",
                        "배송",
                        "멤버십",
                        "내일배송",
                        "오늘출발",
                        "무료반품",
                        "리뷰",
                        "할인",
                        "쿠폰",
                        "혜택",
                        "회원",
                        "N도착",
                        "N내일",
                    ]

                    def looks_like_bad_title(text: str) -> bool:
                        if not text:
                            return True
                        normalized = text.strip()
                        if len(normalized) < 4:
                            return True
                        lowered = normalized.lower()
                        for keyword in warning_keywords:
                            if keyword in normalized:
                                return True
                        if lowered.replace(" ", "").isdigit():
                            return True
                        if any(char.isdigit() for char in normalized) and all(
                            ch.isdigit() or ch in ":./"
                            for ch in normalized
                            if not ch.isalpha()
                        ):
                            return True
                        return False

                    for sel in title_selectors:
                        try:
                            title_elem = search_scope.find_element(By.CSS_SELECTOR, sel)
                            if title_elem:
                                title_text = title_elem.text.strip()
                                if ">" in title_text:
                                    parts = title_text.split(">")
                                    if len(parts) > 1:
                                        title_text = parts[-1].strip()

                                if title_text and len(title_text) >= 4:
                                    if (
                                        title_text not in disallowed_titles
                                        and not looks_like_bad_title(title_text)
                                    ):
                                        title = title_text
                                        break
                        except Exception as e:
                            logger.debug(f"타이틀 셀렉터 '{sel}' 실패: {e}")
                            continue

                    if not title:
                        try:
                            rich_links = search_scope.find_elements(
                                By.CSS_SELECTOR, "a[class*='basicProductCard_link']"
                            )
                            for link in rich_links:
                                fallback = (
                                    (link.get_attribute("aria-label") or "").strip()
                                    or (link.get_attribute("title") or "").strip()
                                    or (
                                        link.get_attribute("data-i18n-key") or ""
                                    ).strip()
                                )
                                if (
                                    fallback
                                    and fallback not in disallowed_titles
                                    and not looks_like_bad_title(fallback)
                                ):
                                    title = fallback
                                    break
                        except Exception as e:
                            logger.debug(f"타이틀 폴백 (rich_links) 실패: {e}")
                            pass

                    if not title:
                        try:
                            all_links = search_scope.find_elements(By.CSS_SELECTOR, "a")
                            for link in all_links:
                                link_text = link.text.strip()
                                if link_text and len(link_text) >= 4:
                                    if ">" in link_text:
                                        parts = link_text.split(">")
                                        if len(parts) > 1:
                                            link_text = parts[-1].strip()
                                    if (
                                        link_text not in disallowed_titles
                                        and not looks_like_bad_title(link_text)
                                    ):
                                        title = link_text
                                        break
                        except Exception as e:
                            logger.debug(f"타이틀 폴백 (all_links) 실패: {e}")
                            pass

                    if not title:
                        try:
                            block_text = (search_scope.text or "").strip()
                            if block_text:
                                first_line = block_text.split("\n")[0].strip()
                                if (
                                    first_line
                                    and first_line not in disallowed_titles
                                    and not looks_like_bad_title(first_line)
                                ):
                                    title = first_line
                        except Exception as e:
                            logger.debug(f"타이틀 폴백 (block_text) 실패: {e}")
                            pass

                    # 상품 링크 추출
                    product_link = ""
                    try:
                        link_selectors = [
                            "a[class*='basicProductCard_link']",
                            "a",
                            "div[class*='basicProductCardInformation'] a",
                            "div[class*='productCardInformation'] a",
                            "a[class*='productCardTitle']",
                            "a[href*='shopping.naver.com']",
                        ]

                        for selector in link_selectors:
                            try:
                                link_elems = search_scope.find_elements(
                                    By.CSS_SELECTOR, selector
                                )
                                if not link_elems:
                                    continue
                                for link_elem in link_elems:
                                    href_value = link_elem.get_attribute("href")
                                    if href_value:
                                        normalized = normalize_product_url(href_value)
                                        if normalized:
                                            product_link = normalized
                                            break
                                if product_link:
                                    break
                            except Exception as e:
                                logger.debug(f"링크 셀렉터 '{selector}' 처리 실패: {e}")
                                continue
                    except Exception as e:
                        logger.debug(f"상품 링크 추출 실패: {e}")
                        pass

                    # 가격 정보 추출
                    original_price = ""
                    displayed_price = ""

                    try:
                        price_containers = item_elem.find_elements(
                            By.CSS_SELECTOR,
                            "div[class*='productCardPrice'] span[class*='price'], "
                            "div[class*='productCardPrice'] em[class*='price'], "
                            "div[class*='productCardPrice'] strong[class*='price'], "
                            "span[class*='price_num'], "
                            "em[class*='price'], "
                            "strong[class*='price']",
                        )
                        price_texts = []
                        for container in price_containers:
                            text = container.text.strip()
                            if text:
                                if (
                                    "원대" in text
                                    or "원부터" in text
                                    or "원이상" in text
                                ):
                                    continue
                                price_texts.append(text)

                        if not price_texts:
                            fallback_text = item_elem.text.strip()
                            if fallback_text:
                                price_texts.append(fallback_text)

                        price_candidates = []
                        for text in price_texts:
                            price_patterns = re.findall(r"([\d,]+)\s*원", text)
                            for match in price_patterns:
                                candidate_raw = match
                                candidate = candidate_raw.replace(",", "")

                                if (
                                    candidate
                                    and candidate.isdigit()
                                    and 4 <= len(candidate) <= 10
                                ):
                                    price_value = int(candidate)
                                    if price_value < 1000 or price_value > 100000000:
                                        continue

                                    if candidate not in [
                                        p.replace(",", "") for p in price_candidates
                                    ]:
                                        price_candidates.append(candidate_raw)

                        if price_candidates:
                            price_nums = [
                                (p.replace(",", ""), p) for p in price_candidates
                            ]
                            price_nums.sort(key=lambda x: int(x[0]))

                            displayed_price = price_nums[0][1] + "원"
                            if len(price_nums) > 1:
                                original_price = price_nums[-1][1] + "원"
                    except Exception as e:
                        logger.debug(f"가격 정보 추출 실패: {e}")
                        pass

                    # 썸네일 이미지 URL 추출
                    thumbnail_url = ""
                    try:
                        img_selectors = [
                            "div[class*='productCardThumbnail_thumbnail__KzO1N'] img",
                            "div[class*='productCardThumbnail'] img",
                            "div[class*='img_area'] img",
                            "img[class*='product']",
                            "img",
                        ]
                        candidate_attrs = [
                            "src",
                            "data-src",
                            "data-lazy-src",
                            "data-srcset",
                            "srcset",
                        ]

                        for selector in img_selectors:
                            try:
                                img_elems = search_scope.find_elements(
                                    By.CSS_SELECTOR, selector
                                )
                                for img_elem in img_elems:
                                    candidate_url = ""
                                    for attr in candidate_attrs:
                                        value = img_elem.get_attribute(attr)
                                        if not value:
                                            continue
                                        if attr.endswith("srcset"):
                                            candidate_url = first_from_srcset(value)
                                        else:
                                            candidate_url = value.strip()
                                        if candidate_url:
                                            break
                                    candidate_url = normalize_image_url(candidate_url)
                                    if candidate_url:
                                        thumbnail_url = candidate_url
                                        break
                                if thumbnail_url:
                                    break
                            except Exception as e:
                                logger.debug(
                                    f"썸네일 셀렉터 '{selector}' 처리 실패: {e}"
                                )
                                continue

                        if not thumbnail_url:
                            source_elems = search_scope.find_elements(
                                By.CSS_SELECTOR, "source"
                            )
                            for source in source_elems:
                                srcset_val = source.get_attribute(
                                    "srcset"
                                ) or source.get_attribute("data-srcset")
                                candidate_url = normalize_image_url(
                                    first_from_srcset(srcset_val)
                                )
                                if candidate_url:
                                    thumbnail_url = candidate_url
                                    break

                        if not thumbnail_url:
                            bg_selectors = [
                                "div[class*='productCardThumbnail']",
                                "div[class*='thumbnail']",
                            ]
                            for selector in bg_selectors:
                                try:
                                    bg_elems = search_scope.find_elements(
                                        By.CSS_SELECTOR, selector
                                    )
                                    for bg_elem in bg_elems:
                                        candidate_url = ""
                                        style_attr = (
                                            bg_elem.get_attribute("style") or ""
                                        )
                                        if style_attr:
                                            match = re.search(
                                                r"url\((.*?)\)", style_attr
                                            )
                                            if match:
                                                candidate_url = (
                                                    match.group(1)
                                                    .strip()
                                                    .strip("'")
                                                    .strip('"')
                                                )
                                        if not candidate_url:
                                            data_lazy = (
                                                bg_elem.get_attribute(
                                                    "data-lazy-background"
                                                )
                                                or bg_elem.get_attribute(
                                                    "data-background-image"
                                                )
                                                or ""
                                            )
                                            candidate_url = (
                                                data_lazy.strip().strip("'").strip('"')
                                            )
                                        candidate_url = normalize_image_url(
                                            candidate_url
                                        )
                                        if candidate_url:
                                            thumbnail_url = candidate_url
                                            break
                                    if thumbnail_url:
                                        break
                                except Exception as e:
                                    logger.debug(
                                        f"썸네일 배경 이미지 셀렉터 '{selector}' 처리 실패: {e}"
                                    )
                                    continue
                    except Exception as e:
                        logger.debug(f"썸네일 이미지 추출 실패: {e}")
                        pass

                    # 타이틀이 없어도 링크가 있으면 수집
                    if not title and not product_link:
                        skipped_count += 1
                        if skipped_count <= 3 or idx >= len(product_items) - 5:
                            logger.warning(
                                "상품 %s/%s - 제목 추출 실패", idx + 1, len(product_items)
                            )
                        continue

                    if not title:
                        title = f"[제목 없음 - 상품 {idx+1}]"

                    # 기본 정보만 저장 (상세 정보는 나중에)
                    basic_product = {
                        "title": title,
                        "original_price": original_price,
                        "displayed_price": displayed_price,
                        "product_link": product_link,
                        "thumbnail_url": thumbnail_url,
                        "detail_specs": {},  # 나중에 채울 예정
                    }
                    basic_products.append(basic_product)

                    if len(basic_products) >= max_products:
                        break

                except Exception as e:
                    logger.warning("상품 %s 기본 정보 추출 오류: %s", idx + 1, e)
                    continue

            logger.debug("✅ 1단계 완료: %s개 상품의 기본 정보 수집 완료", len(basic_products))

            # ============================================================
            # 2단계: 수집한 상품 링크들을 순회하면서 상세 정보 수집
            # ============================================================
            logger.debug("📋 2단계: %s개 상품의 상세 정보 수집 중...", len(basic_products))

            # 원래 창 핸들과 URL을 미리 저장 (2단계 시작 전)
            original_window = driver.current_window_handle
            original_url = driver.current_url

            # 상세 정보 수집용 탭을 미리 하나 생성 (재사용)
            detail_tab_handle = None
            try:
                driver.execute_script("window.open('');")
                detail_tab_handle = [
                    h for h in driver.window_handles if h != original_window
                ][0]
                driver.switch_to.window(original_window)  # 원래 창으로 복귀
            except Exception as e:
                logger.debug(f"상세 정보 수집용 탭 생성 실패: {e}")

            for idx, basic_product in enumerate(basic_products):
                product_link = basic_product.get("product_link", "")

                if not product_link:
                    logger.debug(
                        "상품 %s/%s: 링크 없음, 상세 정보 스킵",
                        idx + 1,
                        len(basic_products),
                    )
                    continue

                try:
                    logger.debug(
                        "상품 %s/%s: %s...",
                        idx + 1,
                        len(basic_products),
                        basic_product["title"][:50],
                    )

                    # 상세 정보 수집용 탭이 없으면 새로 생성
                    if (
                        detail_tab_handle is None
                        or detail_tab_handle not in driver.window_handles
                    ):
                        try:
                            driver.switch_to.window(original_window)
                            driver.execute_script("window.open('');")
                            detail_tab_handle = [
                                h
                                for h in driver.window_handles
                                if h != original_window
                            ][0]
                        except Exception as e:
                            logger.debug(f"탭 생성 실패: {e}")
                            # 탭 생성 실패 시 원래 창에서 직접 이동
                            driver.switch_to.window(original_window)
                            driver.get(product_link)
                            wait_time = 2 + (idx % 2)  # 2~3초 사이로 단축
                            time.sleep(wait_time)

                            try:
                                driver.execute_script("window.scrollBy(0, 500)")
                                time.sleep(0.5)  # 1초 -> 0.5초로 단축
                            except Exception:
                                pass

                            # 에러 페이지 확인
                            page_title = driver.title
                            page_source = driver.page_source
                            if (
                                "상품이 존재하지 않습니다" in page_source
                                or "상품이 존재하지 않습니다" in page_title
                            ):
                                logger.debug(
                                    "상품 %s: 상품이 존재하지 않음 (삭제/판매 중단)",
                                    idx + 1,
                                )
                                basic_product["detail_specs"] = {}
                                driver.get(original_url)
                                time.sleep(1)
                                continue

                            try:
                                WebDriverWait(driver, 5).until(
                                    EC.presence_of_element_located(
                                        (By.CSS_SELECTOR, "div[class*='attribute_wrapper']")
                                    )
                                )
                            except TimeoutException:
                                logger.debug(
                                    "상품 %s: attribute_wrapper 로드 타임아웃", idx + 1
                                )

                            detail_specs = extract_detail_specs(driver)
                            basic_product["detail_specs"] = detail_specs

                            # 원래 검색 결과 페이지로 복귀
                            driver.get(original_url)
                            time.sleep(1)

                            logger.debug(
                                "상세 정보 수집 완료 (%s개 항목)", len(detail_specs)
                            )
                            continue

                    # 상세 정보 수집용 탭으로 전환
                    driver.switch_to.window(detail_tab_handle)

                    # 상품 상세 페이지로 이동 (쿠키가 자동으로 공유됨)
                    driver.get(product_link)

                    # 페이지 로드 대기 (인증화면 통과 및 콘텐츠 로드용)
                    # 요청 간격을 랜덤하게 조정하여 봇 감지 방지 (속도 개선)
                    wait_time = 2 + (idx % 2)  # 2~3초 사이로 단축 (원래 4~6초)
                    time.sleep(wait_time)

                    # 에러 페이지 확인
                    page_title = driver.title
                    page_source = driver.page_source
                    if (
                        "상품이 존재하지 않습니다" in page_source
                        or "상품이 존재하지 않습니다" in page_title
                    ):
                        logger.debug(
                            "상품 %s: 상품이 존재하지 않음 (삭제/판매 중단)",
                            idx + 1,
                        )
                        basic_product["detail_specs"] = {}
                        # 원래 창으로 복귀
                        try:
                            if original_window in driver.window_handles:
                                driver.switch_to.window(original_window)
                            elif len(driver.window_handles) > 0:
                                driver.switch_to.window(driver.window_handles[0])
                                original_window = driver.window_handles[0]
                        except Exception:
                            pass
                        continue

                    # 스크롤하여 동적 콘텐츠 로드
                    try:
                        driver.execute_script("window.scrollBy(0, 500)")
                        time.sleep(0.5)  # 1초 -> 0.5초로 단축
                    except Exception:
                        pass

                    # attribute_wrapper 요소가 로드될 때까지 대기
                    try:
                        WebDriverWait(driver, 5).until(
                            EC.presence_of_element_located(
                                (
                                    By.CSS_SELECTOR,
                                    "div[class*='attribute_wrapper']",
                                )
                            )
                        )
                    except TimeoutException:
                        logger.debug(
                            "상품 %s: attribute_wrapper 로드 타임아웃", idx + 1
                        )

                    # 상세 정보 추출 (메인 드라이버 사용)
                    detail_specs = extract_detail_specs(driver)
                    basic_product["detail_specs"] = detail_specs

                    # 원래 창으로 복귀 (탭은 닫지 않고 재사용)
                    try:
                        if original_window in driver.window_handles:
                            driver.switch_to.window(original_window)
                        else:
                            # 원래 창이 없으면 첫 번째 창 사용
                            if len(driver.window_handles) > 0:
                                driver.switch_to.window(driver.window_handles[0])
                                original_window = driver.window_handles[0]
                    except Exception as switch_error:
                        logger.debug(f"창 전환 실패: {switch_error}")
                        # 최후의 수단: 원래 URL로 이동
                        try:
                            driver.get(original_url)
                            time.sleep(2)
                        except Exception:
                            pass

                    # 다음 상품 처리 전 짧은 대기 (요청 간격 조정) - 단축
                    time.sleep(0.3)  # 0.5초 -> 0.3초로 단축

                    logger.debug("상세 정보 수집 완료 (%s개 항목)", len(detail_specs))

                except Exception as detail_error:
                    logger.warning(
                        "상품 %s 상세 정보 추출 실패: %s", idx + 1, detail_error
                    )
                    # 에러 발생 시에도 원래 창으로 복귀 시도
                    try:
                        # 원래 창으로 복귀
                        if original_window in driver.window_handles:
                            driver.switch_to.window(original_window)
                        elif len(driver.window_handles) > 0:
                            driver.switch_to.window(driver.window_handles[0])
                            original_window = driver.window_handles[0]
                    except Exception as recovery_error:
                        logger.debug(f"세션 복구 실패: {recovery_error}")
                        # 최후의 수단: 원래 URL로 이동
                        try:
                            driver.get(original_url)
                            time.sleep(1)  # 2초 -> 1초로 단축
                        except Exception:
                            pass
                    basic_product["detail_specs"] = {}

            logger.debug(
                "✅ 2단계 완료: %s개 상품의 상세 정보 수집 완료", len(basic_products)
            )

            # 최종 결과에 추가
            products = basic_products

    except Exception as e:
        logger.error("크롤링 오류: %s", e)
        import traceback

        traceback.print_exc()
    finally:
        if driver:
            try:
                driver.quit()
            except Exception as e:
                logger.debug(f"드라이버 종료 실패: {e}")
                pass

    logger.info("네이버 쇼핑 크롤링 완료: %s개", len(products))
    return products


class NaverCrawler:
    """
    네이버 쇼핑 상품 크롤러 (비동기 인터페이스).
    
    Selenium 기반 크롤링을 비동기로 래핑하여 제공.
    """

    def __init__(self, max_workers: int = 1):
        """
        크롤러 초기화.
        
        Args:
            max_workers: 동시 크롤링 스레드 수 (기본값: 1)
        """
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    async def crawl_products(
        self,
        keyword: str,
        max_products: int = 30,
        headless: bool = True,
    ) -> List[Dict[str, str]]:
        """
        네이버 쇼핑 검색 결과에서 상품을 수집 (비동기).
        
        이 메서드는 ThreadPoolExecutor를 사용하여 동기 함수(_crawl_naver_sync)를
        비동기로 실행합니다. Selenium이 동기 라이브러리이므로 이 패턴을 사용합니다.
        
        Args:
            keyword: 검색어
            max_products: 최대 수집 상품 수
            headless: 브라우저 헤드리스 여부
        
        Returns:
            List[Dict[str, str]]: 수집된 상품 리스트
        """
        # Python 3.7+ 호환: 실행 중인 루프가 있으면 사용, 없으면 새로 생성
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()

        # 동기 함수를 ThreadPoolExecutor를 통해 비동기로 실행
        return await loop.run_in_executor(
            self._executor,
            _crawl_naver_sync,
            keyword,
            max_products,
            headless,
        )

    async def close(self) -> None:
        """리소스 정리."""
        self._executor.shutdown(wait=False)


# 편의를 위한 함수형 인터페이스
async def crawl_naver_products(
    keyword: str,
    *,
    max_products: int = 30,
    headless: bool = True,
) -> List[Dict[str, str]]:
    """
    네이버 쇼핑 검색 결과에서 상품을 수집 (비동기 함수).
    
    이 함수는 LangGraph 노드에서 직접 사용할 수 있는 비동기 인터페이스입니다.
    내부적으로 NaverCrawler 클래스를 사용하여 ThreadPoolExecutor로 동기 Selenium 코드를
    비동기로 실행합니다.
    
    사용 예시:
        result = await crawl_naver_products("패딩", max_products=30)
    
    Args:
        keyword: 검색어
        max_products: 최대 수집 상품 수
        headless: 브라우저 헤드리스 여부
    
    Returns:
        List[Dict[str, str]]: 수집된 상품 리스트
    """
    crawler = NaverCrawler()
    try:
        products = await crawler.crawl_products(
            keyword,
            max_products=max_products,
            headless=headless,
        )
        return products
    finally:
        await crawler.close()


__all__ = [
    "crawl_naver_products",
    "build_search_url",
    "extract_detail_specs",
    "normalize_product_url",
    "normalize_image_url",
    "NAVER_SEARCH_URL",
    "NAVER_BASE_URL",
    "NaverCrawler",
]

