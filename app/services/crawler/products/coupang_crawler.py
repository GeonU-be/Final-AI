"""
Coupang 상품 크롤러 (Vision 의존성 제거 버전).

기본적으로 검색 페이지에서 제목/가격/링크/썸네일을 수집하고,
옵션에 따라 상세 페이지 이미지 URL도 추출한다.
"""

from __future__ import annotations

import logging
import re
import time
from typing import List, Optional, Set, Tuple
from urllib.parse import quote

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logger = logging.getLogger(__name__)

# 공통 검색 URL 템플릿
COUPANG_SEARCH_URL = "https://www.coupang.com/np/search?q={query}"


def build_search_url(keyword: str) -> str:
    """검색 키워드를 URL에 맞게 인코딩해 반환."""
    return COUPANG_SEARCH_URL.format(query=quote(keyword))


def clean_product_title(title: str) -> str:
    """노이즈(배송/할인/재고 문구 등)를 걷어낸 상품명 반환."""
    if not title:
        return ""
    lines = title.split("\n")
    cleaned_lines: List[str] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if not re.search(r"[가-힣a-zA-Z]", line):
            continue
        if re.search(r"[\\d,]+\\s*원", line):
            continue
        if any(
            k in line for k in ["도착", "배송", "무료배송", "로켓배송", "내일", "오늘"]
        ):
            continue
        if (
            re.search(r"[\\d.]+\\s*\\([\\d,]+\\)", line)
            or "리뷰" in line
            or "평점" in line
        ):
            continue
        if any(k in line for k in ["쿠폰할인", "할인", "%", "적립", "캐시"]):
            continue
        if any(k in line for k in ["AD", "새 상품", "반품", "품절", "와우"]):
            continue
        if (
            re.search(r"단\\s*\\d+\\s*개\\s*남음", line)
            or "품절 임박" in line
            or "재고" in line
        ):
            continue
        urgency_keywords = [
            "빨리 주문",
            "서둘러",
            "지금 주문",
            "지금 구매",
            "놓치지 마",
            "마감",
            "한정 수량",
        ]
        if any(k in line for k in urgency_keywords):
            continue
        cleaned_lines.append(line)
    if cleaned_lines:
        return cleaned_lines[0]
    for line in lines:
        candidate = line.strip()
        if candidate and re.search(r"[가-힣a-zA-Z]", candidate):
            return candidate
    return lines[0].strip() if lines else ""


def extract_prices(item_elem) -> Tuple[str, str]:
    """상품 카드에서 원가/할인가를 탐색."""
    original_price = ""
    displayed_price = ""
    try:
        all_custom_oos = item_elem.find_elements(
            By.CSS_SELECTOR, "[class*='custom-oos']"
        )
        for elem in all_custom_oos:
            class_attr = elem.get_attribute("class") or ""
            tag_name = (elem.tag_name or "").lower()
            price_text = (elem.text or "").strip()
            if not price_text or "원" not in price_text:
                continue
            price_match = re.search(r"([\\d,]+)\\s*원", price_text) or re.search(
                r"([\\d,]+)", price_text.replace(" ", "")
            )
            if not price_match:
                continue
            raw = price_match.group(1)
            numeric = raw.replace(",", "")
            if not numeric.isdigit():
                continue
            price_fmt = raw + "원"
            is_original = tag_name == "del" or "fw-line-through" in class_attr
            is_original = (
                is_original
                or "fw-text-[12px]" in class_attr
                or "fw-text-[14px]" in class_attr
            )
            if is_original and not original_price:
                original_price = price_fmt
                break
        for elem in all_custom_oos:
            class_attr = elem.get_attribute("class") or ""
            tag_name = (elem.tag_name or "").lower()
            price_text = (elem.text or "").strip()
            if not price_text or "원" not in price_text:
                continue
            price_match = re.search(r"([\\d,]+)\\s*원", price_text) or re.search(
                r"([\\d,]+)", price_text.replace(" ", "")
            )
            if not price_match:
                continue
            raw = price_match.group(1)
            numeric = raw.replace(",", "")
            if not numeric.isdigit():
                continue
            price_fmt = raw + "원"
            if original_price:
                original_num = original_price.replace(",", "").replace("원", "")
                if numeric == original_num:
                    continue
            is_original = tag_name == "del" or "fw-line-through" in class_attr
            is_original = (
                is_original
                or "fw-text-[12px]" in class_attr
                or "fw-text-[14px]" in class_attr
            )
            if is_original:
                continue
            is_discount = (
                "fw-text-[20px]" in class_attr or "fw-text-[24px]" in class_attr
            )
            is_discount = is_discount or "fw-font-bold" in class_attr
            if is_discount and not displayed_price:
                displayed_price = price_fmt
                break
        if original_price and not displayed_price:
            for elem in all_custom_oos:
                class_attr = elem.get_attribute("class") or ""
                tag_name = (elem.tag_name or "").lower()
                if tag_name == "del" or "fw-line-through" in class_attr:
                    continue
                if (
                    "fw-text-[20px]" in class_attr
                    or "fw-text-[24px]" in class_attr
                    or "fw-font-bold" in class_attr
                ):
                    price_text = (elem.text or "").strip()
                    if price_text and "원" in price_text:
                        price_match = re.search(
                            r"([\\d,]+)\\s*원", price_text
                        ) or re.search(r"([\\d,]+)", price_text.replace(" ", ""))
                        if price_match:
                            raw = price_match.group(1)
                            numeric = raw.replace(",", "")
                            if numeric.isdigit():
                                original_num = original_price.replace(",", "").replace(
                                    "원", ""
                                )
                                if numeric != original_num:
                                    displayed_price = raw + "원"
                                    break
        if not original_price and not displayed_price:
            for elem in all_custom_oos:
                price_text = (elem.text or "").strip()
                if not price_text or "원" not in price_text:
                    continue
                price_match = re.search(r"([\\d,]+)\\s*원", price_text) or re.search(
                    r"([\\d,]+)", price_text.replace(" ", "")
                )
                if price_match:
                    raw = price_match.group(1)
                    numeric = raw.replace(",", "")
                    if numeric.isdigit():
                        displayed_price = raw + "원"
                        break
    except Exception:
        pass
    return original_price, displayed_price


