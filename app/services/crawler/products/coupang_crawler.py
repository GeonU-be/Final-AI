"""
Coupang 상품 크롤러 (비동기 버전).

undetected-chromedriver와 Selenium을 사용해 쿠팡 검색 페이지에서 상품 정보를 수집한다.
Selenium은 동기 라이브러리이므로 ThreadPoolExecutor로 감싸서 비동기 처리.
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import quote

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logger = logging.getLogger(__name__)

# 공통 검색 URL 템플릿
COUPANG_SEARCH_URL = "https://www.coupang.com/np/search?q={query}"
COUPANG_BASE_URL = "https://www.coupang.com"


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
        if re.search(r"[\d,]+\s*원", line):
            continue
        if any(
            k in line for k in ["도착", "배송", "무료배송", "로켓배송", "내일", "오늘"]
        ):
            continue
        if (
            re.search(r"[\d.]+\s*\([\d,]+\)", line)
            or "리뷰" in line
            or "평점" in line
        ):
            continue
        if any(k in line for k in ["쿠폰할인", "할인", "%", "적립", "캐시"]):
            continue
        if any(k in line for k in ["AD", "새 상품", "반품", "품절", "와우"]):
            continue
        if (
            re.search(r"단\s*\d+\s*개\s*남음", line)
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
    """상품 카드에서 원가/할인가를 탐색 (Selenium WebElement)."""
    original_price = ""
    displayed_price = ""
    try:
        # custom-oos 클래스를 가진 모든 요소 찾기
        all_custom_oos = item_elem.find_elements(By.CSS_SELECTOR, "[class*='custom-oos']")

        # 1단계: 원가 추출
        for elem in all_custom_oos:
            class_attr = elem.get_attribute("class") or ""
            tag_name = elem.tag_name.lower()
            price_text = elem.text.strip()

            if not price_text or "원" not in price_text:
                continue

            # 가격 숫자 추출
            price_match = re.search(r"([\d,]+)\s*원", price_text) or re.search(
                r"([\d,]+)", price_text.replace(" ", "")
            )
            if not price_match:
                continue

            price_value_raw = price_match.group(1)
            price_value = price_value_raw.replace(",", "")

            if not price_value or not price_value.isdigit():
                continue

            price_value_formatted = price_value_raw + "원"

            # 원가 판별: del 태그이거나 취소선이 있거나 작은 텍스트 크기
            is_original = False
            if tag_name == "del" or "fw-line-through" in class_attr:
                is_original = True
            elif "fw-text-[12px]" in class_attr or "fw-text-[14px]" in class_attr:
                is_original = True

            if is_original and not original_price:
                original_price = price_value_formatted
                break

        # 2단계: 할인가 추출
        for elem in all_custom_oos:
            class_attr = elem.get_attribute("class") or ""
            tag_name = elem.tag_name.lower()
            price_text = elem.text.strip()

            if not price_text or "원" not in price_text:
                continue

            price_match = re.search(r"([\d,]+)\s*원", price_text) or re.search(
                r"([\d,]+)", price_text.replace(" ", "")
            )
            if not price_match:
                continue

            price_value_raw = price_match.group(1)
            price_value = price_value_raw.replace(",", "")

            if not price_value or not price_value.isdigit():
                continue

            price_value_formatted = price_value_raw + "원"

            # 이미 원가로 저장된 가격이면 스킵
            if original_price:
                original_price_num = original_price.replace(",", "").replace("원", "")
                if price_value == original_price_num:
                    continue

            # 원가 조건 체크
            is_original = False
            if tag_name == "del":
                is_original = True
            elif "fw-line-through" in class_attr:
                is_original = True
            elif "fw-text-[12px]" in class_attr or "fw-text-[14px]" in class_attr:
                is_original = True

            # 원가가 아니고, 할인가 조건을 만족하는 경우만
            if not is_original:
                is_discount = False
                if "fw-text-[20px]" in class_attr or "fw-text-[24px]" in class_attr:
                    is_discount = True
                elif "fw-font-bold" in class_attr:
                    is_discount = True

                if is_discount and not displayed_price:
                    displayed_price = price_value_formatted
                    break

        # 할인가를 찾지 못했지만 원가는 있는 경우, 큰 텍스트 크기를 가진 요소 재검색
        if original_price and not displayed_price:
            for elem in all_custom_oos:
                class_attr = elem.get_attribute("class") or ""
                tag_name = elem.tag_name.lower()

                if tag_name == "del" or "fw-line-through" in class_attr:
                    continue

                if (
                    "fw-text-[20px]" in class_attr
                    or "fw-text-[24px]" in class_attr
                    or "fw-font-bold" in class_attr
                ):
                    price_text = elem.text.strip()
                    if price_text and "원" in price_text:
                        price_match = re.search(r"([\d,]+)\s*원", price_text) or re.search(
                            r"([\d,]+)", price_text.replace(" ", "")
                        )
                        if price_match:
                            price_value_raw = price_match.group(1)
                            price_value = price_value_raw.replace(",", "")

                            if price_value and price_value.isdigit():
                                original_price_num = original_price.replace(",", "").replace(
                                    "원", ""
                                )
                                if price_value != original_price_num:
                                    displayed_price = price_value_raw + "원"
                                    break

        # 여전히 둘 다 비어 있으면 custom-oos에서 첫 가격을 displayed_price로 사용
        if not original_price and not displayed_price:
            for elem in all_custom_oos:
                price_text = elem.text.strip()
                if not price_text or "원" not in price_text:
                    continue
                price_match = re.search(r"([\d,]+)\s*원", price_text) or re.search(
                    r"([\d,]+)", price_text.replace(" ", "")
                )
                if price_match:
                    price_value_raw = price_match.group(1)
                    price_value = price_value_raw.replace(",", "")

                    if price_value and price_value.isdigit():
                        displayed_price = price_value_raw + "원"
                        break

    except Exception as e:
        logger.debug("가격 추출 오류: %s", e)

    return original_price, displayed_price


def extract_product_info(item_elem, idx: int) -> Optional[Dict[str, str]]:
    """상품 카드(Selenium WebElement)에서 핵심 정보 추출."""
    try:
        if idx > 0:
            time.sleep(0.5)

        # 상품명 추출
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
                title = title_elem.text.strip()
                if title:
                    break
            except Exception:
                continue

        title = clean_product_title(title)

        # 상품 링크 추출
        product_link = ""
        try:
            link_elem = item_elem.find_element(By.CSS_SELECTOR, "a")
            href = link_elem.get_attribute("href") or ""
            if href:
                if href.startswith("http"):
                    product_link = href
                elif href.startswith("/"):
                    product_link = f"{COUPANG_BASE_URL}{href}"
        except Exception:
            pass

        # 가격 정보 추출
        original_price, displayed_price = extract_prices(item_elem)

        # 썸네일 이미지 URL 추출
        thumbnail_url = ""
        try:
            img_elem = item_elem.find_element(By.CSS_SELECTOR, "img")
            thumbnail_url = img_elem.get_attribute("src") or ""
            if not thumbnail_url:
                thumbnail_url = img_elem.get_attribute("data-src") or ""
        except Exception:
            pass

        # 최소한 제목이 있어야 유효한 상품
        if title:
            return {
                "title": title,
                "original_price": original_price,
                "displayed_price": displayed_price,
                "product_link": product_link,
                "thumbnail_url": thumbnail_url,
            }

    except Exception as e:
        logger.warning("상품 %s 정보 추출 실패: %s", idx + 1, e)

    return None


def extract_detail_images(driver, product_link: str, idx: int) -> List[str]:
    """상세 페이지에서 상품 이미지 URL 수집 (Selenium WebDriver)."""
    detail_images: List[str] = []
    if not product_link:
        return detail_images

    try:
        logger.info("상세 페이지 접속 (%s): %s", idx + 1, product_link)
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
                for img in img_elements:
                    src = img.get_attribute("src") or ""
                    if not src:
                        src = img.get_attribute("data-src") or ""

                    if src and src.startswith("http") and src not in found_urls:
                        if "coupangcdn.com" in src or "coupang.com" in src:
                            found_urls.add(src)
                            detail_images.append(src)
            except Exception:
                continue

        # 방법 2: 이미지가 없으면 더 넓은 범위에서 재시도
        if not detail_images:
            try:
                all_detail_imgs = driver.find_elements(
                    By.CSS_SELECTOR,
                    "div[class*='product-detail'] img, div[class*='vendor'] img",
                )
                for img in all_detail_imgs:
                    src = img.get_attribute("src") or ""
                    if not src:
                        src = img.get_attribute("data-src") or ""

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

    except Exception as e:
        logger.warning("상세 페이지 파싱 실패 (%s): %s", product_link, e)

    return detail_images


def _setup_chrome_environment() -> Optional[str]:
    """
    Chrome 실행을 위한 환경 설정.
    PaddleOCR과의 충돌 방지를 위해 원래 HOME/USERPROFILE 복원.
    
    Returns:
        str: 원래 USERPROFILE/HOME 경로 (없으면 None)
    """
    is_windows = platform.system() == "Windows"

    if is_windows:
        # Windows: USERPROFILE 사용
        original_home = os.environ.get("USERPROFILE", "")
        if not original_home or not os.path.exists(original_home):
            # 기본 경로 시도 (크로스 플랫폼 호환)
            # pathlib을 사용하여 플랫폼 독립적인 경로 생성
            default_home = Path.home()  # 크로스 플랫폼 호환
            if default_home.exists():
                original_home = str(default_home)
    else:
        # Mac/Linux: HOME 사용
        original_home = os.environ.get("HOME", "")

    return original_home if original_home and os.path.exists(original_home) else None


def _crawl_coupang_sync(
    keyword: str,
    max_products: int = 30,
    headless: bool = True,
    fetch_detail_images: bool = False,
    max_pages: int = 2,
) -> List[Dict[str, str]]:
    """
    쿠팡 검색 결과에서 상품을 수집 (동기 버전).
    
    Args:
        keyword: 검색어
        max_products: 최대 수집 상품 수
        headless: 브라우저 헤드리스 여부
        fetch_detail_images: 상세 페이지 이미지 수집 여부
        max_pages: 검색 결과 페이지 탐색 최대 횟수
    
    Returns:
        List[Dict[str, str]]: 수집된 상품 리스트
    """
    products: List[Dict[str, str]] = []
    seen_ids: Set[str] = set()
    seen_titles: Set[str] = set()
    driver = None

    search_url = build_search_url(keyword)
    logger.info("Coupang 크롤링 시작: '%s' (%s)", keyword, search_url)

    # Chrome 환경 설정
    original_home = _setup_chrome_environment()

    def _create_chrome_options():
        """ChromeOptions 객체를 생성하는 헬퍼 함수."""
        options = uc.ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--no-sandbox")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--remote-debugging-port=0")  # 랜덤 포트 사용으로 충돌 방지
        options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        return options
    
    def _kill_chrome_processes():
        """실행 중인 Chrome 프로세스를 종료 (크로스 플랫폼)."""
        try:
            if platform.system() == "Windows":
                # Windows: taskkill 사용
                subprocess.run(
                    ["taskkill", "/F", "/IM", "chrome.exe", "/T"],
                    capture_output=True,
                    timeout=10
                )
                subprocess.run(
                    ["taskkill", "/F", "/IM", "chromedriver.exe", "/T"],
                    capture_output=True,
                    timeout=10
                )
            elif platform.system() == "Darwin":  # macOS
                # macOS: pkill 사용
                subprocess.run(
                    ["pkill", "-f", "Google Chrome"],
                    capture_output=True,
                    timeout=10
                )
                subprocess.run(
                    ["pkill", "-f", "chromedriver"],
                    capture_output=True,
                    timeout=10
                )
            else:  # Linux
                # Linux: pkill 사용
                subprocess.run(
                    ["pkill", "-f", "google-chrome"],
                    capture_output=True,
                    timeout=10
                )
                subprocess.run(
                    ["pkill", "-f", "chromedriver"],
                    capture_output=True,
                    timeout=10
                )
            time.sleep(2)  # 프로세스 종료 대기
        except Exception as e:
            logger.debug(f"Chrome 프로세스 종료 시도 중 오류 (무시 가능): {e}")

    try:
        # Chrome 실행 전 환경 변수 임시 복원
        current_userprofile = os.environ.get("USERPROFILE", "")
        current_home = os.environ.get("HOME", "")

        if original_home:
            if platform.system() == "Windows":
                os.environ["USERPROFILE"] = original_home
            os.environ["HOME"] = original_home

        try:
            # 실행 중인 Chrome 프로세스 정리 (충돌 방지)
            _kill_chrome_processes()
            time.sleep(2)  # 프로세스 종료 대기
            
            # version_main=None은 자동 감지
            # 버전 불일치 문제 해결을 위해 여러 방법 시도
            # 주의: ChromeOptions 객체는 재사용할 수 없으므로 각 시도마다 새로 생성해야 함
            driver = None
            last_error = None
            
            # 방법 1: 자동 감지 (use_subprocess=True)
            try:
                logger.debug("ChromeDriver 자동 감지 시도 (use_subprocess=True)")
                options = _create_chrome_options()
                driver = uc.Chrome(options=options, version_main=None, use_subprocess=True)
                # 연결 확인
                driver.get("data:text/html,<html></html>")
            except Exception as e1:
                last_error = e1
                logger.warning("자동 감지 실패 (use_subprocess=True): %s", str(e1)[:200])
                
                # 방법 2: 자동 감지 (use_subprocess=False)
                try:
                    logger.debug("ChromeDriver 자동 감지 시도 (use_subprocess=False)")
                    # 이전 시도에서 생성된 프로세스 정리
                    if driver:
                        try:
                            driver.quit()
                        except:
                            pass
                    _kill_chrome_processes()
                    time.sleep(2)  # 프로세스 종료 대기
                    
                    options = _create_chrome_options()  # 새로운 객체 생성
                    driver = uc.Chrome(options=options, version_main=None, use_subprocess=False)
                    # 연결 확인
                    driver.get("data:text/html,<html></html>")
                except Exception as e2:
                    last_error = e2
                    logger.warning("자동 감지 실패 (use_subprocess=False): %s", str(e2)[:200])
                    
                    # 방법 3: Chrome 142 버전 명시적 지정
                    try:
                        logger.debug("ChromeDriver 142 버전 명시적 지정 시도")
                        # 이전 시도에서 생성된 프로세스 정리
                        if driver:
                            try:
                                driver.quit()
                            except:
                                pass
                        _kill_chrome_processes()
                        time.sleep(2)  # 프로세스 종료 대기
                        
                        options = _create_chrome_options()  # 새로운 객체 생성
                        driver = uc.Chrome(options=options, version_main=142, use_subprocess=False)
                        # 연결 확인
                        driver.get("data:text/html,<html></html>")
                    except Exception as e3:
                        last_error = e3
                        logger.error("모든 ChromeDriver 초기화 방법 실패")
                        logger.error("마지막 에러: %s", str(e3)[:500])
                        # 크로스 플랫폼 호환 에러 메시지
                        cache_instructions = ""
                        if platform.system() == "Windows":
                            cache_path = os.path.join(
                                os.environ.get("USERPROFILE", ""),
                                "AppData", "Roaming", "undetected_chromedriver"
                            )
                            cache_instructions = (
                                f"   Windows PowerShell: Remove-Item -Recurse -Force \"$env:USERPROFILE\\AppData\\Roaming\\undetected_chromedriver\"\n"
                                f"   Windows CMD: rmdir /s /q \"%USERPROFILE%\\AppData\\Roaming\\undetected_chromedriver\"\n"
                            )
                        elif platform.system() == "Darwin":  # macOS
                            cache_path = os.path.expanduser("~/Library/Application Support/undetected_chromedriver")
                            cache_instructions = (
                                f"   macOS/Linux: rm -rf \"{cache_path}\"\n"
                            )
                        else:  # Linux
                            cache_path = os.path.expanduser("~/.local/share/undetected_chromedriver")
                            cache_instructions = (
                                f"   Linux: rm -rf \"{cache_path}\"\n"
                            )
                        
                        raise Exception(
                            f"ChromeDriver 초기화 실패. Chrome 버전과 ChromeDriver 버전이 맞지 않습니다.\n"
                            f"해결 방법:\n"
                            f"1. Chrome을 최신 버전으로 업데이트\n"
                            f"2. 또는 undetected_chromedriver 캐시 삭제 후 재시도:\n"
                            f"{cache_instructions}"
                            f"마지막 에러: {str(e3)[:200]}"
                        ) from e3
            
            if driver is None:
                raise Exception("ChromeDriver 초기화 실패: driver가 None입니다")
        finally:
            # 환경 변수 복원
            if current_userprofile:
                os.environ["USERPROFILE"] = current_userprofile
            if current_home:
                os.environ["HOME"] = current_home

        logger.debug("쿠팡 메인 진입으로 세션 초기화")
        driver.get(COUPANG_BASE_URL)
        time.sleep(2)

        if not headless:
            time.sleep(10)

        page_num = 1
        while len(products) < max_products and page_num <= max_pages:
            if page_num == 1:
                page_url = search_url
            else:
                separator = "&" if "?" in search_url else "?"
                page_url = f"{search_url}{separator}page={page_num}"

            logger.info("검색 페이지 이동 (%s/%s): %s", page_num, max_pages, page_url)
            driver.get(page_url)

            # 페이지 로드 대기
            if not headless:
                time.sleep(10)
            else:
                time.sleep(8)

            # 페이지 로딩 상태 확인
            try:
                WebDriverWait(driver, 10).until(
                    lambda d: d.execute_script("return document.readyState") == "complete"
                )
            except Exception:
                logger.debug("페이지 로딩 완료 대기 중 타임아웃")

            # 추가 대기 (동적 콘텐츠 로드를 위해)
            time.sleep(3)

            # 스크롤하여 동적 콘텐츠 로드
            for scroll_idx in range(5):
                driver.execute_script("window.scrollBy(0, window.innerHeight * 0.5)")
                time.sleep(2)
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(3)
            driver.execute_script("window.scrollTo(0, 0)")
            time.sleep(2)

            # 상품 리스트 찾기
            product_selectors = [
                "li[class*='ProductUnit_productUnit']",
                "li.ProductUnit_productUnit__Qd6sv",
                "ul#product-list li",
                "#productList li",
                "li[data-id]",
            ]

            product_items = []
            for selector in product_selectors:
                try:
                    items = driver.find_elements(By.CSS_SELECTOR, selector)
                    if items and len(items) > 0:
                        product_items = items
                        logger.debug("발견된 상품 수: %s개 (셀렉터: %s)", len(items), selector)
                        break
                except Exception:
                    continue

            if not product_items:
                logger.warning("기본 셀렉터로 찾지 못함. 넓은 범위로 재검색 중...")
                try:
                    all_lis = driver.find_elements(By.TAG_NAME, "li")
                    for li in all_lis:
                        try:
                            data_id = li.get_attribute("data-id")
                            class_name = li.get_attribute("class") or ""
                            if (
                                data_id
                                or "ProductUnit" in class_name
                                or "product" in class_name.lower()
                            ):
                                product_items.append(li)
                        except Exception:
                            continue
                    if product_items:
                        logger.debug("넓은 범위 검색으로 %s개 요소 발견", len(product_items))
                except Exception as e:
                    logger.warning("넓은 범위 검색 중 오류: %s", e)

            if not product_items:
                logger.warning("상품 리스트를 찾을 수 없습니다 (page=%s)", page_num)
                page_num += 1
                continue

            for idx, item_elem in enumerate(product_items):
                if len(products) >= max_products:
                    break

                product_data = extract_product_info(item_elem, idx)
                if not product_data:
                    continue

                product_link = product_data.get("product_link", "")
                product_id = None
                if product_link:
                    match = re.search(r"/products/(\d+)", product_link)
                    if match:
                        product_id = match.group(1)

                is_duplicate = False
                if product_id and product_id in seen_ids:
                    is_duplicate = True
                elif product_data.get("title", "") in seen_titles:
                    is_duplicate = True

                if not is_duplicate:
                    product_data["detail_images"] = []
                    products.append(product_data)
                    if product_id:
                        seen_ids.add(product_id)
                    if product_data.get("title"):
                        seen_titles.add(product_data["title"])
                else:
                    logger.debug(
                        "중복 상품 스킵: %s...", product_data.get("title", "")[:50]
                    )

            logger.info("페이지 %s 처리 완료 (누적 %s개)", page_num, len(products))
            page_num += 1

        # 상세 이미지 추출 (옵션이 활성화된 경우)
        if fetch_detail_images and products:
            logger.info("상세 이미지 추출 시작 (%s개)", len(products))
            for idx, product in enumerate(products):
                product_link = product.get("product_link", "")
                if product_link:
                    detail_images = extract_detail_images(driver, product_link, idx)
                    product["detail_images"] = detail_images
                    time.sleep(2)

    except Exception as e:
        logger.error("크롤링 오류: %s", e)
        import traceback

        traceback.print_exc()
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    logger.info("Coupang 크롤링 완료: %s개", len(products))
    return products


class CoupangCrawler:
    """
    쿠팡 상품 크롤러 (비동기 인터페이스).
    
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
        fetch_detail_images: bool = False,
        max_pages: int = 2,
    ) -> List[Dict[str, str]]:
        """
        쿠팡 검색 결과에서 상품을 수집 (비동기).
        
        Args:
            keyword: 검색어
            max_products: 최대 수집 상품 수
            headless: 브라우저 헤드리스 여부
            fetch_detail_images: 상세 페이지 이미지 수집 여부
            max_pages: 검색 결과 페이지 탐색 최대 횟수
        
        Returns:
            List[Dict[str, str]]: 수집된 상품 리스트
        """
        # Python 3.7+ 호환: 실행 중인 루프가 있으면 사용, 없으면 새로 생성
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.get_event_loop()

        return await loop.run_in_executor(
            self._executor,
            _crawl_coupang_sync,
            keyword,
            max_products,
            headless,
            fetch_detail_images,
            max_pages,
        )

    async def close(self) -> None:
        """리소스 정리."""
        self._executor.shutdown(wait=False)


