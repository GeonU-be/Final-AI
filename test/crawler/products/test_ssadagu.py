"""
싸다구 크롤러 테스트 모듈.

싸다구 상품 크롤러 Mock 테스트 및 통합 테스트.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from pathlib import Path
import json
from datetime import datetime

from app.services.crawler.products.ssadagu_crawler import (
    build_search_url,
    clean_product_title,
    extract_price_from_detail,
    extract_detail_specs,
    crawl_ssadagu_products,
    SSADAGU_SEARCH_URL,
    SSADAGU_BASE_URL,
)


class TestBuildSearchUrl:
    """build_search_url 헬퍼 함수 테스트."""
    
    def test_build_search_url_encodes_keyword(self):
        """검색 키워드를 URL 인코딩."""
        result = build_search_url("컴퓨터")
        assert "컴퓨터" in result or "%" in result
        assert SSADAGU_SEARCH_URL.split("{")[0] in result
    
    def test_build_search_url_handles_special_characters(self):
        """특수 문자 처리."""
        result = build_search_url("아이폰 15 프로")
        assert "ss_tx=" in result
    
    def test_build_search_url_handles_english(self):
        """영어 키워드 처리."""
        result = build_search_url("laptop")
        assert "ss_tx=" in result


class TestCleanProductTitle:
    """clean_product_title 헬퍼 함수 테스트."""
    
    def test_clean_product_title_removes_quotes(self):
        """큰따옴표 제거."""
        title = '상품명 "추가 정보"'
        result = clean_product_title(title)
        assert "추가 정보" not in result
        assert "상품명" in result
    
    def test_clean_product_title_removes_backslash(self):
        """백슬래시 이후 제거."""
        title = "상품명\\추가정보"
        result = clean_product_title(title)
        assert "추가정보" not in result
        assert "상품명" in result
    
    def test_clean_product_title_removes_after_comma(self):
        """쉼표 이후 제거."""
        title = "상품명, 추가 정보"
        result = clean_product_title(title)
        assert "추가 정보" not in result
        assert "상품명" in result
    
    def test_clean_product_title_removes_keywords(self):
        """특정 키워드 이후 제거."""
        title = "상품명 공장 도매"
        result = clean_product_title(title)
        assert "공장" not in result
        assert "도매" not in result
        assert "상품명" in result
    
    def test_clean_product_title_removes_multiple_keywords(self):
        """여러 키워드 처리."""
        title = "상품명 심천 휴대폰 시장"
        result = clean_product_title(title)
        assert "심천" not in result
        assert "휴대폰" not in result
        assert "시장" not in result
    
    def test_clean_product_title_handles_empty_string(self):
        """빈 문자열 처리."""
        assert clean_product_title("") == ""
    
    def test_clean_product_title_handles_none(self):
        """None 처리."""
        assert clean_product_title(None) == ""


class TestExtractPriceFromDetail:
    """extract_price_from_detail 함수 테스트."""
    
    @pytest.mark.asyncio
    async def test_extract_price_from_detail_finds_price(self):
        """가격 추출 성공."""
        mock_page = AsyncMock()
        mock_price_elem = AsyncMock()
        mock_price_elem.inner_text = AsyncMock(return_value="329,290원")
        
        mock_page.query_selector = AsyncMock(return_value=mock_price_elem)
        
        result = await extract_price_from_detail(mock_page)
        
        assert "329,290원" in result or "329290원" in result
    
    @pytest.mark.asyncio
    async def test_extract_price_from_detail_handles_no_price(self):
        """가격이 없는 경우."""
        mock_page = AsyncMock()
        mock_page.query_selector = AsyncMock(return_value=None)
        
        result = await extract_price_from_detail(mock_page)
        
        assert result == ""
    
    @pytest.mark.asyncio
    async def test_extract_price_from_detail_formats_price(self):
        """가격 포맷팅."""
        mock_page = AsyncMock()
        mock_price_elem = AsyncMock()
        mock_price_elem.inner_text = AsyncMock(return_value="100000")
        
        mock_page.query_selector = AsyncMock(return_value=mock_price_elem)
        
        result = await extract_price_from_detail(mock_page)
        
        # 숫자만 있는 경우도 처리
        assert result != ""


class TestExtractDetailSpecs:
    """extract_detail_specs 함수 테스트."""
    
    @pytest.mark.asyncio
    async def test_extract_detail_specs_finds_specs(self):
        """스펙 추출 성공."""
        mock_page = AsyncMock()
        mock_container = AsyncMock()
        
        # Mock 스펙 아이템들
        mock_item1 = AsyncMock()
        mock_title1 = AsyncMock()
        mock_title1.inner_text = AsyncMock(return_value="모델")
        mock_value1 = AsyncMock()
        mock_value1.inner_text = AsyncMock(return_value="AP156PC01")
        
        mock_item1.query_selector = AsyncMock(side_effect=lambda sel: {
            "div.pro-info-title": mock_title1,
            "div.pro-info-info": mock_value1,
        }.get(sel))
        
        mock_container.query_selector_all = AsyncMock(return_value=[mock_item1])
        mock_page.query_selector = AsyncMock(return_value=mock_container)
        
        result = await extract_detail_specs(mock_page)
        
        assert "모델" in result
        assert result["모델"] == "AP156PC01"
    
    @pytest.mark.asyncio
    async def test_extract_detail_specs_handles_no_container(self):
        """컨테이너가 없는 경우."""
        mock_page = AsyncMock()
        mock_page.query_selector = AsyncMock(return_value=None)
        
        result = await extract_detail_specs(mock_page)
        
        assert result == {}
    
    @pytest.mark.asyncio
    async def test_extract_detail_specs_handles_empty_items(self):
        """스펙 아이템이 없는 경우."""
        mock_page = AsyncMock()
        mock_container = AsyncMock()
        mock_container.query_selector_all = AsyncMock(return_value=[])
        mock_page.query_selector = AsyncMock(return_value=mock_container)
        
        result = await extract_detail_specs(mock_page)
        
        assert result == {}


class TestCrawlSsadaguProducts:
    """crawl_ssadagu_products 비동기 함수 테스트."""
    
    @patch('app.services.crawler.products.ssadagu_crawler.asyncio.sleep')
    @patch('app.services.crawler.products.ssadagu_crawler.async_playwright')
    @pytest.mark.asyncio
    async def test_crawl_ssadagu_products_success(self, mock_playwright, mock_sleep):
        """크롤링 성공."""
        # Mock 설정
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        mock_detail_page = AsyncMock()
        
        # 상품 리스트 Mock
        mock_product_list = AsyncMock()
        mock_item1 = AsyncMock()
        mock_item1.get_attribute = AsyncMock(side_effect=lambda attr: {
            "data-title": "테스트 상품명",
            "data-img-url": "https://example.com/image.jpg",
        }.get(attr, ""))
        
        mock_link_elem = AsyncMock()
        mock_link_elem.get_attribute = AsyncMock(return_value="/shop/view.php?id=123")
        mock_item1.query_selector = AsyncMock(return_value=mock_link_elem)
        
        mock_product_list.query_selector_all = AsyncMock(return_value=[mock_item1])
        
        # page.query_selector는 두 번 호출될 수 있음 (ul.search_product_list, #div_product_list)
        # 첫 번째 호출에서 mock_product_list 반환
        mock_page.query_selector = AsyncMock(side_effect=lambda selector: {
            "ul.search_product_list": mock_product_list,
            "#div_product_list": None,
        }.get(selector, None))
        
        mock_page.goto = AsyncMock()
        mock_page.evaluate = AsyncMock()
        
        # 상세 페이지 Mock
        mock_price_elem = AsyncMock()
        mock_price_elem.inner_text = AsyncMock(return_value="50,000원")
        mock_detail_page.query_selector = AsyncMock(return_value=mock_price_elem)
        mock_detail_page.wait_for_selector = AsyncMock()
        mock_detail_page.close = AsyncMock()
        mock_detail_page.goto = AsyncMock()
        
        # browser.new_page는 두 번 호출될 수 있음 (메인 페이지, 상세 페이지)
        # 첫 번째는 mock_page, 두 번째는 mock_detail_page
        call_count = [0]
        async def new_page_side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_page
            return mock_detail_page
        
        mock_browser.new_page = AsyncMock(side_effect=new_page_side_effect)
        mock_browser.close = AsyncMock()
        
        mock_playwright_instance = MagicMock()
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_playwright.return_value.__aenter__ = AsyncMock(return_value=mock_playwright_instance)
        mock_playwright.return_value.__aexit__ = AsyncMock(return_value=None)
        
        result = await crawl_ssadagu_products("컴퓨터", max_products=1)
        
        assert len(result) == 1
        assert result[0]["title"] == "테스트 상품명"
        assert "image.jpg" in result[0]["thumbnail_url"]
    
    @patch('app.services.crawler.products.ssadagu_crawler.async_playwright')
    @pytest.mark.asyncio
    async def test_crawl_ssadagu_products_handles_no_product_list(self, mock_playwright):
        """상품 리스트를 찾지 못한 경우."""
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        mock_page.query_selector = AsyncMock(return_value=None)
        mock_page.goto = AsyncMock()
        mock_browser.close = AsyncMock()
        
        mock_playwright_instance = MagicMock()
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_playwright.return_value.__aenter__ = AsyncMock(return_value=mock_playwright_instance)
        mock_playwright.return_value.__aexit__ = AsyncMock(return_value=None)
        
        result = await crawl_ssadagu_products("존재하지않는상품명12345", max_products=10)
        
        assert result == []
    
    @patch('app.services.crawler.products.ssadagu_crawler.asyncio.sleep')
    @patch('app.services.crawler.products.ssadagu_crawler.async_playwright')
    @pytest.mark.asyncio
    async def test_crawl_ssadagu_products_respects_max_products(self, mock_playwright, mock_sleep):
        """max_products 파라미터 확인."""
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        mock_detail_page = AsyncMock()
        mock_product_list = AsyncMock()
        
        # 여러 상품 Mock
        mock_items = []
        for i in range(5):
            mock_item = AsyncMock()
            mock_item.get_attribute = AsyncMock(side_effect=lambda attr, idx=i: {
                "data-title": f"상품 {idx+1}",
                "data-img-url": f"https://example.com/image{idx+1}.jpg",
            }.get(attr, ""))
            mock_link_elem = AsyncMock()
            mock_link_elem.get_attribute = AsyncMock(return_value="/shop/view.php?id=123")
            mock_item.query_selector = AsyncMock(return_value=mock_link_elem)
            mock_items.append(mock_item)
        
        mock_product_list.query_selector_all = AsyncMock(return_value=mock_items)
        mock_page.query_selector = AsyncMock(side_effect=lambda selector: {
            "ul.search_product_list": mock_product_list,
            "#div_product_list": None,
        }.get(selector, None))
        mock_page.goto = AsyncMock()
        mock_page.evaluate = AsyncMock()
        
        # 상세 페이지 Mock
        mock_detail_page.query_selector = AsyncMock(return_value=None)
        mock_detail_page.wait_for_selector = AsyncMock()
        mock_detail_page.close = AsyncMock()
        mock_detail_page.goto = AsyncMock()
        
        # browser.new_page는 여러 번 호출될 수 있음
        call_count = [0]
        async def new_page_side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_page
            return mock_detail_page
        
        mock_browser.new_page = AsyncMock(side_effect=new_page_side_effect)
        mock_browser.close = AsyncMock()
        
        mock_playwright_instance = MagicMock()
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_playwright.return_value.__aenter__ = AsyncMock(return_value=mock_playwright_instance)
        mock_playwright.return_value.__aexit__ = AsyncMock(return_value=None)
        
        result = await crawl_ssadagu_products("컴퓨터", max_products=3)
        
        assert len(result) <= 3
    
    @patch('app.services.crawler.products.ssadagu_crawler.async_playwright')
    @pytest.mark.asyncio
    async def test_crawl_ssadagu_products_handles_page_goto_timeout(self, mock_playwright):
        """페이지 로드 타임아웃 처리."""
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        
        # 첫 번째 goto 실패, 두 번째 성공
        call_count = [0]
        async def goto_side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Timeout")
            return None
        
        mock_page.goto = AsyncMock(side_effect=goto_side_effect)
        mock_page.query_selector = AsyncMock(return_value=None)
        mock_browser.close = AsyncMock()
        
        mock_playwright_instance = MagicMock()
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_playwright.return_value.__aenter__ = AsyncMock(return_value=mock_playwright_instance)
        mock_playwright.return_value.__aexit__ = AsyncMock(return_value=None)
        
        result = await crawl_ssadagu_products("컴퓨터", max_products=10)
        
        # 타임아웃 후 빈 결과 반환
        assert isinstance(result, list)


class TestIntegration:
    """통합 테스트 (Mock 사용)."""
    
    @patch('app.services.crawler.products.ssadagu_crawler.asyncio.sleep')
    @patch('app.services.crawler.products.ssadagu_crawler.async_playwright')
    @pytest.mark.asyncio
    async def test_full_workflow(self, mock_playwright, mock_sleep):
        """전체 워크플로우 테스트."""
        mock_browser = AsyncMock()
        mock_page = AsyncMock()
        mock_detail_page = AsyncMock()
        
        mock_product_list = AsyncMock()
        mock_item = AsyncMock()
        mock_item.get_attribute = AsyncMock(side_effect=lambda attr: {
            "data-title": "테스트 상품",
            "data-img-url": "https://example.com/thumb.jpg",
        }.get(attr, ""))
        
        mock_link_elem = AsyncMock()
        mock_link_elem.get_attribute = AsyncMock(return_value="/shop/view.php?id=123")
        mock_item.query_selector = AsyncMock(return_value=mock_link_elem)
        
        mock_product_list.query_selector_all = AsyncMock(return_value=[mock_item])
        
        # page.query_selector는 두 번 호출될 수 있음
        mock_page.query_selector = AsyncMock(side_effect=lambda selector: {
            "ul.search_product_list": mock_product_list,
            "#div_product_list": None,
        }.get(selector, None))
        
        mock_page.goto = AsyncMock()
        mock_page.evaluate = AsyncMock()
        
        mock_price_elem = AsyncMock()
        mock_price_elem.inner_text = AsyncMock(return_value="100,000원")
        mock_detail_page.query_selector = AsyncMock(return_value=mock_price_elem)
        mock_detail_page.wait_for_selector = AsyncMock()
        mock_detail_page.close = AsyncMock()
        mock_detail_page.goto = AsyncMock()
        
        # browser.new_page는 두 번 호출될 수 있음
        call_count = [0]
        async def new_page_side_effect():
            call_count[0] += 1
            if call_count[0] == 1:
                return mock_page
            return mock_detail_page
        
        mock_browser.new_page = AsyncMock(side_effect=new_page_side_effect)
        mock_browser.close = AsyncMock()
        
        mock_playwright_instance = MagicMock()
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_playwright.return_value.__aenter__ = AsyncMock(return_value=mock_playwright_instance)
        mock_playwright.return_value.__aexit__ = AsyncMock(return_value=None)
        
        result = await crawl_ssadagu_products("컴퓨터", max_products=1)
        
        assert len(result) == 1
        product = result[0]
        assert "title" in product
        assert "product_link" in product
        assert "thumbnail_url" in product
        assert "price" in product
        assert "detail_specs" in product


@pytest.mark.integration
@pytest.mark.slow
class TestRealIntegration:
    """
    실제 브라우저를 사용하는 통합 테스트 (느리고 불안정할 수 있음).
    
    이 클래스의 테스트는 Mock을 사용하지 않습니다.
    실제 Playwright 브라우저를 실행하고 실제 ssadagu.kr에 접속합니다.
    
    실행 방법:
    pytest test/crawler/products/test_ssadagu.py::TestRealIntegration::test_real_ssadagu_crawling -v -s
    
    또는 마커 사용:
    pytest test/crawler/products/test_ssadagu.py -m integration -v -s
    """
    
    @pytest.mark.asyncio
    async def test_real_ssadagu_crawling(self):
        """
        실제 싸다구 쇼핑몰에서 상품을 크롤링하는 테스트.
        
        Mock을 사용하지 않고 실제 브라우저를 실행합니다.
        실제 ssadagu.kr 웹사이트에 접속하여 데이터를 수집합니다.
        """
        print("\n" + "="*70)
        print("🔍 실제 싸다구 크롤링 테스트 시작")
        print("="*70)
        
        # 실제 크롤링 실행
        keyword = "컴퓨터"
        max_products = 5  # 테스트용으로 적은 수
        print(f"\n📦 설정:")
        print(f"   - 검색 키워드: {keyword}")
        print(f"   - 최대 수집 개수: {max_products}개")
        print(f"   - 헤드리스 모드: True")
        print(f"\n⏳ 크롤링 시작... (30초~1분 정도 소요될 수 있습니다)\n")
        
        result = await crawl_ssadagu_products(
            keyword,
            max_products=max_products,
            headless=True,
            page_timeout_ms=60_000
        )
        
        # 결과 저장 (test_ssadagu.py와 같은 경로, 고정 파일명)
        test_dir = Path(__file__).parent  # test/crawler/products/
        output_file = test_dir / "ssadagu_test_result.json"
        try:
            output_data = {
                "timestamp": datetime.now().isoformat(),
                "test_settings": {
                    "keyword": keyword,
                    "max_products": max_products,
                    "headless": True,
                },
                "result": {
                    "total_products": len(result),
                    "products": result,
                },
            }
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            print(f"\n💾 결과 저장: {output_file}")
        except Exception as e:
            print(f"\n⚠️ 파일 저장 실패: {e}")
        
        # 결과 출력
        print("\n" + "="*70)
        print(f"✅ 크롤링 완료!")
        print(f"📊 총 {len(result)}개 상품 수집")
        print("="*70)
        print("\n📋 수집된 상품 목록:")
        print("-" * 70)
        
        for idx, product in enumerate(result, 1):
            print(f"\n  {idx}. {product.get('title', 'Unknown')[:50]}...")
            print(f"     가격: {product.get('price', '정보 없음')}")
            print(f"     링크: {product.get('product_link', '정보 없음')[:60]}...")
            detail_specs = product.get('detail_specs', {})
            if detail_specs:
                print(f"     상세 스펙:")
                for spec_key, spec_val in list(detail_specs.items())[:3]:
                    print(f"       - {spec_key}: {spec_val}")
        
        print("\n" + "="*70)
        
        # 최소한 1개 이상의 상품이 수집되어야 함
        assert len(result) > 0, "상품이 수집되지 않았습니다"
        
        # 각 상품에 필수 필드가 있는지 확인
        for product in result:
            assert "title" in product, "상품에 title이 없습니다"
            assert product["title"], "상품 title이 비어있습니다"
            assert "product_link" in product, "상품에 product_link가 없습니다"
            assert "price" in product, "상품에 price 필드가 없습니다"
            assert "detail_specs" in product, "상품에 detail_specs 필드가 없습니다"
            assert isinstance(product["detail_specs"], dict), "detail_specs는 딕셔너리여야 합니다"