def extract_product_info(item_elem, idx: int) -> Optional[dict]:
    """상품 카드(WebElement)에서 핵심 정보 추출."""
    try:
        if idx > 0:
            time.sleep(0.5)
        title = ""
        title_selectors = [
            "a.ProductUnit_productName__P8nrl",
            "div.ProductUnit_productInfo__1l0il a",
            "div.ProductUnit_productInfo__1l0il",
            ".name",
            "[class*='name']",
        ]
        for sel in title_selectors:
            try:
                title_elem = item_elem.find_element(By.CSS_SELECTOR, sel)
                title = (title_elem.text or "").strip()
                if title:
                    break
            except Exception:
                continue
        title = clean_product_title(title)
        product_link = ""
        try:
            link_elem = item_elem.find_element(By.CSS_SELECTOR, "a")
            href = link_elem.get_attribute("href") or ""
            if href.startswith("http"):
                product_link = href
            elif href.startswith("/"):
                product_link = f"https://www.coupang.com{href}"
        except Exception:
            pass
        original_price, displayed_price = extract_prices(item_elem)
        thumbnail_url = ""
        try:
            img_elem = item_elem.find_element(By.CSS_SELECTOR, "img")
            thumbnail_url = img_elem.get_attribute("src") or ""
            if not thumbnail_url:
                thumbnail_url = img_elem.get_attribute("data-src") or ""
        except Exception:
            pass
        if title:
            return {
                "title": title,
                "original_price": original_price,
                "displayed_price": displayed_price,
                "product_link": product_link,
                "thumbnail_url": thumbnail_url,
            }
    except Exception as exc:
        logger.warning("상품 %s 정보 추출 실패: %s", idx + 1, exc)
    return None


def extract_detail_images(driver, product_link: str, idx: int) -> List[str]:
    """상세 페이지에서 상품 이미지 URL 수집."""
    detail_images: List[str] = []
    if not product_link:
        return detail_images
    try:
        logger.info("상세 페이지 접속 (%s/%s): %s", idx + 1, "?", product_link)
        driver.get(product_link)
        time.sleep(3)
        try:
            driver.execute_script("window.scrollBy(0, window.innerHeight * 2)")
            time.sleep(2)
        except Exception:
            pass
        selectors_to_try = [
            "div.product-detail-content-inside div.vendor-item div.type-HTML div.subType-TEXT p[style*='text-align:center'] img",
            "div.product-detail-content-inside div.vendor-item div.type-TEXT div.subType-TEXT p[style*='text-align:center'] img",
            "div.product-detail-content-inside div.vendor-item div[class*='type-HTML'] div.subType-TEXT p[style*='text-align:center'] img",
            "div.product-detail-content-inside div.vendor-item div[class*='type-TEXT'] div.subType-TEXT p[style*='text-align:center'] img",
            "div.product-detail-content-inside div.vendor-item div.type-HTML div.subType-TEXT p img",
            "div.product-detail-content-inside div.vendor-item div.type-TEXT div.subType-TEXT p img",
            "div.product-detail-content-inside div.vendor-item div[class*='type-HTML'] div.subType-TEXT p img",
            "div.product-detail-content-inside div.vendor-item div[class*='type-TEXT'] div.subType-TEXT p img",
            "div.product-detail-content-inside div.vendor-item div[class*='type-'] p img",
            "div.product-detail-content-inside div.vendor-item p img",
            "div.product-detail-content-inside p img",
            "div[class*='product-detail-content'] p[style*='text-align'] img",
            "div[class*='product-detail-content'] p img",
            "div[class*='vendor-item'] p img",
            "div[class*='subType-TEXT'] p img",
            "div.product-detail-content img",
            "div[class*='product-detail'] img",
        ]
        found_urls: Set[str] = set()
        for selector in selectors_to_try:
            try:
                img_elements = driver.find_elements(By.CSS_SELECTOR, selector)
            except Exception:
                continue
            for img in img_elements:
                src = img.get_attribute("src") or img.get_attribute("data-src") or ""
                if src and src.startswith("http") and src not in found_urls:
                    if "coupangcdn.com" in src or "coupang.com" in src:
                        found_urls.add(src)
                        detail_images.append(src)
        if not detail_images:
            try:
                all_detail_imgs = driver.find_elements(
                    By.CSS_SELECTOR,
                    "div[class*='product-detail'] img, div[class*='vendor'] img",
                )
                for img in all_detail_imgs:
                    src = (
                        img.get_attribute("src") or img.get_attribute("data-src") or ""
                    )
                    if src and src.startswith("http") and src not in found_urls:
                        if "coupangcdn.com" in src or "coupang.com" in src:
                            if "/vendor_inventory/" in src or "/image/" in src:
                                found_urls.add(src)
                                detail_images.append(src)
            except Exception:
                pass
        if detail_images:
            logger.info("상세 이미지 %s개 발견", len(detail_images))
        else:
            logger.warning("상세 이미지를 찾지 못함: %s", product_link)
    except Exception as exc:
        logger.warning("상세 페이지 파싱 실패 (%s): %s", product_link, exc)
    return detail_images