# 편의를 위한 함수형 인터페이스
async def crawl_coupang_products(
    keyword: str,
    *,
    max_products: int = 30,
    headless: bool = True,
    fetch_detail_images: bool = False,
    max_pages: int = 2,
    use_ocr: bool = True,
    max_ocr_images: Optional[int] = 5,
) -> List[Dict[str, str]]:
    """
    쿠팡 검색 결과에서 상품을 수집 (비동기).
    
    Args:
        keyword: 검색어
        max_products: 최대 수집 상품 수
        headless: 브라우저 헤드리스 여부
        fetch_detail_images: 상세 페이지 이미지 수집 여부
        max_pages: 검색 결과 페이지 탐색 최대 횟수
        use_ocr: OCR을 사용하여 상세 이미지에서 텍스트 추출 여부
        max_ocr_images: OCR 처리할 최대 이미지 수 (None이면 전체)
    
    Returns:
        List[Dict[str, str]]: 수집된 상품 리스트 (ocr_text 필드 포함 가능)
    """
    crawler = CoupangCrawler()
    try:
        products = await crawler.crawl_products(
            keyword,
            max_products=max_products,
            headless=headless,
            fetch_detail_images=fetch_detail_images,
            max_pages=max_pages,
        )
        
        # OCR 처리 (옵션이 활성화되고 상세 이미지가 있는 경우)
        if use_ocr and products:
            from app.services.crawler.ocr.paddle_ocr import PaddleOCRService
            from app.services.crawler.ocr.text_extractor import clean_ocr_text
            
            logger.info("OCR 텍스트 추출 시작 (%s개 상품)", len(products))
            print(f"\n🔍 OCR 처리 시작: {len(products)}개 상품")
            
            ocr_service = PaddleOCRService(lang="korean")
            
            try:
                # OCR 엔진 초기화
                print("  OCR 엔진 초기화 중...")
                initialized = await ocr_service.initialize()
                if not initialized:
                    error_msg = "OCR 엔진 초기화 실패 (PaddleOCR 모델이 설치되지 않았거나 초기화에 실패했습니다)"
                    logger.warning(error_msg)
                    print(f"  ❌ {error_msg}")
                    print("  💡 해결 방법: pip install paddlepaddle paddleocr")
                    for product in products:
                        product["ocr_text"] = ""
                        product["ocr_text_raw"] = ""
                    return products
                
                print("  ✅ OCR 엔진 초기화 완료")
                
                # 각 상품의 상세 이미지에서 텍스트 추출
                for idx, product in enumerate(products, 1):
                    detail_images = product.get("detail_images", [])
                    title = product.get("title", "")[:40]
                    
                    logger.debug("OCR 처리 중 (%s/%s): %s...", idx, len(products), title)
                    print(f"  [{idx}/{len(products)}] OCR 처리 중: {title}...")
                    
                    if not detail_images:
                        product["ocr_text"] = ""
                        product["ocr_text_raw"] = ""
                        logger.debug("  상세 이미지 없음")
                        print(f"    ⚠️ 상세 이미지 없음")
                        continue
                    
                    print(f"    📷 상세 이미지 {len(detail_images)}개 발견, OCR 처리 중...")
                    
                    # OCR 실행
                    try:
                        ocr_result = await ocr_service.extract_texts_from_urls(
                            detail_images,
                            max_images=max_ocr_images
                        )
                        
                        # OCR 결과 디버깅 정보
                        combined_text = ocr_result.get("combined", "")
                        texts_list = ocr_result.get("texts", [])
                        processed_count = ocr_result.get("count", 0)
                        
                        logger.debug("  OCR 원본 결과: combined=%s, texts=%s, count=%d", 
                                    combined_text[:100] if combined_text else "(빈 문자열)", 
                                    len(texts_list), 
                                    processed_count)
                        
                        # 텍스트 정제
                        cleaned_text = clean_ocr_text(combined_text)
                        product["ocr_text"] = cleaned_text
                        
                        # 원본 텍스트도 저장 (디버깅용)
                        product["ocr_text_raw"] = combined_text
                        
                        if cleaned_text:
                            preview = cleaned_text[:100] + "..." if len(cleaned_text) > 100 else cleaned_text
                            logger.debug("  정제된 텍스트: %s", preview)
                            print(f"    ✅ OCR 텍스트 추출 성공: {preview}")
                        else:
                            if combined_text:
                                logger.warning("  원본 텍스트는 있지만 정제 후 빈 문자열: %s", combined_text[:200])
                                print(f"    ⚠️ 원본 텍스트는 있지만 정제 후 제거됨: {combined_text[:100]}...")
                            else:
                                logger.debug("  추출된 텍스트 없음 (이미지에 텍스트가 없거나 OCR 실패)")
                                print(f"    ❌ OCR 텍스트 추출 실패 (이미지에 텍스트가 없거나 인식 실패)")
                    except Exception as e:
                        error_msg = f"OCR 처리 실패: {e}"
                        logger.warning("OCR 처리 실패 (%s): %s", title, e)
                        print(f"    ❌ {error_msg}")
                        product["ocr_text"] = ""
                        product["ocr_text_raw"] = ""
                
                logger.info("OCR 텍스트 추출 완료")
                print(f"\n✅ OCR 처리 완료: {len(products)}개 상품 처리")
            finally:
                await ocr_service.close()
        
        return products
    finally:
        await crawler.close()


__all__ = [
    "crawl_coupang_products",
    "build_search_url",
    "clean_product_title",
    "COUPANG_SEARCH_URL",
    "COUPANG_BASE_URL",
]
