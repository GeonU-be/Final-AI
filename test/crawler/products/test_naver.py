"""
네이버 쇼핑 크롤러 테스트 모듈.

네이버 쇼핑 상품 크롤러 Mock 테스트.

테스트 구조:
- 단위 테스트 (TestBuildSearchUrl, TestNormalizeProductUrl, TestNormalizeImageUrl, TestExtractDetailSpecs, TestCrawlNaverProducts)
  : Mock 사용, 빠른 실행, 외부 의존성 없음
  
- 통합 테스트는 test_naver_integration.py에 별도로 분리되어 있습니다.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch

from app.services.crawler.products.naver_crawler import (
    build_search_url,
    normalize_product_url,
    normalize_image_url,
    extract_detail_specs,
    crawl_naver_products,
    NaverCrawler,
    NAVER_SEARCH_URL,
    NAVER_BASE_URL,
)


class TestBuildSearchUrl:
    """build_search_url 헬퍼 함수 테스트."""
    
    def test_build_search_url_encodes_keyword(self):
        """검색 키워드를 URL 인코딩."""
        result = build_search_url("패딩")
        assert "패딩" in result or "%" in result
        assert NAVER_SEARCH_URL.split("{")[0] in result
    
    def test_build_search_url_handles_special_characters(self):
        """특수 문자 처리."""
        result = build_search_url("아이폰 15 프로")
        assert "query=" in result
    
    def test_build_search_url_handles_english(self):
        """영어 키워드 처리."""
        result = build_search_url("laptop")
        assert "laptop" in result or "query=" in result


class TestNormalizeProductUrl:
    """normalize_product_url 헬퍼 함수 테스트."""
    
    def test_normalize_product_url_handles_full_url(self):
        """전체 URL 처리."""
        url = "https://shopping.naver.com/products/12345"
        result = normalize_product_url(url)
        assert result == url
    
    def test_normalize_product_url_handles_relative_url(self):
        """상대 경로 URL 처리."""
        url = "/products/12345"
        result = normalize_product_url(url)
        assert result.startswith("https://shopping.naver.com")
    
    def test_normalize_product_url_handles_protocol_relative_url(self):
        """프로토콜 상대 URL 처리."""
        url = "//shopping.naver.com/products/12345"
        result = normalize_product_url(url)
        assert result.startswith("https:")
    
    def test_normalize_product_url_filters_bad_domains(self):
        """불량 도메인 필터링."""
        url = "https://help.pay.naver.com/something"
        result = normalize_product_url(url)
        assert result == ""
    
    def test_normalize_product_url_handles_javascript_url(self):
        """JavaScript URL 처리."""
        url = "javascript:void(0)"
        result = normalize_product_url(url)
        assert result == ""
    
    def test_normalize_product_url_handles_empty_string(self):
        """빈 문자열 처리."""
        assert normalize_product_url("") == ""


class TestNormalizeImageUrl:
    """normalize_image_url 헬퍼 함수 테스트."""
    
    def test_normalize_image_url_handles_full_url(self):
        """전체 URL 처리."""
        url = "https://shopping-phinf.pstatic.net/image.jpg"
        result = normalize_image_url(url)
        assert result == url
    
    def test_normalize_image_url_handles_relative_url(self):
        """상대 경로 URL 처리."""
        url = "/image.jpg"
        result = normalize_image_url(url)
        assert result.startswith("https://shopping-phinf.pstatic.net")
    
    def test_normalize_image_url_handles_protocol_relative_url(self):
        """프로토콜 상대 URL 처리."""
        url = "//shopping-phinf.pstatic.net/image.jpg"
        result = normalize_image_url(url)
        assert result.startswith("https:")
    
    def test_normalize_image_url_filters_data_url(self):
        """Data URL 필터링."""
        url = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        result = normalize_image_url(url)
        assert result == ""
    
    def test_normalize_image_url_handles_empty_string(self):
        """빈 문자열 처리."""
        assert normalize_image_url("") == ""


class TestExtractDetailSpecs:
    """extract_detail_specs 함수 테스트."""
    
    def test_extract_detail_specs_finds_specs(self):
        """상세 스펙 추출."""
        mock_driver = MagicMock()
        
        # Mock attribute_wrapper
        mock_attribute_wrapper = MagicMock()
        
        # Mock rows
        mock_row1 = MagicMock()
        mock_th1 = MagicMock()
        mock_th1.text = "상품번호"
        mock_td1 = MagicMock()
        mock_td1.text = "12345"
        
        mock_row1.find_element.side_effect = lambda by, selector: {
            ("css selector", "th"): mock_th1,
            ("css selector", "td"): mock_td1,
        }.get((by, selector))
        
        mock_row2 = MagicMock()
        mock_th2 = MagicMock()
        mock_th2.text = "제조사"
        mock_td2 = MagicMock()
        mock_td2.text = "테스트 제조사"
        
        mock_row2.find_element.side_effect = lambda by, selector: {
            ("css selector", "th"): mock_th2,
            ("css selector", "td"): mock_td2,
        }.get((by, selector))
        
        mock_attribute_wrapper.find_elements.return_value = [mock_row1, mock_row2]
        
        # Mock driver.find_element
        mock_driver.find_element.return_value = mock_attribute_wrapper
        mock_driver.title = "상품 상세"
        mock_driver.page_source = "정상 페이지"
        
        result = extract_detail_specs(mock_driver)
        
        assert "상품번호" in result
        assert result["상품번호"] == "12345"
        assert "제조사" in result
        assert result["제조사"] == "테스트 제조사"
    
    def test_extract_detail_specs_handles_error_page(self):
        """에러 페이지 처리."""
        mock_driver = MagicMock()
        mock_driver.title = "상품이 존재하지 않습니다"
        mock_driver.page_source = "상품이 존재하지 않습니다"
        
        result = extract_detail_specs(mock_driver)
        
        assert result == {}
    
    def test_extract_detail_specs_handles_no_attribute_wrapper(self):
        """attribute_wrapper가 없는 경우."""
        mock_driver = MagicMock()
        mock_driver.find_element.side_effect = Exception("Not found")
        mock_driver.title = "상품 상세"
        mock_driver.page_source = "정상 페이지"
        
        result = extract_detail_specs(mock_driver)
        
        assert result == {}
    
    def test_extract_detail_specs_handles_empty_specs(self):
        """빈 스펙 처리."""
        mock_driver = MagicMock()
        mock_attribute_wrapper = MagicMock()
        mock_attribute_wrapper.find_elements.return_value = []
        
        mock_driver.find_element.return_value = mock_attribute_wrapper
        mock_driver.title = "상품 상세"
        mock_driver.page_source = "정상 페이지"
        
        result = extract_detail_specs(mock_driver)
        
        assert result == {}


class TestCrawlNaverProducts:
    """crawl_naver_products 비동기 함수 테스트."""
    
    @patch('app.services.crawler.products.naver_crawler._crawl_naver_sync')
    @pytest.mark.asyncio
    async def test_crawl_naver_products_calls_sync_function(self, mock_crawl_sync):
        """동기 함수 호출 확인."""
        mock_crawl_sync.return_value = [
            {
                "title": "테스트 상품",
                "original_price": "100,000원",
                "displayed_price": "80,000원",
                "product_link": "https://shopping.naver.com/products/12345",
                "thumbnail_url": "https://shopping-phinf.pstatic.net/image.jpg",
                "detail_specs": {},
            }
        ]
        
        result = await crawl_naver_products("패딩", max_products=1)
        
        assert len(result) == 1
        assert result[0]["title"] == "테스트 상품"
        mock_crawl_sync.assert_called_once()
    
    @patch('app.services.crawler.products.naver_crawler._crawl_naver_sync')
    @pytest.mark.asyncio
    async def test_crawl_naver_products_respects_max_products(self, mock_crawl_sync):
        """max_products 파라미터 확인."""
        mock_crawl_sync.return_value = []
        
        await crawl_naver_products("패딩", max_products=10)
        
        call_args = mock_crawl_sync.call_args
        assert call_args[0][1] == 10  # max_products는 두 번째 위치 인자
    
    @patch('app.services.crawler.products.naver_crawler._crawl_naver_sync')
    @pytest.mark.asyncio
    async def test_crawl_naver_products_handles_empty_result(self, mock_crawl_sync):
        """빈 결과 처리."""
        mock_crawl_sync.return_value = []
        
        result = await crawl_naver_products("존재하지않는상품명12345", max_products=10)
        
        assert result == []


class TestNaverCrawler:
    """NaverCrawler 클래스 테스트."""
    
    @patch('app.services.crawler.products.naver_crawler._crawl_naver_sync')
    @pytest.mark.asyncio
    async def test_naver_crawler_crawl_products(self, mock_crawl_sync):
        """crawl_products 메서드 테스트."""
        mock_crawl_sync.return_value = [
            {"title": "상품1", "product_link": "https://shopping.naver.com/products/1"},
            {"title": "상품2", "product_link": "https://shopping.naver.com/products/2"},
        ]
        
        crawler = NaverCrawler()
        try:
            result = await crawler.crawl_products("패딩", max_products=2)
            
            assert len(result) == 2
            assert result[0]["title"] == "상품1"
        finally:
            await crawler.close()
    
    @pytest.mark.asyncio
    async def test_naver_crawler_close(self):
        """close 메서드 테스트."""
        crawler = NaverCrawler()
        await crawler.close()  # 예외 없이 실행되어야 함


class TestIntegration:
    """통합 테스트 (Mock 사용)."""
    
    @patch('app.services.crawler.products.naver_crawler._crawl_naver_sync')
    @pytest.mark.asyncio
    async def test_full_workflow(self, mock_crawl_sync):
        """전체 워크플로우 테스트."""
        mock_crawl_sync.return_value = [
            {
                "title": "테스트 상품",
                "original_price": "100,000원",
                "displayed_price": "80,000원",
                "product_link": "https://shopping.naver.com/products/12345",
                "thumbnail_url": "https://shopping-phinf.pstatic.net/image.jpg",
                "detail_specs": {
                    "상품번호": "12345",
                    "제조사": "테스트 제조사",
                },
            }
        ]
        
        result = await crawl_naver_products("패딩", max_products=1)
        
        assert len(result) == 1
        product = result[0]
        assert "title" in product
        assert "product_link" in product
        assert "thumbnail_url" in product
        assert "detail_specs" in product
        assert product["detail_specs"]["상품번호"] == "12345"

