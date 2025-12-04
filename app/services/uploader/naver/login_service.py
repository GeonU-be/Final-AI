import asyncio
from playwright.async_api import async_playwright
import os

LOGIN_URL = "https://nid.naver.com/nidlogin.login"


# --------------------------------------------
# ① 세션 파일이 비어 있는지 확인하고 필요하면 삭제
# --------------------------------------------
async def is_session_file_empty(session_file: str) -> bool:
    """
    기능:
        - 세션 파일이 존재하지만 크기가 0이면 삭제한다.
        - 잘못된 세션 파일로 인해 로그인 오류를 방지하기 위한 전처리 단계.

    반환값:
        - True  → 세션 파일이 비어 있어 삭제한 경우
        - False → 세션 파일이 정상인 경우 또는 파일이 없는 경우
    """
    if os.path.exists(session_file) and os.path.getsize(session_file) == 0:
        os.remove(session_file)
        print("세션 파일이 비어 있어 삭제함")
        return True
    return False


# --------------------------------------------
# ② 기존 세션 상태가 유효한지 검사
# --------------------------------------------
async def validate_existing_session(browser, session_file: str) -> bool:
    """
    기능:
        - 기존 세션 파일(storage_state)을 로드하여 블로그 페이지 접속
        - URL을 확인하여 로그인 상태인지 판단한다.

    반환값:
        - True  → 이미 로그인 된 상태 → 로그인 생략 가능
        - False → 세션 만료 또는 로그인 필요
    """
    if not os.path.exists(session_file):
        return False

    print("기존 세션 파일 발견 → 세션 유효성 검사 중...")

    context = await browser.new_context(storage_state=session_file)
    page = await context.new_page()

    await page.goto("https://blog.naver.com", timeout=30000)

    # URL에 로그인 페이지가 없으면 로그인 성공 상태
    if "nidlogin.login" not in page.url:
        print("세션 유효 → 로그인 생략")
        return True

    print("세션 만료 → 신규 로그인 필요")
    return False


# --------------------------------------------
# ③ 신규 로그인 수행 후 세션 파일 저장
# --------------------------------------------
async def perform_new_login(browser, login_id: str, login_pw: str, session_file: str) -> bool:
    """
    기능:
        - 네이버 로그인 페이지 접속
        - 아이디/비밀번호 입력 후 로그인 버튼 클릭
        - 정상 로그인 시 새로운 storage_state를 파일에 저장

    반환값:
        - True → 로그인 성공 & 세션 저장 완료
        - False → 로그인 중 오류 발생
    """

    print("신규 로그인 시도 중...")

    context = await browser.new_context()
    page = await context.new_page()

    await page.goto(LOGIN_URL, timeout=30000)
    await page.fill("#id", login_id)
    await page.fill("#pw", login_pw)
    await page.click("button[type=submit]")

    # 로그인 완료되는 순간 URL이 로그인 페이지에서 벗어남
    await page.wait_for_url(lambda url: "nidlogin.login" in url, timeout=10000)

    # 저장
    await context.storage_state(path=session_file)
    print("신규 로그인 성공 → 세션 저장 완료")
    return True


# --------------------------------------------
# 자동 로그인 로직 전체 통합
# --------------------------------------------
async def naver_auto_login(login_id: str, login_pw: str, session_file: str) -> bool:
    """
    기능:
        - 기존 세션 파일 처리
        - 세션 유효성 검사
        - 필요 시 신규 로그인 수행

    반환값:
        - True  → 로그인 성공(기존 세션 또는 신규 로그인)
        - False → 로그인 실패 또는 Playwright 오류
    """

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=120)

        try:
            # Step 1. 비어 있는 세션 파일 삭제
            await is_session_file_empty(session_file)

            # Step 2. 기존 세션 검사
            if await validate_existing_session(browser, session_file):
                return True

            # Step 3. 신규 로그인 진행
            success = await perform_new_login(browser, login_id, login_pw, session_file)
            return success

        except Exception as e:
            print(f"[자동 로그인 오류] {e}")
            return False

        finally:
            await browser.close()