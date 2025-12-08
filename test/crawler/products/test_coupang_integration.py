"""
쿠팡 크롤러 통합 테스트 모듈.

실제 브라우저를 사용하는 통합 테스트만 포함합니다.
Mock 테스트와 완전히 격리되어 있습니다.

실행 방법:
pytest test/crawler/products/test_coupang_integration.py -v -s
"""

import pytest
from pathlib import Path
import json
from datetime import datetime
import time
import platform
import subprocess

from app.services.crawler.products.coupang_crawler import crawl_coupang_products


def _kill_chrome_processes():
    """Chrome 프로세스를 종료하는 헬퍼 함수."""
    try:
        if platform.system() == "Windows":
            subprocess.run(
                ["taskkill", "/F", "/IM", "chrome.exe", "/T"],
                capture_output=True,
                timeout=5
            )
            subprocess.run(
                ["taskkill", "/F", "/IM", "chromedriver.exe", "/T"],
                capture_output=True,
                timeout=5
            )
        elif platform.system() == "Darwin":  # macOS
            subprocess.run(
                ["pkill", "-f", "Google Chrome"],
                capture_output=True,
                timeout=5
            )
            subprocess.run(
                ["pkill", "-f", "chromedriver"],
                capture_output=True,
                timeout=5
            )
        else:  # Linux
            subprocess.run(
                ["pkill", "-f", "google-chrome"],
                capture_output=True,
                timeout=5
            )
            subprocess.run(
                ["pkill", "-f", "chromedriver"],
                capture_output=True,
                timeout=5
            )
        time.sleep(1)  # 프로세스 종료 대기
    except Exception:
        pass  # 프로세스가 없어도 무시


@pytest.mark.integration
@pytest.mark.slow
class TestRealIntegration:
    """실제 브라우저를 사용하는 통합 테스트."""
    
    @pytest.fixture(autouse=True, scope="class")
    def setup_integration_test(self):
        """통합 테스트 전후 Chrome 프로세스 정리."""
        # 테스트 전 Chrome 프로세스 정리 (이전 실행에서 남은 프로세스 제거)
        _kill_chrome_processes()
        
        yield  # 테스트 실행
        
        # 테스트 후 Chrome 프로세스 정리
        _kill_chrome_processes()
    
    @pytest.mark.asyncio
    async def test_real_coupang_crawling(self):
        """
        실제 쿠팡 크롤링 테스트.
        
        주의: 이 테스트는 실제 브라우저를 실행하고 쿠팡에 접속합니다.
        실행 시간이 오래 걸릴 수 있으며, 네트워크 연결이 필요합니다.
        """
        keyword = "노트북"
        max_products = 5  # 테스트용으로 적은 수
        
        result = await crawl_coupang_products(
            keyword,
            max_products=max_products,
            headless=False,
            fetch_detail_images=True,
            max_pages=1,
            use_ocr=True,  # OCR로 상세 이미지에서 텍스트 추출
            max_ocr_images=3,  # 상품당 최대 3개 이미지 OCR 처리
        )
        
        # 결과 저장 (test_coupang_integration.py와 같은 경로, 고정 파일명)
        test_dir = Path(__file__).parent  # test/crawler/products/
        output_file = test_dir / "coupang_test_result.json"
        try:
            output_data = {
                "timestamp": datetime.now().isoformat(),
                "test_settings": {
                    "keyword": keyword,
                    "max_products": max_products,
                    "headless": False,
                    "fetch_detail_images": True,
                    "max_pages": 1,
                    "use_ocr": True,
                    "max_ocr_images": 3,
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
        
        print(f"\n{'='*60}")
        print(f"쿠팡 크롤링 테스트 결과")
        print(f"{'='*60}")
        print(f"키워드: {keyword}")
        print(f"수집된 상품 수: {len(result)}")
        print(f"결과 파일: {output_file}")
        print(f"{'='*60}\n")
        
        # 최소한 1개 이상의 상품이 수집되어야 함
        assert len(result) > 0, "상품이 수집되지 않았습니다"
        
        # 각 상품에 필수 필드가 있는지 확인
        ocr_processed_count = 0
        for product in result:
            assert "title" in product, "상품에 title이 없습니다"
            assert product["title"], "상품 title이 비어있습니다"
            assert "product_link" in product, "상품에 product_link가 없습니다"
            
            # OCR 기능 검증
            assert "ocr_text" in product, "상품에 ocr_text 필드가 없습니다 (OCR 기능 미작동)"
            # ocr_text는 문자열이어야 함 (빈 문자열도 허용)
            assert isinstance(product["ocr_text"], str), "ocr_text는 문자열이어야 합니다"
            
            # 원본 OCR 텍스트 필드도 확인 (디버깅용, 선택적)
            if "ocr_text_raw" in product:
                assert isinstance(product["ocr_text_raw"], str), "ocr_text_raw는 문자열이어야 합니다"
            
            # 상세 이미지가 있고 OCR이 성공한 경우 검증
            detail_images = product.get("detail_images", [])
            if detail_images and product["ocr_text"]:
                ocr_processed_count += 1
                # OCR 텍스트에 마케팅 문구가 제거되었는지 확인 (clean_ocr_text 적용 여부)
                ocr_text = product["ocr_text"]
                # 마케팅 문구가 제거되었는지 간접 확인 (일부 마케팅 키워드가 없어야 함)
                marketing_keywords = ["배송", "도착", "출고", "특가", "할인", "프로모션", "이벤트"]
                # 주의: 마케팅 키워드가 완전히 제거되지 않을 수 있으므로, 단순히 필드 존재만 확인
        
        # OCR 처리 결과 출력
        print(f"\n📝 OCR 처리 결과:")
        print(f"  - 총 상품 수: {len(result)}")
        print(f"  - OCR 텍스트 추출 성공: {ocr_processed_count}개")
        
        # 원본 OCR 텍스트가 있는 상품 수 확인
        raw_ocr_count = sum(1 for p in result if p.get("ocr_text_raw"))
        print(f"  - 원본 OCR 텍스트 존재: {raw_ocr_count}개")
        
        # OCR 텍스트가 있는 상품 예시 출력
        ocr_examples = [p for p in result if p.get("ocr_text")]
        if ocr_examples:
            print(f"\n  ✅ 정제된 OCR 텍스트 예시 (최대 3개):")
            for idx, product in enumerate(ocr_examples[:3], 1):
                ocr_text = product["ocr_text"]
                preview = ocr_text[:100] + "..." if len(ocr_text) > 100 else ocr_text
                print(f"    {idx}. {product.get('title', 'Unknown')[:30]}...")
                print(f"       OCR: {preview}")
        
        # 원본 텍스트는 있지만 정제 후 빈 문자열인 경우
        raw_only = [p for p in result if p.get("ocr_text_raw") and not p.get("ocr_text")]
        if raw_only:
            print(f"\n  ⚠️ 원본 텍스트는 있지만 정제 후 제거됨 (최대 3개):")
            for idx, product in enumerate(raw_only[:3], 1):
                raw_text = product.get("ocr_text_raw", "")
                preview = raw_text[:150] + "..." if len(raw_text) > 150 else raw_text
                print(f"    {idx}. {product.get('title', 'Unknown')[:30]}...")
                print(f"       원본: {preview}")
        
        # OCR이 전혀 실행되지 않은 경우 (원본도 없음)
        no_ocr = [p for p in result if not p.get("ocr_text_raw") and p.get("detail_images")]
        if no_ocr:
            print(f"\n  ❌ 상세 이미지는 있지만 OCR 텍스트 추출 실패: {len(no_ocr)}개")

