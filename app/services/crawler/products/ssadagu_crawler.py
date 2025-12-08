"""
싸다구 상품 크롤러 (비동기 버전).

Playwright를 사용해 싸다구 쇼핑몰 검색 페이지에서 상품 정보를 수집한다.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Dict, List, Optional
from urllib.parse import quote

from playwright.async_api import async_playwright, Page, Browser

logger = logging.getLogger(__name__)

# 공통 검색 URL 템플릿
SSADAGU_SEARCH_URL = "https://ssadagu.kr/shop/search.php?ss_tx={query}"
SSADAGU_BASE_URL = "https://ssadagu.kr"


def build_search_url(keyword: str) -> str:
    """검색 키워드를 URL에 맞게 인코딩해 반환."""
    return SSADAGU_SEARCH_URL.format(query=quote(keyword))


def clean_product_title(title: str) -> str:
    """
    상품명 정제 (쉼표, 백슬래시, 큰따옴표 이후 불필요한 정보 제거).
    
    Args:
        title: 원본 상품명
    
    Returns:
        str: 정제된 상품명
    """
    if not title:
        return ""
    
    # 큰따옴표로 둘러싸인 부분 제거 (이스케이프된 큰따옴표 포함)
    title = re.sub(r'\\"[^"]*\\"', '', title).strip()
    title = re.sub(r'"[^"]*"', '', title).strip()
    
    # 백슬래시가 있으면 그 뒤 부분 제거
    if "\\" in title:
        title = title.split("\\")[0].strip()
    
    # 쉼표로 분리하여 첫 번째 부분만 사용 (주요 상품명)
    if "," in title:
        title = title.split(",")[0].strip()
    
    # 특정 키워드 이후 제거
    keywords_to_remove = [
        "모든 네트워크 지원",
        "심천 휴대폰 시장",
        "공장 도매",
        "인기 상품",
        "도매",
        "공장"
    ]
    for keyword in keywords_to_remove:
        if keyword in title:
            idx = title.find(keyword)
            title = title[:idx].strip()
            break
    
    return title


async def extract_price_from_detail(detail_page: Page) -> str:
    """
    상세 페이지에서 가격 추출.
    
    Args:
        detail_page: Playwright Page 객체
    
    Returns:
        str: 가격 문자열 (예: "329,290원")
    """
    selectors = [
        "div.item-info div.item-info-base div.flex-container div.flex-container h3.pdt_price span.price.gsItemPriceKWR",
        "div.item-info div.item-info-base h3.pdt_price span.price",
        "div.item-info-base .pdt_price span[class*='price']",
        "span.price.gsItemPriceKWR",
        ".pdt_price span.price"
    ]
    
    for selector in selectors:
        try:
            price_elem = await detail_page.query_selector(selector)
            if price_elem:
                price_text = (await price_elem.inner_text()).strip()
                if not price_text:
                    continue
                
                price_match = re.search(r'([\d,]+)', price_text)
                if price_match:
                    raw_value = price_match.group(1)
                    normalized = raw_value.replace(',', '')
                    if normalized.isdigit():
                        formatted = "{:,}원".format(int(normalized))
                        return formatted
                
                if "원" in price_text:
                    return price_text
        except Exception:
            continue
    
    return ""


async def extract_detail_specs(detail_page: Page) -> Dict[str, str]:
    """
    상세 페이지에서 상품 스펙 추출.
    
    Args:
        detail_page: Playwright Page 객체
    
    Returns:
        Dict[str, str]: 스펙 딕셔너리 (예: {"모델": "AP156PC01", "상표": "아이오파"})
    """
    specs = {}
    try:
        container = await detail_page.query_selector("div.pro-info-boxs")
        if not container:
            container = await detail_page.query_selector("#productAttributes")
        
        if not container:
            return specs
        
        items = await container.query_selector_all("div.pro-info-item")
        for item in items:
            try:
                title_elem = await item.query_selector("div.pro-info-title")
                if not title_elem:
                    title_elem = await item.query_selector("div[class*='pro-info-title']")
                
                value_elem = await item.query_selector("div.pro-info-info")
                if not value_elem:
                    value_elem = await item.query_selector("div[class*='pro-info-info']")
                
                if not title_elem or not value_elem:
                    continue
                
                title = (await title_elem.inner_text()).strip().rstrip(":")
                value = (await value_elem.inner_text()).strip()
                
                if title and value:
                    specs[title] = value
            except Exception:
                continue
    except Exception:
        pass
    
    return specs


async def crawl_ssadagu_products(
    keyword: str,
    *,
    max_products: int = 30,
    headless: bool = True,
    page_timeout_ms: int = 30_000,
) -> List[Dict[str, str]]:
    """
    싸다구 쇼핑몰에서 상품을 크롤링합니다 (비동기).
    
    Args:
        keyword: 검색 키워드
        max_products: 최대 수집할 상품 개수
        headless: 헤드리스 모드 여부
        page_timeout_ms: 페이지 로드 타임아웃 (밀리초)
    
    Returns:
        List[Dict[str, str]]: 수집된 상품 리스트
    """
    products: List[Dict[str, str]] = []
    search_url = build_search_url(keyword)
    
    logger.info("싸다구 크롤링 시작: '%s' (%s)", keyword, search_url)
    
    async with async_playwright() as p:
        browser: Browser = await p.chromium.launch(headless=headless)
        page = await browser.new_page()
        
        try:
            logger.debug("접속 중: %s", search_url)
            try:
                await page.goto(search_url, wait_until="networkidle", timeout=page_timeout_ms)
            except Exception:
                logger.warning("초기 접속 실패, load 이벤트까지 대기 재시도")
                try:
                    await page.goto(search_url, wait_until="load", timeout=page_timeout_ms)
                except Exception as e:
                    logger.error(f"페이지 로드 실패: {e}")
                    await browser.close()
                    return []
            
            await asyncio.sleep(2)
            
            # 스크롤하여 동적 콘텐츠 로드 (더 많은 상품 로드)
            for scroll_idx in range(5):
                await page.evaluate("window.scrollBy(0, window.innerHeight)")
                await asyncio.sleep(0.8)
            
            # 페이지 끝까지 스크롤
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)
            
            # 상품 리스트 찾기
            product_list = await page.query_selector("ul.search_product_list")
            if not product_list:
                product_list = await page.query_selector("#div_product_list")
            
            if not product_list:
                logger.warning("상품 리스트를 찾을 수 없습니다")
                await browser.close()
                return []
            
            # 각 상품 li 요소 찾기
            product_items = await product_list.query_selector_all("li")
            logger.info("발견된 상품 수: %s개", len(product_items))
            
            # 유효한 상품이 max_products개가 될 때까지 더 많은 상품 처리
            processed_count = 0
            for item_elem in product_items:
                if len(products) >= max_products:
                    break
                
                processed_count += 1
                try:
                    # data 속성에서 정보 추출
                    title = await item_elem.get_attribute("data-title") or ""
                    img_url = await item_elem.get_attribute("data-img-url") or ""
                    
                    # 상품명 정제
                    title = clean_product_title(title)
                    
                    # 상품 링크 찾기
                    product_link = ""
                    link_elem = await item_elem.query_selector("a")
                    if link_elem:
                        href = await link_elem.get_attribute("href") or ""
                        if href:
                            if href.startswith("http"):
                                product_link = href
                            else:
                                product_link = f"{SSADAGU_BASE_URL}{href}"
                    
                    # 상품 상세 페이지에서 정확한 가격 및 상세 정보 추출
                    price = ""
                    detail_specs = {}
                    if product_link:
                        detail_page = None
                        try:
                            detail_page = await browser.new_page()
                            await detail_page.goto(
                                product_link,
                                wait_until="domcontentloaded",
                                timeout=page_timeout_ms
                            )
                            # 요청 간 더 긴 대기 시간을 주어 rate limiting 가능성을 낮춤
                            await asyncio.sleep(2.0 + (processed_count % 3))  # 2~4초 사이 대기
                            
                            try:
                                await detail_page.wait_for_selector("div.item-info-base", timeout=5000)
                            except Exception:
                                logger.debug("상세 페이지 로딩 대기 중 타임아웃 (무시)")
                            
                            price = await extract_price_from_detail(detail_page)
                            detail_specs = await extract_detail_specs(detail_page)
                        except Exception as detail_error:
                            logger.warning("상품 %s 상세 정보 추출 실패: %s", processed_count, detail_error)
                        finally:
                            if detail_page:
                                try:
                                    await detail_page.close()
                                except Exception:
                                    pass
                    
                    # 최소한 제목이 있어야 유효한 상품
                    if title:
                        product_data = {
                            "title": title,
                            "price": price,
                            "product_link": product_link,
                            "thumbnail_url": img_url,
                            "detail_specs": detail_specs
                        }
                        products.append(product_data)
                        
                        # 목표 개수에 도달하면 중단
                        if len(products) >= max_products:
                            break
                except Exception as e:
                    logger.warning("상품 정보 추출 오류: %s", e)
                    continue
            
            if len(products) < max_products:
                logger.warning(
                    "유효한 상품이 %s개만 수집되었습니다. (처리한 상품: %s개)",
                    len(products),
                    processed_count
                )
        
        except Exception as e:
            logger.error("크롤링 오류: %s", e)
            import traceback
            traceback.print_exc()
        finally:
            await browser.close()
    
    logger.info("싸다구 크롤링 완료: %s개", len(products))
    return products


__all__ = [
    "crawl_ssadagu_products",
    "build_search_url",
    "clean_product_title",
    "extract_price_from_detail",
    "extract_detail_specs",
    "SSADAGU_SEARCH_URL",
    "SSADAGU_BASE_URL",
]

