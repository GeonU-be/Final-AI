"""
쿠팡 크롤러 테스트 모듈.

쿠팡 상품 크롤러 Mock 테스트.

테스트 구조:
- 단위 테스트 (TestBuildSearchUrl, TestCleanProductTitle, TestExtractPrices, TestExtractProductInfo, TestCrawlCoupangProducts)
  : Mock 사용, 빠른 실행, 외부 의존성 없음
  
- 통합 테스트는 test_coupang_integration.py에 별도로 분리되어 있습니다.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, PropertyMock

from app.services.crawler.products.coupang_crawler import (
    build_search_url,
    clean_product_title,
    extract_prices,
    extract_product_info,
    extract_detail_images,
    crawl_coupang_products,
    CoupangCrawler,
    COUPANG_SEARCH_URL,
    COUPANG_BASE_URL,
)


class TestBuildSearchUrl:
    """build_search_url 헬퍼 함수 테스트."""
    
    def test_build_search_url_encodes_keyword(self):
        """검색 키워드를 URL 인코딩."""
        result = build_search_url("노트북")
        assert "노트북" in result or "%" in result
        assert COUPANG_SEARCH_URL.split("{")[0] in result
    
    def test_build_search_url_handles_special_characters(self):
        """특수 문자 처리."""
        result = build_search_url("아이폰 15 프로")
        assert "q=" in result
    
    def test_build_search_url_handles_english(self):
        """영어 키워드 처리."""
        result = build_search_url("laptop")
        assert "laptop" in result or "q=" in result


class TestCleanProductTitle:
    """clean_product_title 헬퍼 함수 테스트."""
    
    def test_clean_product_title_removes_price(self):
        """가격 정보 제거."""
        title = "노트북\n50,000원\n무료배송"
        result = clean_product_title(title)
        assert "50,000원" not in result
        assert "노트북" in result
    
    def test_clean_product_title_removes_delivery_info(self):
        """배송 정보 제거."""
        title = "아이폰 15\n로켓배송\n내일 도착"
        result = clean_product_title(title)
        assert "로켓배송" not in result
        assert "내일" not in result
        assert "도착" not in result
    
    def test_clean_product_title_removes_review_info(self):
        """리뷰/평점 정보 제거."""
        title = "상품명\n4.5 (1,234)\n리뷰 보기"
        result = clean_product_title(title)
        assert "리뷰" not in result
        assert "4.5" not in result or "(" not in result
    
    def test_clean_product_title_removes_discount_info(self):
        """할인 정보 제거."""
        title = "상품명\n쿠폰할인 20%\n적립금"
        result = clean_product_title(title)
        assert "할인" not in result
        assert "%" not in result
        assert "적립" not in result
    
    def test_clean_product_title_removes_stock_info(self):
        """재고 정보 제거."""
        title = "상품명\n단 3개 남음\n품절 임박"
        result = clean_product_title(title)
        assert "남음" not in result
        assert "품절" not in result
    
    def test_clean_product_title_removes_urgency_keywords(self):
        """긴급 구매 문구 제거."""
        title = "상품명\n빨리 주문하세요\n서둘러"
        result = clean_product_title(title)
        assert "빨리" not in result
        assert "서둘러" not in result
    
    def test_clean_product_title_returns_first_valid_line(self):
        """첫 번째 유효한 라인 반환."""
        title = "정상 상품명\n50,000원\n무료배송"
        result = clean_product_title(title)
        assert result == "정상 상품명"
    
    def test_clean_product_title_handles_empty_string(self):
        """빈 문자열 처리."""
        assert clean_product_title("") == ""
        assert clean_product_title("\n\n") == ""
    
    def test_clean_product_title_handles_only_noise(self):
        """노이즈만 있는 경우 처리."""
        title = "50,000원\n무료배송\n리뷰 100개"
        result = clean_product_title(title)
        # 노이즈만 있으면 첫 번째 라인 반환
        assert result is not None


class TestExtractPrices:
    """extract_prices 함수 테스트."""
    
    def test_extract_prices_finds_original_and_displayed_price(self):
        """원가와 할인가 추출."""
        # Mock WebElement 설정
        mock_item = MagicMock()
        
        # 원가 요소 (del 태그 또는 작은 텍스트)
        mock_original_elem = MagicMock()
        mock_original_elem.get_attribute.return_value = "fw-text-[12px] custom-oos"
        mock_original_elem.tag_name = "del"
        mock_original_elem.text = "100,000원"
        
        # 할인가 요소 (큰 텍스트)
        mock_displayed_elem = MagicMock()
        mock_displayed_elem.get_attribute.return_value = "fw-text-[20px] custom-oos fw-font-bold"
        mock_displayed_elem.tag_name = "span"
        mock_displayed_elem.text = "80,000원"
        
        mock_item.find_elements.return_value = [mock_original_elem, mock_displayed_elem]
        
        original, displayed = extract_prices(mock_item)
        
        assert "100,000원" in original
        assert "80,000원" in displayed
    
    def test_extract_prices_handles_no_prices(self):
        """가격이 없는 경우."""
        mock_item = MagicMock()
        mock_item.find_elements.return_value = []
        
        original, displayed = extract_prices(mock_item)
        
        assert original == ""
        assert displayed == ""
    
    def test_extract_prices_handles_only_displayed_price(self):
        """할인가만 있는 경우."""
        mock_item = MagicMock()
        
        mock_displayed_elem = MagicMock()
        mock_displayed_elem.get_attribute.return_value = "fw-text-[20px] custom-oos"
        mock_displayed_elem.tag_name = "span"
        mock_displayed_elem.text = "50,000원"
        
        mock_item.find_elements.return_value = [mock_displayed_elem]
        
        original, displayed = extract_prices(mock_item)
        
        assert original == ""
        assert "50,000원" in displayed


class TestExtractProductInfo:
    """extract_product_info 함수 테스트."""
    
    @patch('app.services.crawler.products.coupang_crawler.time.sleep')
    def test_extract_product_info_extracts_all_fields(self, mock_sleep):
        """모든 필드 추출."""
        mock_item = MagicMock()
        
        # 제목 요소
        mock_title_elem = MagicMock()
        mock_title_elem.text = "테스트 상품명"
        
        # 링크 요소
        mock_link_elem = MagicMock()
        mock_link_elem.get_attribute.return_value = "https://www.coupang.com/products/12345"
        
        # 이미지 요소
        mock_img_elem = MagicMock()
        mock_img_elem.get_attribute.side_effect = lambda attr: {
            "src": "https://thumbnail.coupangcdn.com/image.jpg",
            "data-src": None,
        }.get(attr, "")
        
        # 가격 Mock
        mock_price_elem = MagicMock()
        mock_price_elem.get_attribute.return_value = "custom-oos"
        mock_price_elem.tag_name = "span"
        mock_price_elem.text = "50,000원"
        
        mock_item.find_element.side_effect = lambda by, selector: {
            ("css selector", "a.ProductUnit_productName__P8nrl"): mock_title_elem,
            ("css selector", "a"): mock_link_elem,
            ("css selector", "img"): mock_img_elem,
        }.get((by, selector), MagicMock())
        
        mock_item.find_elements.return_value = [mock_price_elem]
        
        result = extract_product_info(mock_item, 0)
        
        assert result is not None
        assert result["title"] == "테스트 상품명"
        assert "12345" in result["product_link"]
        assert "image.jpg" in result["thumbnail_url"]
    
    @patch('app.services.crawler.products.coupang_crawler.time.sleep')
    def test_extract_product_info_handles_relative_link(self, mock_sleep):
        """상대 경로 링크 처리."""
        mock_item = MagicMock()
        
        mock_title_elem = MagicMock()
        mock_title_elem.text = "테스트 상품"
        
        mock_link_elem = MagicMock()
        mock_link_elem.get_attribute.return_value = "/products/12345"
        
        mock_img_elem = MagicMock()
        mock_img_elem.get_attribute.return_value = ""
        
        mock_item.find_element.side_effect = lambda by, selector: {
            ("css selector", "a.ProductUnit_productName__P8nrl"): mock_title_elem,
            ("css selector", "a"): mock_link_elem,
            ("css selector", "img"): mock_img_elem,
        }.get((by, selector), MagicMock())
        
        mock_item.find_elements.return_value = []
        
        result = extract_product_info(mock_item, 0)
        
        assert result is not None
        assert result["product_link"].startswith(COUPANG_BASE_URL)
    
    @patch('app.services.crawler.products.coupang_crawler.time.sleep')
    def test_extract_product_info_returns_none_without_title(self, mock_sleep):
        """제목이 없으면 None 반환."""
        mock_item = MagicMock()
        mock_item.find_element.side_effect = Exception("Not found")
        mock_item.find_elements.return_value = []
        
        result = extract_product_info(mock_item, 0)
        
        assert result is None


class TestExtractDetailImages:
    """extract_detail_images 함수 테스트."""
    
    @patch('app.services.crawler.products.coupang_crawler.time.sleep')
    def test_extract_detail_images_finds_images(self, mock_sleep):
        """상세 이미지 추출."""
        mock_driver = MagicMock()
        
        # 이미지 요소들
        mock_img1 = MagicMock()
        mock_img1.get_attribute.side_effect = lambda attr: {
            "src": "https://coupangcdn.com/vendor_inventory/img1.jpg",
            "data-src": None,
        }.get(attr, "")
        
        mock_img2 = MagicMock()
        mock_img2.get_attribute.side_effect = lambda attr: {
            "src": "https://coupangcdn.com/vendor_inventory/img2.jpg",
            "data-src": None,
        }.get(attr, "")
        
        mock_driver.find_elements.return_value = [mock_img1, mock_img2]
        mock_driver.execute_script.return_value = None
        
        result = extract_detail_images(mock_driver, "https://www.coupang.com/products/12345", 0)
        
        assert len(result) == 2
        assert "img1.jpg" in result[0]
        assert "img2.jpg" in result[1]
    
    @patch('app.services.crawler.products.coupang_crawler.time.sleep')
    def test_extract_detail_images_handles_empty_link(self, mock_sleep):
        """빈 링크 처리."""
        mock_driver = MagicMock()
        
        result = extract_detail_images(mock_driver, "", 0)
        
        assert result == []
        mock_driver.get.assert_not_called()
    
    @patch('app.services.crawler.products.coupang_crawler.time.sleep')
    def test_extract_detail_images_filters_non_coupang_urls(self, mock_sleep):
        """쿠팡 URL이 아닌 이미지 필터링."""
        mock_driver = MagicMock()
        
        mock_img = MagicMock()
        mock_img.get_attribute.return_value = "https://external.com/image.jpg"
        
        mock_driver.find_elements.return_value = [mock_img]
        mock_driver.execute_script.return_value = None
        
        result = extract_detail_images(mock_driver, "https://www.coupang.com/products/12345", 0)
        
        assert len(result) == 0


class TestCrawlCoupangProducts:
    """crawl_coupang_products 비동기 함수 테스트."""
    
    @patch('app.services.crawler.products.coupang_crawler._crawl_coupang_sync')
    @pytest.mark.asyncio
    async def test_crawl_coupang_products_calls_sync_function(self, mock_crawl_sync):
        """동기 함수 호출 확인."""
        mock_crawl_sync.return_value = [
            {
                "title": "테스트 상품",
                "original_price": "100,000원",
                "displayed_price": "80,000원",
                "product_link": "https://www.coupang.com/products/12345",
                "thumbnail_url": "https://thumbnail.coupangcdn.com/image.jpg",
                "detail_images": [],
            }
        ]
        
        result = await crawl_coupang_products("노트북", max_products=1)
        
        assert len(result) == 1
        assert result[0]["title"] == "테스트 상품"
        mock_crawl_sync.assert_called_once()
    
    @patch('app.services.crawler.products.coupang_crawler._crawl_coupang_sync')
    @pytest.mark.asyncio
    async def test_crawl_coupang_products_respects_max_products(self, mock_crawl_sync):
        """max_products 파라미터 확인."""
        mock_crawl_sync.return_value = []
        
        await crawl_coupang_products("노트북", max_products=10)
        
        call_args = mock_crawl_sync.call_args
        assert call_args[0][1] == 10  # max_products는 두 번째 위치 인자
    
    @patch('app.services.crawler.products.coupang_crawler._crawl_coupang_sync')
    @pytest.mark.asyncio
    async def test_crawl_coupang_products_handles_empty_result(self, mock_crawl_sync):
        """빈 결과 처리."""
        mock_crawl_sync.return_value = []
        
        result = await crawl_coupang_products("존재하지않는상품명12345", max_products=10)
        
        assert result == []


class TestCoupangCrawler:
    """CoupangCrawler 클래스 테스트."""
    
    @patch('app.services.crawler.products.coupang_crawler._crawl_coupang_sync')
    @pytest.mark.asyncio
    async def test_coupang_crawler_crawl_products(self, mock_crawl_sync):
        """crawl_products 메서드 테스트."""
        mock_crawl_sync.return_value = [
            {"title": "상품1", "product_link": "https://www.coupang.com/products/1"},
            {"title": "상품2", "product_link": "https://www.coupang.com/products/2"},
        ]
        
        crawler = CoupangCrawler()
        try:
            result = await crawler.crawl_products("노트북", max_products=2)
            
            assert len(result) == 2
            assert result[0]["title"] == "상품1"
        finally:
            await crawler.close()
    
    @pytest.mark.asyncio
    async def test_coupang_crawler_close(self):
        """close 메서드 테스트."""
        crawler = CoupangCrawler()
        await crawler.close()  # 예외 없이 실행되어야 함


class TestIntegration:
    """통합 테스트 (Mock 사용)."""
    
    @patch('app.services.crawler.products.coupang_crawler._crawl_coupang_sync')
    @pytest.mark.asyncio
    async def test_full_workflow(self, mock_crawl_sync):
        """전체 워크플로우 테스트."""
        mock_crawl_sync.return_value = [
            {
                "title": "테스트 상품",
                "original_price": "100,000원",
                "displayed_price": "80,000원",
                "product_link": "https://www.coupang.com/products/12345",
                "thumbnail_url": "https://thumbnail.coupangcdn.com/image.jpg",
                "detail_images": [],
            }
        ]
        
        result = await crawl_coupang_products("노트북", max_products=1)
        
        assert len(result) == 1
        product = result[0]
        assert "title" in product
        assert "product_link" in product
        assert "thumbnail_url" in product