def _ensure_page_ready(driver, timeout: int = 10) -> None:
    """DOMContentLoaded 이후까지 대기."""
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
    except Exception:
        logger.debug("페이지 readyState 대기 타임아웃")


def crawl_coupang_products(
    keyword: str,
    *,
    max_products: int = 30,
    headless: bool = True,
    fetch_detail_images: bool = False,
    max_pages: int = 2,
) -> List[dict]:
    """
    쿠팡 검색 결과에서 상품을 수집한다.

    Args:
        keyword: 검색어.
        max_products: 최대 수집 상품 수.
        headless: 브라우저 헤드리스 여부.
        fetch_detail_images: 상세 페이지 이미지 수집 여부.
        max_pages: 검색 결과 페이지 탐색 최대 횟수.
    """
    products: List[dict] = []
    seen_ids: Set[str] = set()
    seen_titles: Set[str] = set()
    driver = None

    search_url = build_search_url(keyword)
    logger.info("Coupang 크롤링 시작: '%s' (%s)", keyword, search_url)

    try:
        options = uc.ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        driver = uc.Chrome(options=options, version_main=None)

        logger.debug("쿠팡 메인 진입으로 세션 초기화")
        driver.get("https://www.coupang.com/")
        time.sleep(2)

        page_num = 1
        while len(products) < max_products and page_num <= max_pages:
            page_url = search_url if page_num == 1 else f"{search_url}&page={page_num}"
            logger.info("검색 페이지 이동 (%s/%s): %s", page_num, max_pages, page_url)
            driver.get(page_url)
            _ensure_page_ready(driver)
            time.sleep(3)

            for _ in range(5):
                driver.execute_script("window.scrollBy(0, window.innerHeight * 0.5)")
                time.sleep(1)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(2)
            driver.execute_script("window.scrollTo(0, 0)")
            time.sleep(1)

            selectors = [
                "li[class*='ProductUnit_productUnit']",
                "li.ProductUnit_productUnit__Qd6sv",
                "ul#product-list li",
                "#productList li",
                "li[data-id]",
            ]
            product_items = []
            for selector in selectors:
                try:
                    items = driver.find_elements(By.CSS_SELECTOR, selector)
                    if items:
                        product_items = items
                        break
                except Exception:
                    continue

            if not product_items:
                logger.warning("상품 리스트를 찾지 못했습니다 (page=%s)", page_num)
                page_num += 1
                continue

            for idx, item in enumerate(product_items):
                if len(products) >= max_products:
                    break
                product = extract_product_info(item, idx)
                if not product:
                    continue
                link = product.get("product_link", "")
                product_id = None
                if link:
                    match = re.search(r"/products/(\\d+)", link)
                    if match:
                        product_id = match.group(1)
                if (product_id and product_id in seen_ids) or product.get(
                    "title"
                ) in seen_titles:
                    continue
                product["detail_images"] = []
                products.append(product)
                if product_id:
                    seen_ids.add(product_id)
                if product.get("title"):
                    seen_titles.add(product["title"])
            logger.info("페이지 %s 처리 완료 (누적 %s개)", page_num, len(products))
            page_num += 1

        if fetch_detail_images and products:
            logger.info("상세 이미지 추출 시작 (%s개)", len(products))
            for idx, product in enumerate(products):
                link = product.get("product_link")
                if not link:
                    continue
                images = extract_detail_images(driver, link, idx)
                product["detail_images"] = images
                time.sleep(1)
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    logger.info("Coupang 크롤링 완료: %s개", len(products))
    return products
