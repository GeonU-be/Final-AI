"""
네이버 쇼핑 크롤러 통합 테스트 모듈.

실제 브라우저를 사용하는 통합 테스트만 포함합니다.
Mock 테스트와 완전히 격리되어 있습니다.

실행 방법:
pytest test/crawler/products/test_naver_integration.py -v -s

또는 마커 사용:
pytest test/crawler/products/test_naver_integration.py -m integration -v -s
"""

import pytest
from pathlib import Path
import json
from datetime import datetime

from app.services.crawler.products.naver_crawler import crawl_naver_products


@pytest.mark.integration
@pytest.mark.slow
class TestRealIntegration:
    """
    실제 브라우저를 사용하는 통합 테스트 (느리고 불안정할 수 있음).
    
    이 클래스의 테스트는 Mock을 사용하지 않습니다.
    실제 Selenium 브라우저를 실행하고 실제 네이버 쇼핑에 접속합니다.
    
    실행 방법:
    pytest test/crawler/products/test_naver_integration.py::TestRealIntegration::test_real_naver_crawling -v -s
    
    또는 마커 사용:
    pytest test/crawler/products/test_naver_integration.py -m integration -v -s
    
    주의: driver.quit()이 자동으로 호출되므로 사용자가 열어둔 Chrome 창은 영향받지 않습니다.
    """
    
    @pytest.mark.asyncio
    async def test_real_naver_crawling(self):
        """
        실제 네이버 쇼핑 크롤링 테스트.
        
        주의: 이 테스트는 실제 브라우저를 실행하고 네이버 쇼핑에 접속합니다.
        실행 시간이 오래 걸릴 수 있으며, 네트워크 연결이 필요합니다.
        """
        print("\n" + "="*70)
        print("🔍 실제 네이버 쇼핑 크롤링 테스트 시작")
        print("="*70)
        
        # 실제 크롤링 실행
        keyword = "패딩"
        max_products = 5  # 테스트용으로 적은 수
        print(f"\n📦 설정:")
        print(f"   - 검색 키워드: {keyword}")
        print(f"   - 최대 수집 개수: {max_products}개")
        print(f"   - 헤드리스 모드: False")
        print(f"\n⏳ 크롤링 시작... (1~2분 정도 소요될 수 있습니다)\n")
        
        result = await crawl_naver_products(
            keyword,
            max_products=max_products,
            headless=False,
        )
        
        # 결과 저장 (test_naver_integration.py와 같은 경로, 고정 파일명)
        test_dir = Path(__file__).parent  # test/crawler/products/
        output_file = test_dir / "naver_test_result.json"
        try:
            output_data = {
                "timestamp": datetime.now().isoformat(),
                "test_settings": {
                    "keyword": keyword,
                    "max_products": max_products,
                    "headless": False,
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
            if product.get('original_price'):
                print(f"     원가: {product.get('original_price')}")
            if product.get('displayed_price'):
                print(f"     할인가격: {product.get('displayed_price')}")
            print(f"     링크: {product.get('product_link', '정보 없음')[:60]}...")
            detail_specs = product.get('detail_specs', {})
            if detail_specs:
                print(f"     상세 스펙 ({len(detail_specs)}개 항목):")
                for spec_key, spec_val in list(detail_specs.items())[:3]:
                    print(f"       - {spec_key}: {spec_val[:50]}...")
            else:
                print(f"     상세 스펙: 없음 (상품이 존재하지 않거나 스펙 추출 실패)")
        
        print("\n" + "="*70)
        
        # 최소한 1개 이상의 상품이 수집되어야 함
        assert len(result) > 0, "상품이 수집되지 않았습니다"
        
        # 각 상품에 필수 필드가 있는지 확인
        products_with_specs = 0
        products_without_specs = 0
        
        for product in result:
            assert "title" in product, "상품에 title이 없습니다"
            assert product["title"], "상품 title이 비어있습니다"
            assert "product_link" in product, "상품에 product_link가 없습니다"
            assert "thumbnail_url" in product, "상품에 thumbnail_url 필드가 없습니다"
            assert "detail_specs" in product, "상품에 detail_specs 필드가 없습니다"
            assert isinstance(product["detail_specs"], dict), "detail_specs는 딕셔너리여야 합니다"
            
            # 상세 스펙이 있는 상품과 없는 상품 카운트
            if product["detail_specs"]:
                products_with_specs += 1
            else:
                products_without_specs += 1
        
        # 상세 스펙 수집 통계 출력
        print(f"\n📊 상세 스펙 수집 통계:")
        print(f"  - 총 상품 수: {len(result)}")
        print(f"  - 상세 스펙 수집 성공: {products_with_specs}개")
        print(f"  - 상세 스펙 수집 실패: {products_without_specs}개")
        
        if products_with_specs > 0:
            print(f"\n  ✅ 상세 스펙이 있는 상품 예시 (최대 3개):")
            for idx, product in enumerate([p for p in result if p.get("detail_specs")][:3], 1):
                print(f"    {idx}. {product.get('title', 'Unknown')[:40]}...")
                specs = product.get('detail_specs', {})
                print(f"       스펙 항목: {list(specs.keys())[:5]}")
        
        if products_without_specs > 0:
            print(f"\n  ⚠️ 상세 스펙이 없는 상품 (최대 3개):")
            for idx, product in enumerate([p for p in result if not p.get("detail_specs")][:3], 1):
                print(f"    {idx}. {product.get('title', 'Unknown')[:40]}...")
                print(f"       링크: {product.get('product_link', '')[:60]}...")
                print(f"       (상품이 존재하지 않거나 스펙 추출 실패 가능)")

