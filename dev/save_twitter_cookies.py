"""
Twitter(X.com) 쿠키 저장 스크립트.

이 스크립트를 실행하면 브라우저가 열리고 X.com 로그인 페이지가 표시됩니다.
수동으로 로그인을 완료하면 쿠키가 자동으로 저장됩니다.

사용법:
    python dev/save_twitter_cookies.py

쿠키 파일은 프로젝트 루트에 `twitter_cookies.json`으로 저장됩니다.
"""

import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.services.crawler.keywords.twitter_crawler import save_twitter_cookies, DEFAULT_COOKIE_FILE

if __name__ == "__main__":
    print("=" * 70)
    print("🔐 Twitter(X.com) 쿠키 저장 스크립트")
    print("=" * 70)
    print("\n📝 다음 단계를 따라주세요:")
    print("   1. 브라우저가 열리면 X.com 로그인 페이지가 표시됩니다")
    print("   2. 수동으로 로그인을 완료하세요")
    print("   3. 로그인이 완료되면 자동으로 쿠키가 저장됩니다")
    print("   4. 최대 5분까지 대기합니다")
    print(f"\n💾 쿠키 파일 위치: {project_root / DEFAULT_COOKIE_FILE}")
    print("=" * 70 + "\n")
    
    # 쿠키 저장 (headless=False로 브라우저 표시)
    success = save_twitter_cookies(
        cookie_file=str(project_root / DEFAULT_COOKIE_FILE),
        headless=False  # 브라우저를 표시하여 로그인 가능
    )
    
    if success:
        print("\n" + "=" * 70)
        print("✅ 쿠키 저장 완료!")
        print(f"📁 파일 위치: {project_root / DEFAULT_COOKIE_FILE}")
        print("=" * 70)
        print("\n이제 통합 테스트를 실행할 수 있습니다:")
        print("pytest test/crawler/keywords/test_twitter.py -m integration -v -s")
    else:
        print("\n" + "=" * 70)
        print("❌ 쿠키 저장 실패")
        print("=" * 70)
        print("\n다음 사항을 확인해주세요:")
        print("   1. 로그인이 정상적으로 완료되었는지")
        print("   2. 브라우저가 정상적으로 열렸는지")
        print("   3. 네트워크 연결이 정상인지")
        print("\n다시 시도해주세요.")

