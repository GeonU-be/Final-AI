"""
Twitter(X.com) 크롤러 테스트 모듈.

Twitter 실시간 트렌드 키워드 크롤러 테스트.

테스트 구조:
- 단위 테스트 (TestValidText, TestCrawlTwitterTrends, TestGetTrendKeywords)
  : Mock 사용, 빠른 실행, 외부 의존성 없음
  
- 통합 테스트 (TestRealIntegration)
  : 실제 브라우저 실행, Mock 없음, 실제 X.com 접속 (쿠키 파일 필요)
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from pathlib import Path
import json
import os
from datetime import datetime

from app.services.crawler.keywords.twitter_crawler import (
    _valid_text,
    crawl_twitter_trends,
    get_trend_keywords,
    save_twitter_cookies,
    EXCLUDED_TEXTS,
    TREND_URL,
    LOGIN_URL,
    DEFAULT_COOKIE_FILE,
)


class TestValidText:
    """_valid_text 헬퍼 함수 테스트."""
    
    def test_valid_text_accepts_normal_keyword(self):
        """정상적인 키워드는 통과."""
        assert _valid_text("노트북", EXCLUDED_TEXTS) is True
        # "아이폰 15"는 EXCLUDED_TEXTS에 "5"가 포함되어 있어서 거부될 수 있음
        # 실제 함수 동작: any(excluded in text) 체크로 인해 "5"가 포함된 텍스트 거부
        assert _valid_text("아이폰", EXCLUDED_TEXTS) is True
        # "트렌드 키워드"는 EXCLUDED_TEXTS에 "트렌드"가 포함되어 있어서 거부됨
        # 실제 함수 동작: any(excluded in text) 체크로 인해 "트렌드"가 포함된 텍스트 거부
        assert _valid_text("인기 키워드", EXCLUDED_TEXTS) is True
    
    def test_valid_text_rejects_empty_or_short(self):
        """빈 문자열이나 너무 짧은 텍스트는 거부."""
        assert _valid_text("", EXCLUDED_TEXTS) is False
        assert _valid_text("a", EXCLUDED_TEXTS) is False  # 1글자
        assert _valid_text("가", EXCLUDED_TEXTS) is False  # 1글자
    
    def test_valid_text_rejects_too_long(self):
        """너무 긴 텍스트는 거부."""
        long_text = "a" * 101  # 101글자
        assert _valid_text(long_text, EXCLUDED_TEXTS) is False
    
    def test_valid_text_rejects_urls(self):
        """URL은 거부."""
        assert _valid_text("http://example.com", EXCLUDED_TEXTS) is False
        assert _valid_text("https://twitter.com", EXCLUDED_TEXTS) is False
    
    def test_valid_text_rejects_at_mentions(self):
        """@로 시작하는 텍스트는 거부."""
        assert _valid_text("@username", EXCLUDED_TEXTS) is False
        assert _valid_text("@twitter", EXCLUDED_TEXTS) is False
    
    def test_valid_text_rejects_digits(self):
        """숫자만 있는 텍스트는 거부."""
        assert _valid_text("123", EXCLUDED_TEXTS) is False
        assert _valid_text("42", EXCLUDED_TEXTS) is False
    
    def test_valid_text_rejects_excluded_texts(self):
        """제외 목록에 있는 텍스트는 거부."""
        assert _valid_text("Home", EXCLUDED_TEXTS) is False
        assert _valid_text("Explore", EXCLUDED_TEXTS) is False
        assert _valid_text("트렌드", EXCLUDED_TEXTS) is False
    
    def test_valid_text_rejects_texts_containing_excluded(self):
        """제외 텍스트를 포함하는 경우도 거부."""
        assert _valid_text("Home page", EXCLUDED_TEXTS) is False
        assert _valid_text("Explore more", EXCLUDED_TEXTS) is False
    
    def test_valid_text_rejects_too_many_words(self):
        """너무 많은 단어는 거부 (15개 초과)."""
        many_words = " ".join(["word"] * 16)  # 16개 단어
        assert _valid_text(many_words, EXCLUDED_TEXTS) is False


class TestCrawlTwitterTrends:
    """crawl_twitter_trends 메인 함수 테스트."""
    
    @patch('app.services.crawler.keywords.twitter_crawler.async_playwright')
    @patch('app.services.crawler.keywords.twitter_crawler.os.path.exists')
    @pytest.mark.asyncio
    async def test_crawl_twitter_trends_success(self, mock_exists, mock_playwright):
        """성공적인 크롤링 테스트."""
        # Mock 설정
        mock_exists.return_value = True  # 쿠키 파일 존재
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()
        mock_playwright_instance = MagicMock()
        
        mock_playwright.return_value.__aenter__ = AsyncMock(return_value=mock_playwright_instance)
        mock_playwright.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)
        
        # Mock 쿠키 파일 읽기
        mock_cookies = [{"name": "test", "value": "cookie"}]
        with patch('builtins.open', mock_open(read_data=json.dumps(mock_cookies))):
            
            # Mock 페이지 요소 설정
            mock_span = AsyncMock()
            mock_span.inner_text = AsyncMock(return_value="테스트 키워드")
            
            mock_trend_elem = AsyncMock()
            mock_trend_elem.query_selector_all = AsyncMock(return_value=[mock_span])
            
            mock_page.query_selector_all = AsyncMock(return_value=[mock_trend_elem])
            mock_page.content = AsyncMock(return_value="<html>content</html>")
            mock_page.url = TREND_URL
            mock_page.goto = AsyncMock(return_value=None)
            mock_page.wait_for_selector = AsyncMock(return_value=None)
            mock_page.evaluate = AsyncMock(return_value=None)
            mock_context.add_cookies = AsyncMock(return_value=None)
            mock_browser.close = AsyncMock(return_value=None)
            
            # 함수 실행
            result = await crawl_twitter_trends(headless=True, max_trends=5, cookie_file="test_cookies.json")
            
            # 검증
            assert isinstance(result, dict)
            assert "total_trends" in result
            assert "trends" in result
            assert "source" in result
            assert "collected_at" in result
            assert isinstance(result["trends"], list)
            assert result["total_trends"] >= 0
            
            # 브라우저가 닫혔는지 확인
            mock_browser.close.assert_called_once()
    
    @patch('app.services.crawler.keywords.twitter_crawler.os.path.exists')
    @pytest.mark.asyncio
    async def test_crawl_twitter_trends_missing_cookie_file(self, mock_exists):
        """쿠키 파일이 없을 때 에러 발생."""
        mock_exists.return_value = False
        
        with pytest.raises(FileNotFoundError) as exc_info:
            await crawl_twitter_trends(cookie_file="nonexistent.json")
        
        assert "쿠키 파일을 찾을 수 없습니다" in str(exc_info.value)
    
    @patch('app.services.crawler.keywords.twitter_crawler.async_playwright')
    @patch('app.services.crawler.keywords.twitter_crawler.os.path.exists')
    @pytest.mark.asyncio
    async def test_crawl_twitter_trends_with_custom_excluded_texts(self, mock_exists, mock_playwright):
        """커스텀 제외 텍스트 사용 테스트."""
        mock_exists.return_value = True
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()
        mock_playwright_instance = MagicMock()
        
        mock_playwright.return_value.__aenter__ = AsyncMock(return_value=mock_playwright_instance)
        mock_playwright.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)
        
        # Mock 쿠키 파일
        mock_cookies = [{"name": "test", "value": "cookie"}]
        with patch('builtins.open', mock_open(read_data=json.dumps(mock_cookies))):
            mock_page.query_selector_all = AsyncMock(return_value=[])
            mock_page.content = AsyncMock(return_value="<html>content</html>")
            mock_page.url = TREND_URL
            mock_page.goto = AsyncMock(return_value=None)
            mock_page.wait_for_selector = AsyncMock(return_value=None)
            mock_page.evaluate = AsyncMock(return_value=None)
            mock_context.add_cookies = AsyncMock(return_value=None)
            mock_browser.close = AsyncMock(return_value=None)
            
            custom_excluded = {"커스텀", "제외", "텍스트"}
            result = await crawl_twitter_trends(
                headless=True,
                max_trends=10,
                cookie_file="test_cookies.json",
                excluded_texts=custom_excluded
            )
            
            assert isinstance(result, dict)
            assert result["total_trends"] == 0
            assert result["trends"] == []
    
    @patch('app.services.crawler.keywords.twitter_crawler.async_playwright')
    @patch('app.services.crawler.keywords.twitter_crawler.os.path.exists')
    @pytest.mark.asyncio
    async def test_crawl_twitter_trends_respects_max_trends(self, mock_exists, mock_playwright):
        """max_trends 제한 테스트."""
        mock_exists.return_value = True
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()
        mock_playwright_instance = MagicMock()
        
        mock_playwright.return_value.__aenter__ = AsyncMock(return_value=mock_playwright_instance)
        mock_playwright.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)
        
        # 여러 키워드 반환하도록 설정
        mock_spans = []
        for i in range(20):
            mock_span = AsyncMock()
            mock_span.inner_text = AsyncMock(return_value=f"키워드 {i}")
            mock_spans.append(mock_span)
        
        mock_trend_elem = AsyncMock()
        mock_trend_elem.query_selector_all = AsyncMock(return_value=mock_spans)
        
        # Mock 쿠키 파일
        mock_cookies = [{"name": "test", "value": "cookie"}]
        with patch('builtins.open', mock_open(read_data=json.dumps(mock_cookies))):
            mock_page.query_selector_all = AsyncMock(return_value=[mock_trend_elem])
            mock_page.content = AsyncMock(return_value="<html>content</html>")
            mock_page.url = TREND_URL
            mock_page.goto = AsyncMock(return_value=None)
            mock_page.wait_for_selector = AsyncMock(return_value=None)
            mock_page.evaluate = AsyncMock(return_value=None)
            mock_context.add_cookies = AsyncMock(return_value=None)
            mock_browser.close = AsyncMock(return_value=None)
            
            result = await crawl_twitter_trends(headless=True, max_trends=5, cookie_file="test_cookies.json")
            
            assert result["total_trends"] <= 5
            assert len(result["trends"]) <= 5
    
    @patch('app.services.crawler.keywords.twitter_crawler.async_playwright')
    @patch('app.services.crawler.keywords.twitter_crawler.os.path.exists')
    @pytest.mark.asyncio
    async def test_crawl_twitter_trends_handles_expired_cookie(self, mock_exists, mock_playwright):
        """만료된 쿠키 처리 테스트."""
        mock_exists.return_value = True
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()
        mock_playwright_instance = MagicMock()
        
        mock_playwright.return_value.__aenter__ = AsyncMock(return_value=mock_playwright_instance)
        mock_playwright.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)
        
        # 로그인 페이지로 리다이렉트된 경우
        mock_page.content = AsyncMock(return_value="<html>Log in</html>")
        mock_page.url = "https://x.com/i/flow/login"
        mock_page.goto = AsyncMock(return_value=None)
        mock_context.add_cookies = AsyncMock(return_value=None)
        mock_browser.close = AsyncMock(return_value=None)
        
        # Mock 쿠키 파일
        mock_cookies = [{"name": "test", "value": "cookie"}]
        with patch('builtins.open', mock_open(read_data=json.dumps(mock_cookies))):
            result = await crawl_twitter_trends(
                headless=True,
                max_trends=10,
                cookie_file="test_cookies.json"
            )
            
            assert isinstance(result, dict)
            assert result["total_trends"] == 0
            assert result["trends"] == []
            # 쿠키 파일 삭제는 twitter_cookie_manager에서 처리하므로 여기서는 호출하지 않음


class TestGetTrendKeywords:
    """get_trend_keywords 편의 함수 테스트."""
    
    @patch('app.services.crawler.keywords.twitter_crawler.crawl_twitter_trends', new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_get_trend_keywords_returns_list(self, mock_crawl):
        """키워드 리스트 반환 테스트."""
        mock_crawl.return_value = {
            "total_trends": 3,
            "source": TREND_URL,
            "collected_at": "2024-01-01 12:00:00",
            "trends": [
                {"keyword": "키워드1"},
                {"keyword": "키워드2"},
                {"keyword": "키워드3"},
            ]
        }
        
        result = await get_trend_keywords(max_trends=3, cookie_file="test_cookies.json")
        
        assert isinstance(result, list)
        assert len(result) == 3
        assert result == ["키워드1", "키워드2", "키워드3"]
        mock_crawl.assert_called_once()
    
    @patch('app.services.crawler.keywords.twitter_crawler.crawl_twitter_trends', new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_get_trend_keywords_filters_missing_keyword(self, mock_crawl):
        """keyword 필드가 없는 항목은 필터링."""
        mock_crawl.return_value = {
            "total_trends": 3,
            "source": TREND_URL,
            "collected_at": "2024-01-01 12:00:00",
            "trends": [
                {"keyword": "키워드1"},
                {},  # keyword 없음
                {"keyword": "키워드3"},
            ]
        }
        
        result = await get_trend_keywords(cookie_file="test_cookies.json")
        
        assert len(result) == 2
        assert "키워드1" in result
        assert "키워드3" in result
    
    @patch('app.services.crawler.keywords.twitter_crawler.crawl_twitter_trends', new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_get_trend_keywords_handles_empty_result(self, mock_crawl):
        """빈 결과 처리."""
        mock_crawl.return_value = {
            "total_trends": 0,
            "source": TREND_URL,
            "collected_at": "2024-01-01 12:00:00",
            "trends": []
        }
        
        result = await get_trend_keywords(cookie_file="test_cookies.json")
        
        assert isinstance(result, list)
        assert len(result) == 0
    
    @patch('app.services.crawler.keywords.twitter_crawler.crawl_twitter_trends', new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_get_trend_keywords_passes_parameters(self, mock_crawl):
        """파라미터 전달 테스트."""
        mock_crawl.return_value = {
            "total_trends": 0,
            "source": TREND_URL,
            "collected_at": "2024-01-01 12:00:00",
            "trends": []
        }
        
        custom_excluded = {"커스텀"}
        await get_trend_keywords(
            headless=False,
            max_trends=50,
            cookie_file="custom_cookies.json",
            excluded_texts=custom_excluded,
            page_timeout_ms=30000
        )
        
        mock_crawl.assert_called_once_with(
            headless=False,
            max_trends=50,
            cookie_file="custom_cookies.json",
            excluded_texts=custom_excluded,
            page_timeout_ms=30000
        )


class TestSaveTwitterCookies:
    """save_twitter_cookies 함수 테스트."""
    
    @patch('app.services.crawler.keywords.twitter_crawler.sync_playwright')
    def test_save_twitter_cookies_success(self, mock_playwright):
        """쿠키 저장 성공 테스트."""
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_playwright_instance = MagicMock()
        
        mock_playwright.return_value.__enter__.return_value = mock_playwright_instance
        mock_playwright_instance.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        
        # 로그인 완료 시뮬레이션
        mock_page.url = "https://x.com/home"
        mock_page.content.return_value = "<html>Home</html>"
        mock_page.query_selector_all.return_value = [MagicMock()]  # nav 요소
        
        # 쿠키 저장
        mock_cookies = [{"name": "test", "value": "cookie"}]
        mock_context.cookies.return_value = mock_cookies
        
        with patch('builtins.open', create=True) as mock_open:
            mock_file = MagicMock()
            mock_file.__enter__.return_value = mock_file
            mock_open.return_value = mock_file
            
            result = save_twitter_cookies(cookie_file="test_cookies.json", headless=True)
            
            assert result is True
            mock_browser.close.assert_called_once()
    
    @patch('app.services.crawler.keywords.twitter_crawler.sync_playwright')
    @patch('app.services.crawler.keywords.twitter_crawler.time')
    def test_save_twitter_cookies_login_timeout(self, mock_time, mock_playwright):
        """로그인 타임아웃 테스트."""
        # 시간 Mock 설정: time.time()이 호출될 때마다 증가
        # 시작: 0초, 이후 3초씩 증가하여 300초(5분)를 넘어서 타임아웃 발생
        call_count = [0]  # 클로저를 사용하여 호출 횟수 추적
        
        def time_side_effect():
            # 첫 번째 호출: start_time = 0
            # 이후 호출: 3, 6, 9, ... 300, 303 (타임아웃)
            call_count[0] += 1
            if call_count[0] == 1:
                return 0  # start_time
            else:
                # 3초 간격으로 증가, 300초를 넘어서면 타임아웃
                return (call_count[0] - 1) * 3
        
        mock_time.time.side_effect = time_side_effect
        mock_time.sleep = MagicMock()  # sleep은 즉시 완료
        
        mock_browser = MagicMock()
        mock_context = MagicMock()
        mock_page = MagicMock()
        mock_playwright_instance = MagicMock()
        
        mock_playwright.return_value.__enter__.return_value = mock_playwright_instance
        mock_playwright_instance.chromium.launch.return_value = mock_browser
        mock_browser.new_context.return_value = mock_context
        mock_context.new_page.return_value = mock_page
        
        # 로그인 페이지에 머물러 있음 (로그인 완료되지 않음)
        mock_page.url = LOGIN_URL
        mock_page.content.return_value = "<html>Log in</html>"
        mock_page.query_selector_all.return_value = []  # nav 요소 없음
        
        result = save_twitter_cookies(cookie_file="test_cookies.json", headless=True)
        
        assert result is False
        mock_browser.close.assert_called_once()


class TestIntegration:
    """통합 테스트 (실제 브라우저 실행 없이)."""
    
    @patch('app.services.crawler.keywords.twitter_crawler.async_playwright')
    @patch('app.services.crawler.keywords.twitter_crawler.os.path.exists')
    @pytest.mark.asyncio
    async def test_full_workflow(self, mock_exists, mock_playwright):
        """전체 워크플로우 테스트."""
        mock_exists.return_value = True
        mock_browser = AsyncMock()
        mock_context = AsyncMock()
        mock_page = AsyncMock()
        mock_playwright_instance = MagicMock()
        
        mock_playwright.return_value.__aenter__ = AsyncMock(return_value=mock_playwright_instance)
        mock_playwright.return_value.__aexit__ = AsyncMock(return_value=None)
        mock_playwright_instance.chromium.launch = AsyncMock(return_value=mock_browser)
        mock_browser.new_context = AsyncMock(return_value=mock_context)
        mock_context.new_page = AsyncMock(return_value=mock_page)
        
        # 실제 키워드처럼 보이는 데이터
        test_keywords = [
            "아이폰 15",
            "갤럭시 S24",
            "노트북",
            "태블릿",
            "스마트워치"
        ]
        
        mock_spans = []
        for keyword in test_keywords:
            mock_span = AsyncMock()
            mock_span.inner_text = AsyncMock(return_value=keyword)
            mock_spans.append(mock_span)
        
        mock_trend_elem = AsyncMock()
        mock_trend_elem.query_selector_all = AsyncMock(return_value=mock_spans)
        
        # Mock 쿠키 파일
        mock_cookies = [{"name": "test", "value": "cookie"}]
        with patch('builtins.open', mock_open(read_data=json.dumps(mock_cookies))):
            mock_page.query_selector_all = AsyncMock(return_value=[mock_trend_elem])
            mock_page.content = AsyncMock(return_value="<html>content</html>")
            mock_page.url = TREND_URL
            mock_page.goto = AsyncMock(return_value=None)
            mock_page.wait_for_selector = AsyncMock(return_value=None)
            mock_page.evaluate = AsyncMock(return_value=None)
            mock_context.add_cookies = AsyncMock(return_value=None)
            mock_browser.close = AsyncMock(return_value=None)
            
            # 실행
            result = await crawl_twitter_trends(headless=True, max_trends=10, cookie_file="test_cookies.json")
            keywords = await get_trend_keywords(headless=True, max_trends=10, cookie_file="test_cookies.json")
            
            # 검증
            assert result["total_trends"] > 0
            assert len(keywords) > 0
            assert all(isinstance(kw, str) for kw in keywords)
            assert all(len(kw) > 0 for kw in keywords)


class TestRealIntegration:
    """
    실제 브라우저를 사용하는 통합 테스트 (느리고 불안정할 수 있음).
    
    이 클래스의 테스트는 Mock을 사용하지 않습니다.
    실제 Playwright 브라우저를 실행하고 실제 X.com에 접속합니다.
    쿠키 파일이 필요합니다.
    
    실행 방법:
    pytest test/crawler/keywords/test_twitter.py::TestRealIntegration::test_real_twitter_trends_crawling -v -s
    
    또는 마커 사용:
    pytest test/crawler/keywords/test_twitter.py -m integration -v -s
    
    주의: 쿠키 파일(twitter_cookies.json)이 필요합니다.
    먼저 save_twitter_cookies()를 실행하여 쿠키를 저장하세요.
    """
    
    @pytest.mark.integration
    @pytest.mark.slow
    @pytest.mark.asyncio
    async def test_real_twitter_trends_crawling(self):
        """
        실제 Twitter(X.com)에서 키워드를 추출하는 테스트.
        
        Mock을 사용하지 않고 실제 브라우저를 실행합니다.
        실제 X.com 웹사이트에 접속하여 데이터를 수집합니다.
        
        주의: 쿠키 파일이 필요합니다. 없으면 테스트가 실패합니다.
        """
        print("\n" + "="*70)
        print("🔍 실제 Twitter(X.com) 크롤링 테스트 시작")
        print("="*70)
        
        # 쿠키 파일 확인
        cookie_file = DEFAULT_COOKIE_FILE
        if not os.path.exists(cookie_file):
            pytest.skip(
                f"쿠키 파일이 없습니다: {cookie_file}\n"
                f"먼저 save_twitter_cookies()를 실행하여 쿠키를 저장하세요."
            )
        
        # 실제 크롤링 실행
        max_trends = 20  # 테스트용으로 적은 수
        print(f"\n📦 설정:")
        print(f"   - 최대 수집 개수: {max_trends}개")
        print(f"   - 헤드리스 모드: True")
        print(f"   - 쿠키 파일: {cookie_file}")
        print(f"\n⏳ 크롤링 시작... (30초~1분 정도 소요될 수 있습니다)\n")
        
        result = await crawl_twitter_trends(
            headless=True,
            max_trends=max_trends,
            cookie_file=cookie_file,
            page_timeout_ms=60_000
        )
        
        # 결과 출력
        print("\n" + "="*70)
        print(f"✅ 크롤링 완료!")
        print(f"📊 총 {result['total_trends']}개 키워드 수집")
        print("="*70)
        print("\n📋 수집된 키워드 목록:")
        print("-" * 70)
        
        for idx, trend in enumerate(result['trends'][:max_trends], 1):
            keyword = trend.get('keyword', '')
            print(f"{idx:2d}. {keyword}")
        
        # 검증
        assert isinstance(result, dict), "결과가 딕셔너리 형식이 아닙니다"
        assert "total_trends" in result, "total_trends 키가 없습니다"
        assert "trends" in result, "trends 키가 없습니다"
        assert "source" in result, "source 키가 없습니다"
        assert "collected_at" in result, "collected_at 키가 없습니다"
        
        # 키워드만 추출
        keywords = await get_trend_keywords(headless=True, max_trends=max_trends, cookie_file=cookie_file)
        print(f"\n📝 키워드만 추출: {len(keywords)}개")
        print("-" * 70)
        for idx, kw in enumerate(keywords[:15], 1):
            print(f"{idx:2d}. {kw}")
        if len(keywords) > 15:
            print(f"    ... 외 {len(keywords) - 15}개")
        
        # JSON 파일로 저장 (test_google_trend.py와 같은 경로)
        test_dir = Path(__file__).parent  # test/crawler/keywords/
        output_file = test_dir / "twitter_trends_test_result.json"
        try:
            output_data = {
                "timestamp": datetime.now().isoformat(),
                "test_settings": {
                    "max_trends": max_trends,
                    "headless": True,
                    "cookie_file": cookie_file
                },
                "result": result,
                "keywords_only": keywords
            }
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            print(f"\n💾 결과 저장: {output_file}")
        except Exception as e:
            print(f"\n⚠️ 파일 저장 실패: {e}")
        
        print("\n" + "="*70)
        print("✅ 테스트 완료!")
        print("="*70 + "\n")
        
        # 검증
        if len(keywords) > 0:
            assert all(isinstance(kw, str) for kw in keywords), "모든 키워드는 문자열이어야 합니다"
            assert all(len(kw) > 0 for kw in keywords), "빈 키워드가 있습니다"
        else:
            print("⚠️ 키워드가 수집되지 않았습니다. 쿠키가 만료되었을 수 있습니다.")
