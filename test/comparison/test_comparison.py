"""
상품 비교 모듈 통합 테스트.

키워드 추출, 유사도 계산, 상품 매칭 기능을 테스트.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import imagehash
from PIL import Image
from io import BytesIO
import json
from pathlib import Path
from datetime import datetime

from app.services.comparison.keywords import KeywordExtractor
from app.services.comparison.similarity import SimilarityCalculator
from app.services.comparison.matcher import ProductMatcher


# ============================================================================
# KeywordExtractor 테스트
# ============================================================================

class TestKeywordExtractor:
    """KeywordExtractor 클래스 테스트."""
    
    def test_extract_capacity_patterns(self):
        """용량 패턴 추출."""
        text = "노트북 16GB RAM 512GB SSD 1TB HDD"
        keywords = KeywordExtractor.extract(text)
        
        assert "16GB" in keywords or "16" in keywords
        assert "512GB" in keywords or "512" in keywords
        assert "1TB" in keywords or "1" in keywords
    
    def test_extract_size_patterns(self):
        """크기 패턴 추출."""
        text = "15.6인치 노트북 1920x1080 해상도"
        keywords = KeywordExtractor.extract(text)
        
        assert any("15.6" in k or "인치" in k for k in keywords)
        assert any("1920" in k or "1080" in k for k in keywords)
    
    def test_extract_model_patterns(self):
        """모델 번호 패턴 추출."""
        text = "iPhone14 GalaxyS23 i5-12400 RTX3060"
        keywords = KeywordExtractor.extract(text)
        
        assert any("IPHONE14" in k or "14" in k for k in keywords)
        assert any("I5" in k or "12400" in k for k in keywords)
        assert any("RTX" in k or "3060" in k for k in keywords)
    
    def test_extract_color_keywords(self):
        """색상 키워드 추출."""
        text = "블랙 노트북 화이트 실버"
        keywords = KeywordExtractor.extract(text)
        
        assert "블랙" in keywords or "BLACK" in keywords
        assert "화이트" in keywords or "WHITE" in keywords
        assert "실버" in keywords or "SILVER" in keywords
    
    def test_extract_material_keywords(self):
        """재질 키워드 추출."""
        text = "면 소재 폴리에스터 나일론"
        keywords = KeywordExtractor.extract(text)
        
        assert "면" in keywords or "COTTON" in keywords
        assert "폴리에스터" in keywords or "POLYESTER" in keywords
    
    def test_extract_origin_keywords(self):
        """원산지 키워드 추출."""
        text = "한국산 제품 중국 제조국"
        keywords = KeywordExtractor.extract(text)
        
        assert "한국" in keywords or "KOREA" in keywords
        assert "중국" in keywords or "CHINA" in keywords
    
    def test_extract_computer_patterns(self):
        """컴퓨터 전용 패턴 추출."""
        text = "i5-12400 RTX 3060 GTX 1660 13세대"
        keywords = KeywordExtractor.extract(text)
        
        assert any("I5" in k or "12400" in k for k in keywords)
        assert any("RTX" in k or "3060" in k for k in keywords)
        assert any("13" in k or "세대" in k for k in keywords)
    
    def test_extract_quantity_patterns(self):
        """수량 패턴 추출."""
        text = "1개 2EA 3SET 10팩"
        keywords = KeywordExtractor.extract(text)
        
        assert any("1" in k or "개" in k for k in keywords)
        assert any("2" in k or "EA" in k for k in keywords)
    
    def test_extract_certification_patterns(self):
        """인증 패턴 추출."""
        text = "KC인증 CE인증 ISO9001"
        keywords = KeywordExtractor.extract(text)
        
        assert any("KC" in k or "인증" in k for k in keywords)
        assert any("ISO" in k or "9001" in k for k in keywords)
    
    def test_extract_handles_empty_string(self):
        """빈 문자열 처리."""
        keywords = KeywordExtractor.extract("")
        assert keywords == set()
    
    def test_extract_handles_none(self):
        """None 처리."""
        keywords = KeywordExtractor.extract(None)
        assert keywords == set()
    
    def test_normalize_keyword(self):
        """키워드 정규화."""
        assert KeywordExtractor.normalize_keyword("iPhone 14") == "iphone14"
        assert KeywordExtractor.normalize_keyword("RTX-3060") == "rtx3060"
        assert KeywordExtractor.normalize_keyword("i5_12400") == "i512400"
        assert KeywordExtractor.normalize_keyword("") == ""
    
    def test_normalize_keyword_removes_spaces(self):
        """공백 제거."""
        result = KeywordExtractor.normalize_keyword("  iPhone  14  ")
        assert " " not in result
    
    def test_extract_complex_text(self):
        """복잡한 텍스트에서 키워드 추출."""
        text = "삼성 갤럭시 노트북 15.6인치 i7-13700H 16GB RAM 512GB SSD RTX 4060 블랙"
        keywords = KeywordExtractor.extract(text)
        
        # 여러 키워드가 추출되어야 함
        assert len(keywords) > 0
        assert any("I7" in k or "13700" in k for k in keywords)
        assert any("16GB" in k or "16" in k for k in keywords)
        assert any("512GB" in k or "512" in k for k in keywords)


# ============================================================================
# SimilarityCalculator 테스트
# ============================================================================

class TestSimilarityCalculator:
    """SimilarityCalculator 클래스 테스트."""
    
    def test_init_default_weights(self):
        """기본 가중치로 초기화."""
        calc = SimilarityCalculator()
        
        assert calc.image_weight == 0.35
        assert calc.price_weight == 0.15
        assert calc.title_weight == 0.25
        assert calc.ocr_specs_weight == 0.25
        assert calc.total_weight == 1.0
    
    def test_init_custom_weights(self):
        """커스텀 가중치로 초기화."""
        calc = SimilarityCalculator(
            image_weight=0.5,
            price_weight=0.2,
            title_weight=0.2,
            ocr_specs_weight=0.1
        )
        
        assert calc.image_weight == 0.5
        # 부동소수점 정밀도 문제로 근사값 비교
        assert abs(calc.total_weight - 1.0) < 0.0001
    
    @pytest.mark.asyncio
    @patch('app.services.comparison.similarity.aiohttp.ClientSession')
    async def test_get_image_hash_success(self, mock_session_class):
        """이미지 해시 계산 성공."""
        # Mock 이미지 데이터
        img = Image.new('RGB', (100, 100), color='red')
        img_bytes = BytesIO()
        img.save(img_bytes, format='PNG')
        img_data = img_bytes.getvalue()
        
        # Mock HTTP 응답
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=img_data)
        
        # session.get()이 context manager를 반환
        mock_get_context = MagicMock()
        mock_get_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get_context.__aexit__ = AsyncMock(return_value=None)
        
        # session.get() Mock
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_get_context)
        
        # ClientSession() 호출 결과가 context manager
        mock_session_instance = MagicMock()
        mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_instance.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session_instance
        
        calc = SimilarityCalculator()
        hash_value = await calc.get_image_hash("https://example.com/image.jpg")
        
        assert hash_value is not None
        assert isinstance(hash_value, imagehash.ImageHash)
    
    @pytest.mark.asyncio
    @patch('app.services.comparison.similarity.aiohttp.ClientSession')
    async def test_get_image_hash_caching(self, mock_session_class):
        """이미지 해시 캐싱."""
        img = Image.new('RGB', (100, 100), color='red')
        img_bytes = BytesIO()
        img.save(img_bytes, format='PNG')
        img_data = img_bytes.getvalue()
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=img_data)
        
        # session.get()이 context manager를 반환
        mock_get_context = MagicMock()
        mock_get_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get_context.__aexit__ = AsyncMock(return_value=None)
        
        # session.get() Mock
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_get_context)
        
        # ClientSession() 호출 결과가 context manager
        mock_session_instance = MagicMock()
        mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_instance.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session_instance
        
        calc = SimilarityCalculator()
        url = "https://example.com/image.jpg"
        
        # 첫 번째 호출
        hash1 = await calc.get_image_hash(url)
        
        # 두 번째 호출 (캐시에서 가져옴)
        hash2 = await calc.get_image_hash(url)
        
        assert hash1 == hash2
        # HTTP 요청은 한 번만 발생해야 함 (캐시 때문에)
        # 첫 번째 호출에서만 session.get()이 호출됨
        assert mock_session.get.call_count == 1
    
    @pytest.mark.asyncio
    @patch('app.services.comparison.similarity.aiohttp.ClientSession')
    async def test_calculate_image_similarity_identical(self, mock_session_class):
        """동일한 이미지 유사도 계산."""
        # 같은 이미지 데이터
        img = Image.new('RGB', (100, 100), color='red')
        img_bytes = BytesIO()
        img.save(img_bytes, format='PNG')
        img_data = img_bytes.getvalue()
        
        # 두 URL 모두 같은 이미지 데이터 반환
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=img_data)
        
        # session.get()이 context manager를 반환
        mock_get_context = MagicMock()
        mock_get_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get_context.__aexit__ = AsyncMock(return_value=None)
        
        # session.get() Mock
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_get_context)
        
        # ClientSession() 호출 결과가 context manager
        mock_session_instance = MagicMock()
        mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_instance.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session_instance
        
        calc = SimilarityCalculator()
        similarity = await calc.calculate_image_similarity(
            "https://example.com/img1.jpg",
            "https://example.com/img1.jpg"  # 같은 URL로 변경하여 캐시 활용
        )
        
        # 같은 이미지이므로 유사도가 높아야 함
        assert similarity > 0.9
    
    @pytest.mark.asyncio
    async def test_calculate_image_similarity_empty_urls(self):
        """빈 URL 처리."""
        calc = SimilarityCalculator()
        similarity = await calc.calculate_image_similarity("", "")
        
        assert similarity == 0.0
    
    def test_calculate_title_similarity_identical(self):
        """동일한 상품명 유사도."""
        calc = SimilarityCalculator()
        similarity = calc.calculate_title_similarity(
            "삼성 노트북 15.6인치",
            "삼성 노트북 15.6인치"
        )
        
        assert similarity > 0.9
    
    def test_calculate_title_similarity_similar(self):
        """유사한 상품명."""
        calc = SimilarityCalculator()
        similarity = calc.calculate_title_similarity(
            "삼성 갤럭시 노트북 15.6인치",
            "삼성 노트북 15.6인치"
        )
        
        assert similarity > 0.5
    
    def test_calculate_title_similarity_different(self):
        """다른 상품명."""
        calc = SimilarityCalculator()
        similarity = calc.calculate_title_similarity(
            "삼성 노트북",
            "애플 아이폰"
        )
        
        assert similarity < 0.5
    
    def test_calculate_title_similarity_empty(self):
        """빈 상품명 처리."""
        calc = SimilarityCalculator()
        similarity = calc.calculate_title_similarity("", "노트북")
        
        assert similarity == 0.0
    
    def test_calculate_price_similarity_identical(self):
        """동일한 가격."""
        calc = SimilarityCalculator()
        similarity = calc.calculate_price_similarity("100,000원", "100000원")
        
        assert similarity == 1.0
    
    def test_calculate_price_similarity_similar(self):
        """유사한 가격."""
        calc = SimilarityCalculator()
        similarity = calc.calculate_price_similarity("100,000원", "105,000원")
        
        assert similarity > 0.9
    
    def test_calculate_price_similarity_different(self):
        """다른 가격."""
        calc = SimilarityCalculator()
        similarity = calc.calculate_price_similarity("100,000원", "200,000원")
        
        assert similarity < 0.6
    
    def test_calculate_price_similarity_empty(self):
        """빈 가격 처리."""
        calc = SimilarityCalculator()
        similarity = calc.calculate_price_similarity(None, "100,000원")
        
        assert similarity == 0.0
    
    def test_parse_price(self):
        """가격 파싱."""
        calc = SimilarityCalculator()
        
        assert calc._parse_price("100,000원") == 100000.0
        assert calc._parse_price("100000") == 100000.0
        assert calc._parse_price(100000) == 100000.0
        assert calc._parse_price(None) is None
        assert calc._parse_price("") is None
    
    def test_calculate_ocr_specs_similarity_identical(self):
        """동일한 OCR/스펙."""
        calc = SimilarityCalculator()
        
        ocr_text = "CPU: i7-13700H RAM: 16GB SSD: 512GB"
        detail_specs = {
            "프로세서": "i7-13700H",
            "메모리 용량": "16GB",
            "저장 유형": "SSD 512GB"
        }
        
        similarity = calc.calculate_ocr_specs_similarity(ocr_text, detail_specs)
        
        assert similarity > 0.5
    
    def test_calculate_ocr_specs_similarity_empty(self):
        """빈 OCR/스펙 처리."""
        calc = SimilarityCalculator()
        similarity = calc.calculate_ocr_specs_similarity("", {})
        
        assert similarity == 0.0
    
    def test_convert_specs_to_text(self):
        """스펙을 텍스트로 변환."""
        calc = SimilarityCalculator()
        
        detail_specs = {
            "모델": "노트북",
            "CPU 유형": "i7-13700H",
            "메모리 용량": "16GB",
            "기타": "선택 사항"  # 노이즈 값
        }
        
        text = calc._convert_specs_to_text(detail_specs)
        
        assert "모델" in text
        assert "CPU" in text or "i7" in text
        assert "16GB" in text or "16" in text
        assert "선택 사항" not in text  # 노이즈 제거
    
    def test_extract_keyword_contexts(self):
        """키워드 주변 텍스트 추출."""
        calc = SimilarityCalculator()
        
        text = "이것은 테스트 텍스트입니다. CPU i7-13700H 프로세서가 있습니다."
        keywords = {"i7-13700H", "CPU"}
        
        contexts = calc._extract_keyword_contexts(text, keywords, context_size=10)
        
        assert len(contexts) > 0
        assert any("i7" in ctx or "CPU" in ctx for ctx in contexts)
    
    @pytest.mark.asyncio
    @patch('app.services.comparison.similarity.SimilarityCalculator.calculate_image_similarity')
    async def test_calculate_combined_similarity(self, mock_image_sim):
        """종합 유사도 계산."""
        mock_image_sim.return_value = 0.8
        
        calc = SimilarityCalculator()
        
        product1 = {
            "title": "삼성 노트북 15.6인치",
            "displayed_price": "1,000,000원",
            "thumbnail_url": "https://example.com/img1.jpg",
            "ocr_text": "CPU: i7 RAM: 16GB"
        }
        
        product2 = {
            "title": "삼성 노트북 15.6인치",
            "price": "1,050,000원",
            "thumbnail_url": "https://example.com/img2.jpg",
            "detail_specs": {
                "프로세서": "i7",
                "메모리 용량": "16GB"
            }
        }
        
        result = await calc.calculate_combined_similarity(product1, product2)
        
        assert "combined_similarity" in result
        assert "image_similarity" in result
        assert "price_similarity" in result
        assert "title_similarity" in result
        assert "ocr_specs_similarity" in result
        
        assert 0.0 <= result["combined_similarity"] <= 1.0
        assert result["image_similarity"] == 0.8
    
    def test_clear_cache(self):
        """캐시 초기화."""
        calc = SimilarityCalculator()
        calc._image_hash_cache["test_url"] = MagicMock()
        
        calc.clear_cache()
        
        assert len(calc._image_hash_cache) == 0


# ============================================================================
# ProductMatcher 테스트
# ============================================================================

class TestProductMatcher:
    """ProductMatcher 클래스 테스트."""
    
    def test_init_default_values(self):
        """기본값으로 초기화."""
        matcher = ProductMatcher()
        
        assert matcher.threshold == ProductMatcher.DEFAULT_THRESHOLD
        assert matcher.max_workers == 10
        assert isinstance(matcher.calculator, SimilarityCalculator)
    
    def test_init_custom_values(self):
        """커스텀 값으로 초기화."""
        calc = SimilarityCalculator()
        matcher = ProductMatcher(
            threshold=0.5,
            max_workers=5,
            similarity_calculator=calc
        )
        
        assert matcher.threshold == 0.5
        assert matcher.max_workers == 5
        assert matcher.calculator == calc
    
    @pytest.mark.asyncio
    @patch('app.services.comparison.matcher.SimilarityCalculator.calculate_combined_similarity')
    async def test_find_similar_products_above_threshold(self, mock_calc):
        """임계값 이상 상품 찾기."""
        # Mock 유사도 계산 결과
        mock_calc.return_value = {
            "combined_similarity": 0.6,
            "image_similarity": 0.7,
            "price_similarity": 0.8,
            "title_similarity": 0.5,
            "ocr_specs_similarity": 0.4
        }
        
        products_coupang = [
            {
                "title": "노트북",
                "displayed_price": "1,000,000원",
                "thumbnail_url": "https://example.com/img1.jpg",
                "product_link": "https://coupang.com/product1"
            }
        ]
        
        products_ssadagu = [
            {
                "title": "노트북",
                "price": "1,050,000원",
                "thumbnail_url": "https://example.com/img2.jpg",
                "product_link": "https://ssadagu.com/product1"
            }
        ]
        
        matcher = ProductMatcher(threshold=0.5)
        results = await matcher.find_similar_products(products_coupang, products_ssadagu)
        
        assert len(results) == 1
        assert results[0]["similarity"]["combined_similarity"] == 0.6
        assert "coupang_product" in results[0]
        assert "ssadagu_product" in results[0]
    
    @pytest.mark.asyncio
    @patch('app.services.comparison.matcher.SimilarityCalculator.calculate_combined_similarity')
    async def test_find_similar_products_below_threshold(self, mock_calc):
        """임계값 미만 상품 필터링."""
        mock_calc.return_value = {
            "combined_similarity": 0.3,  # 임계값 미만
            "image_similarity": 0.2,
            "price_similarity": 0.3,
            "title_similarity": 0.4,
            "ocr_specs_similarity": 0.2
        }
        
        products_coupang = [
            {
                "title": "노트북",
                "displayed_price": "1,000,000원",
                "thumbnail_url": "https://example.com/img1.jpg",
                "product_link": "https://coupang.com/product1"
            }
        ]
        
        products_ssadagu = [
            {
                "title": "스마트폰",
                "price": "500,000원",
                "thumbnail_url": "https://example.com/img2.jpg",
                "product_link": "https://ssadagu.com/product1"
            }
        ]
        
        matcher = ProductMatcher(threshold=ProductMatcher.DEFAULT_THRESHOLD)
        results = await matcher.find_similar_products(products_coupang, products_ssadagu)
        
        assert len(results) == 0
    
    @pytest.mark.asyncio
    @patch('app.services.comparison.matcher.SimilarityCalculator.calculate_combined_similarity')
    async def test_find_similar_products_no_thumbnails(self, mock_calc):
        """썸네일이 없는 상품 제외."""
        products_coupang = [
            {
                "title": "노트북",
                "displayed_price": "1,000,000원",
                "thumbnail_url": "",  # 썸네일 없음
                "product_link": "https://coupang.com/product1"
            }
        ]
        
        products_ssadagu = [
            {
                "title": "노트북",
                "price": "1,050,000원",
                "thumbnail_url": "https://example.com/img2.jpg",
                "product_link": "https://ssadagu.com/product1"
            }
        ]
        
        matcher = ProductMatcher()
        results = await matcher.find_similar_products(products_coupang, products_ssadagu)
        
        # 썸네일이 없으면 비교하지 않음
        assert mock_calc.call_count == 0
        assert len(results) == 0
    
    @pytest.mark.asyncio
    @patch('app.services.comparison.matcher.SimilarityCalculator.calculate_combined_similarity')
    async def test_find_similar_products_empty_lists(self, mock_calc):
        """빈 리스트 처리."""
        matcher = ProductMatcher()
        results = await matcher.find_similar_products([], [])
        
        assert len(results) == 0
        assert mock_calc.call_count == 0
    
    @pytest.mark.asyncio
    @patch('app.services.comparison.matcher.SimilarityCalculator.calculate_combined_similarity')
    async def test_find_similar_products_progress_callback(self, mock_calc):
        """진행 상황 콜백 테스트."""
        mock_calc.return_value = {
            "combined_similarity": 0.6,
            "image_similarity": 0.7,
            "price_similarity": 0.8,
            "title_similarity": 0.5,
            "ocr_specs_similarity": 0.4
        }
        
        products_coupang = [
            {
                "title": "노트북",
                "displayed_price": "1,000,000원",
                "thumbnail_url": "https://example.com/img1.jpg",
                "product_link": "https://coupang.com/product1"
            }
        ]
        
        products_ssadagu = [
            {
                "title": "노트북",
                "price": "1,050,000원",
                "thumbnail_url": "https://example.com/img2.jpg",
                "product_link": "https://ssadagu.com/product1"
            }
        ]
        
        callback_calls = []
        
        def progress_callback(progress, message):
            callback_calls.append((progress, message))
        
        matcher = ProductMatcher()
        results = await matcher.find_similar_products(
            products_coupang,
            products_ssadagu,
            progress_callback=progress_callback
        )
        
        # 콜백이 호출되었는지 확인
        assert len(callback_calls) > 0
    
    @pytest.mark.asyncio
    @patch('app.services.comparison.matcher.SimilarityCalculator.calculate_combined_similarity')
    async def test_find_top_matches(self, mock_calc):
        """상위 K개 상품 찾기."""
        # 여러 상품에 대한 Mock 결과
        mock_results = [
            {
                "combined_similarity": 0.9,
                "image_similarity": 0.9,
                "price_similarity": 0.9,
                "title_similarity": 0.9,
                "ocr_specs_similarity": 0.9
            },
            {
                "combined_similarity": 0.7,
                "image_similarity": 0.7,
                "price_similarity": 0.7,
                "title_similarity": 0.7,
                "ocr_specs_similarity": 0.7
            },
            {
                "combined_similarity": 0.5,
                "image_similarity": 0.5,
                "price_similarity": 0.5,
                "title_similarity": 0.5,
                "ocr_specs_similarity": 0.5
            },
        ]
        
        call_count = [0]
        def mock_calc_side_effect(*args, **kwargs):
            result = mock_results[call_count[0] % len(mock_results)]
            call_count[0] += 1
            return result
        
        mock_calc.side_effect = mock_calc_side_effect
        
        products_coupang = [
            {
                "title": f"노트북 {i}",
                "displayed_price": f"{1000000 + i * 10000}원",
                "thumbnail_url": f"https://example.com/img{i}.jpg",
                "product_link": f"https://coupang.com/product{i}"
            }
            for i in range(3)
        ]
        
        products_ssadagu = [
            {
                "title": f"노트북 {i}",
                "price": f"{1050000 + i * 10000}원",
                "thumbnail_url": f"https://example.com/img{i+10}.jpg",
                "product_link": f"https://ssadagu.com/product{i}"
            }
            for i in range(3)
        ]
        
        matcher = ProductMatcher(threshold=ProductMatcher.DEFAULT_THRESHOLD)
        results = await matcher.find_top_matches(products_coupang, products_ssadagu, top_k=2)
        
        # 상위 2개만 반환되어야 함
        assert len(results) <= 2
        # 유사도 내림차순 정렬 확인
        if len(results) > 1:
            assert results[0]["similarity"]["combined_similarity"] >= results[1]["similarity"]["combined_similarity"]
    
    @pytest.mark.asyncio
    @patch('app.services.comparison.matcher.SimilarityCalculator.calculate_combined_similarity')
    async def test_find_similar_products_handles_exceptions(self, mock_calc):
        """예외 처리."""
        mock_calc.side_effect = Exception("테스트 예외")
        
        products_coupang = [
            {
                "title": "노트북",
                "displayed_price": "1,000,000원",
                "thumbnail_url": "https://example.com/img1.jpg",
                "product_link": "https://coupang.com/product1"
            }
        ]
        
        products_ssadagu = [
            {
                "title": "노트북",
                "price": "1,050,000원",
                "thumbnail_url": "https://example.com/img2.jpg",
                "product_link": "https://ssadagu.com/product1"
            }
        ]
        
        matcher = ProductMatcher()
        results = await matcher.find_similar_products(products_coupang, products_ssadagu)
        
        # 예외가 발생해도 빈 리스트 반환
        assert isinstance(results, list)


# ============================================================================
# 통합 테스트 (비교 결과 JSON 저장 - GraphState 형식)
# ============================================================================

@pytest.mark.integration
@pytest.mark.slow
class TestRealIntegration:
    """
    GraphState 형식에 맞춘 비교 결과를 JSON으로 저장하는 통합 테스트.
    
    LangGraph에서 사용하는 GraphState 형식으로 데이터를 구성하고,
    실제 비교 로직을 실행하여 결과를 JSON 파일로 저장합니다.
    
    실행 방법:
    pytest test/comparison/test_comparison.py::TestRealIntegration::test_comparison_with_graphstate_format -v -s
    pytest test/comparison/test_comparison.py::TestRealIntegration::test_comparison_with_real_crawled_data -v -s
    """
    
    @pytest.mark.asyncio
    @patch('app.services.comparison.similarity.aiohttp.ClientSession')
    async def test_comparison_with_graphstate_format(self, mock_session_class):
        """
        GraphState 형식으로 쿠팡과 싸다구 상품을 비교하고 결과를 JSON 파일로 저장.
        
        LangGraph의 product_check 노드와 동일한 방식으로 데이터를 처리합니다.
        Mock 이미지 데이터를 사용하여 실제 비교 로직을 테스트합니다.
        """
        print("\n" + "="*70)
        print("🔍 상품 비교 테스트 시작 (GraphState 형식)")
        print("="*70)
        
        # Mock 이미지 데이터 설정
        img = Image.new('RGB', (100, 100), color='red')
        img_bytes = BytesIO()
        img.save(img_bytes, format='PNG')
        img_data = img_bytes.getvalue()
        
        # Mock HTTP 응답 설정
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=img_data)
        
        mock_get_context = MagicMock()
        mock_get_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get_context.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_get_context)
        
        mock_session_instance = MagicMock()
        mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_instance.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session_instance
        
        # GraphState 형식으로 상품 데이터 구성
        # products: dict[str, list[dict]] 형식
        products = {
            "coupang": [
                {
                    "title": "삼성 갤럭시 노트북 15.6인치 i7-13700H 16GB RAM 512GB SSD RTX 4060 블랙",
                    "displayed_price": "1,890,000원",
                    "original_price": "2,100,000원",
                    "price": "1,890,000원",
                    "thumbnail_url": "https://example.com/coupang1.jpg",
                    "product_link": "https://www.coupang.com/products/12345",
                    "ocr_text": "CPU: i7-13700H RAM: 16GB SSD: 512GB 그래픽: RTX 4060"
                },
                {
                    "title": "LG 그램 노트북 17인치 i5-1340P 8GB RAM 256GB SSD 화이트",
                    "displayed_price": "1,290,000원",
                    "price": "1,290,000원",
                    "thumbnail_url": "https://example.com/coupang2.jpg",
                    "product_link": "https://www.coupang.com/products/67890",
                    "ocr_text": "CPU: i5-1340P RAM: 8GB SSD: 256GB"
                }
            ],
            "ssadagu": [
                {
                    "title": "삼성 갤럭시 노트북 15.6인치 i7-13700H 16GB RAM 512GB SSD RTX 4060 블랙",
                    "price": "1,850,000원",
                    "displayed_price": "1,850,000원",
                    "thumbnail_url": "https://example.com/ssadagu1.jpg",
                    "product_link": "https://ssadagu.kr/shop/view.php?platform=1688&num_iid=12345",
                    "detail_specs": {
                        "프로세서": "i7-13700H",
                        "메모리 용량": "16GB",
                        "저장 유형": "SSD 512GB",
                        "그래픽 카드": "RTX 4060",
                        "화면 크기": "15.6인치",
                        "색상": "블랙"
                    }
                },
                {
                    "title": "애플 맥북 프로 14인치 M3 Pro 18GB RAM 512GB SSD 스페이스 그레이",
                    "price": "2,490,000원",
                    "displayed_price": "2,490,000원",
                    "thumbnail_url": "https://example.com/ssadagu2.jpg",
                    "product_link": "https://ssadagu.kr/shop/view.php?platform=1688&num_iid=67890",
                    "detail_specs": {
                        "프로세서": "M3 Pro",
                        "메모리 용량": "18GB",
                        "저장 유형": "SSD 512GB",
                        "화면 크기": "14인치",
                        "색상": "스페이스 그레이"
                    }
                }
            ]
        }
        
        # LangGraph product_check 노드처럼 데이터 추출
        products_coupang = products.get("coupang", [])
        products_ssadagu = products.get("ssadagu", [])
        
        print(f"\n📦 설정:")
        print(f"   - GraphState 형식: products (dict[str, list[dict]])")
        print(f"   - 쿠팡 상품 수: {len(products_coupang)}개")
        print(f"   - 싸다구 상품 수: {len(products_ssadagu)}개")
        print(f"\n⏳ 비교 시작...\n")
        
        # 상품 비교 실행 (LangGraph product_check 노드와 동일한 방식)
        matcher = ProductMatcher(threshold=ProductMatcher.DEFAULT_THRESHOLD)
        results = await matcher.find_similar_products(
            products_coupang,
            products_ssadagu
        )
        
        # 결과 저장 (test_comparison.py와 같은 경로, 고정 파일명)
        test_dir = Path(__file__).parent  # test/comparison/
        output_file = test_dir / "comparison_test_result.json"
        
        try:
            output_data = {
                "timestamp": datetime.now().isoformat(),
                "test_settings": {
                    "threshold": ProductMatcher.DEFAULT_THRESHOLD,
                    "data_format": "GraphState",
                    "products_structure": "dict[str, list[dict]]",
                    "coupang_products_count": len(products_coupang),
                    "ssadagu_products_count": len(products_ssadagu),
                },
                "graphstate": {
                    "products": products,  # 원본 GraphState 형식 데이터
                    "filtered_products": [
                        {"mall": "coupang", "items": products_coupang},
                        {"mall": "ssadagu", "items": products_ssadagu}
                    ]
                },
                "result": {
                    "total_matches": len(results),
                    "matches": results,
                },
            }
            
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            
            print(f"\n💾 결과 저장: {output_file}")
        except Exception as e:
            print(f"\n⚠️ 파일 저장 실패: {e}")
        
        # 결과 출력
        print("\n" + "="*70)
        print(f"✅ 비교 완료!")
        print(f"📊 총 {len(results)}개 유사 상품 쌍 발견")
        print("="*70)
        print("\n📋 매칭된 상품 쌍:")
        print("-" * 70)
        
        for idx, match in enumerate(results, 1):
            coupang = match.get("coupang_product", {})
            ssadagu = match.get("ssadagu_product", {})
            similarity = match.get("similarity", {})
            
            print(f"\n  {idx}. 매칭 쌍 #{idx}")
            print(f"     쿠팡: {coupang.get('title', 'Unknown')[:50]}...")
            print(f"           가격: {coupang.get('price', '정보 없음')}")
            print(f"     싸다구: {ssadagu.get('title', 'Unknown')[:50]}...")
            print(f"             가격: {ssadagu.get('price', '정보 없음')}")
            print(f"     종합 유사도: {similarity.get('combined_similarity', 0.0):.3f}")
            print(f"       - 이미지: {similarity.get('image_similarity', 0.0):.3f}")
            print(f"       - 가격: {similarity.get('price_similarity', 0.0):.3f}")
            print(f"       - 상품명: {similarity.get('title_similarity', 0.0):.3f}")
            print(f"       - 상세정보: {similarity.get('ocr_specs_similarity', 0.0):.3f}")
        
        print("\n" + "="*70)
        
        # 검증
        assert isinstance(results, list), "결과는 리스트여야 합니다"
        assert len(results) > 0, "최소 1개 이상의 매칭이 있어야 합니다"
        
        # 각 매칭 결과 검증
        for match in results:
            assert "coupang_product" in match, "쿠팡 상품 정보가 있어야 합니다"
            assert "ssadagu_product" in match, "싸다구 상품 정보가 있어야 합니다"
            assert "similarity" in match, "유사도 정보가 있어야 합니다"
            
            similarity = match["similarity"]
            assert "combined_similarity" in similarity, "종합 유사도가 있어야 합니다"
            assert 0.0 <= similarity["combined_similarity"] <= 1.0, "유사도는 0-1 사이여야 합니다"
    
    @pytest.mark.asyncio
    @patch('app.services.comparison.similarity.aiohttp.ClientSession')
    async def test_comparison_with_real_crawled_data(self, mock_session_class):
        """
        실제 크롤링된 데이터를 사용하여 비교 테스트.
        
        test/crawler/products/ 경로의 크롤링 결과 파일을 읽어서
        GraphState 형식으로 변환한 후 실제 비교를 수행합니다.
        
        파일이 없으면 스킵됩니다.
        """
        print("\n" + "="*70)
        print("🔍 실제 크롤링 데이터 비교 테스트")
        print("="*70)
        
        # 크롤링 결과 파일 경로
        crawler_test_dir = Path(__file__).parent.parent / "crawler" / "products"
        coupang_file = crawler_test_dir / "coupang_test_result.json"
        ssadagu_file = crawler_test_dir / "ssadagu_test_result.json"
        
        # 파일 존재 확인
        if not coupang_file.exists() or not ssadagu_file.exists():
            pytest.skip(f"크롤링 결과 파일이 없습니다. "
                       f"먼저 크롤링 테스트를 실행하세요: "
                       f"{coupang_file} 또는 {ssadagu_file}")
        
        # 크롤링 결과 파일 읽기
        try:
            with open(coupang_file, "r", encoding="utf-8") as f:
                coupang_data = json.load(f)
            with open(ssadagu_file, "r", encoding="utf-8") as f:
                ssadagu_data = json.load(f)
        except Exception as e:
            pytest.skip(f"크롤링 결과 파일을 읽을 수 없습니다: {e}")
        
        # GraphState 형식으로 변환
        products = {
            "coupang": coupang_data.get("result", {}).get("products", []),
            "ssadagu": ssadagu_data.get("result", {}).get("products", [])
        }
        
        products_coupang = products.get("coupang", [])
        products_ssadagu = products.get("ssadagu", [])
        
        if not products_coupang or not products_ssadagu:
            pytest.skip("크롤링 결과에 상품이 없습니다.")
        
        # Mock 이미지 데이터 설정 (실제 이미지 다운로드 대신)
        img = Image.new('RGB', (100, 100), color='red')
        img_bytes = BytesIO()
        img.save(img_bytes, format='PNG')
        img_data = img_bytes.getvalue()
        
        # Mock HTTP 응답 설정
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=img_data)
        
        mock_get_context = MagicMock()
        mock_get_context.__aenter__ = AsyncMock(return_value=mock_response)
        mock_get_context.__aexit__ = AsyncMock(return_value=None)
        
        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_get_context)
        
        mock_session_instance = MagicMock()
        mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session_instance.__aexit__ = AsyncMock(return_value=None)
        mock_session_class.return_value = mock_session_instance
        
        print(f"\n📦 설정:")
        print(f"   - 데이터 소스: 실제 크롤링 결과 파일")
        print(f"   - 쿠팡 파일: {coupang_file.name}")
        print(f"   - 싸다구 파일: {ssadagu_file.name}")
        print(f"   - 쿠팡 상품 수: {len(products_coupang)}개")
        print(f"   - 싸다구 상품 수: {len(products_ssadagu)}개")
        print(f"\n⏳ 비교 시작...\n")
        
        # 상품 비교 실행
        matcher = ProductMatcher(threshold=ProductMatcher.DEFAULT_THRESHOLD)
        results = await matcher.find_similar_products(
            products_coupang,
            products_ssadagu
        )
        
        # 결과 저장
        test_dir = Path(__file__).parent
        output_file = test_dir / "comparison_real_data_result.json"
        
        try:
            output_data = {
                "timestamp": datetime.now().isoformat(),
                "test_settings": {
                    "threshold": ProductMatcher.DEFAULT_THRESHOLD,
                    "data_source": "real_crawled_data",
                    "coupang_file": str(coupang_file),
                    "ssadagu_file": str(ssadagu_file),
                    "coupang_products_count": len(products_coupang),
                    "ssadagu_products_count": len(products_ssadagu),
                },
                "graphstate": {
                    "products": products,
                    "filtered_products": [
                        {"mall": "coupang", "items": products_coupang},
                        {"mall": "ssadagu", "items": products_ssadagu}
                    ]
                },
                "result": {
                    "total_matches": len(results),
                    "matches": results,
                },
            }
            
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            
            print(f"\n💾 결과 저장: {output_file}")
        except Exception as e:
            print(f"\n⚠️ 파일 저장 실패: {e}")
        
        # 결과 출력
        print("\n" + "="*70)
        print(f"✅ 비교 완료!")
        print(f"📊 총 {len(results)}개 유사 상품 쌍 발견")
        print("="*70)
        
        if results:
            print("\n📋 매칭된 상품 쌍 (상위 5개):")
            print("-" * 70)
            
            for idx, match in enumerate(results[:5], 1):
                coupang = match.get("coupang_product", {})
                ssadagu = match.get("ssadagu_product", {})
                similarity = match.get("similarity", {})
                
                print(f"\n  {idx}. 매칭 쌍 #{idx}")
                print(f"     쿠팡: {coupang.get('title', 'Unknown')[:50]}...")
                print(f"           가격: {coupang.get('price', '정보 없음')}")
                print(f"     싸다구: {ssadagu.get('title', 'Unknown')[:50]}...")
                print(f"             가격: {ssadagu.get('price', '정보 없음')}")
                print(f"     종합 유사도: {similarity.get('combined_similarity', 0.0):.3f}")
        
        print("\n" + "="*70)
        
        # 검증
        assert isinstance(results, list), "결과는 리스트여야 합니다"

