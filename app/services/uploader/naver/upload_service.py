from playwright.async_api import async_playwright
import asyncio


# ---------------------------------------------------------
# ① 글쓰기 페이지 오픈
# ---------------------------------------------------------
async def open_editor_page(browser, BLOG_ID, session_file):
    """
    기능:
        - 저장된 세션을 이용하여 네이버 블로그 글쓰기 페이지로 이동한다.
        - mainFrame 로딩까지 포함.

    입력:
        browser: launch된 playwright browser 객체
        BLOG_ID: 네이버 블로그 ID
        session_file: 세션 파일 경로

    반환:
        frame: mainFrame 객체 (이후 모든 입력은 frame 기준으로 이루어짐)
    """
    context = await browser.new_context(storage_state=session_file)
    page = await context.new_page()

    await page.goto(
        f"https://blog.naver.com/{BLOG_ID}?Redirect=Write&",
        timeout=30000
    )

    await page.wait_for_selector("iframe[name='mainFrame']")
    frame = page.frame(name="mainFrame")

    return frame, page


# ---------------------------------------------------------
# ② 기존 작성 팝업 닫기
# ---------------------------------------------------------
async def close_existing_popup(frame):
    """
    기능:
        - '기존 작성 팝업'이 나타난 경우 취소 버튼을 누른다.

    입력:
        frame: mainFrame 객체

    반환:
        bool → 팝업이 존재해 닫았으면 True, 없으면 False
    """
    try:
        await frame.wait_for_selector("button.se-popup-button-cancel", timeout=2500)
        await frame.click("button.se-popup-button-cancel", force=True)
        return True
    except Exception:
        return False


# ---------------------------------------------------------
# ③ 도움말 패널 닫기
# ---------------------------------------------------------
async def close_help_panel(frame):
    """
    기능:
        - 글쓰기 페이지에서 자동으로 나타나는 도움말 패널을 닫는다.

    반환:
        bool → 닫았으면 True / 없어서 못 닫았으면 False
    """
    try:
        await frame.wait_for_selector("button.se-help-panel-close-button", timeout=2500)
        await frame.click("button.se-help-panel-close-button", force=True)
        return True
    except Exception:
        return False


# ---------------------------------------------------------
# ④ 제목 입력
# ---------------------------------------------------------
async def fill_title(frame, title):
    """
    기능:
        - 제목 입력 영역 클릭 후 title 텍스트를 입력한다.

    반환:
        bool → 입력 성공 여부
    """
    try:
        await frame.wait_for_selector("p.se-text-paragraph span.se-placeholder")
        await frame.click("p.se-text-paragraph span.se-placeholder")
        await frame.type("p.se-text-paragraph", title)
        return True
    except Exception:
        return False


# ---------------------------------------------------------
# ⑤ 본문 입력
# ---------------------------------------------------------
async def fill_content(frame, content):
    """
    기능:
        - 본문 영역 클릭 후 content 텍스트 입력.

    반환:
        bool → 입력 성공 여부
    """
    try:
        await frame.wait_for_selector(
            "div.se-module-text p.se-text-paragraph span.se-placeholder",
            timeout=5000
        )
        await frame.click(
            "div.se-module-text p.se-text-paragraph span.se-placeholder"
        )
        await frame.type("div.se-module-text p.se-text-paragraph", content)
        return True
    except Exception:
        return False


# ---------------------------------------------------------
# ⑥ 발행 버튼 (1단계)
# ---------------------------------------------------------
async def publish_first_step(frame):
    """
    기능:
        - '발행' 첫 번째 버튼 클릭

    반환:
        bool → 클릭 성공 여부
    """
    try:
        await frame.wait_for_selector("button.publish_btn__m9KHH", timeout=5000)
        await frame.click("button.publish_btn__m9KHH")
        return True
    except Exception:
        return False


# ---------------------------------------------------------
# ⑦ 최종 발행 버튼 (2단계)
# ---------------------------------------------------------
async def publish_final_step(frame):
    """
    기능:
        - '최종 발행 버튼' 클릭

    반환:
        bool → 클릭 성공 여부
    """
    try:
        await frame.wait_for_selector(
            "button[data-testid='seOnePublishBtn']",
            timeout=5000
        )
        await frame.click("button[data-testid='seOnePublishBtn']")
        return True
    except Exception:
        return False


# ---------------------------------------------------------
# ⑧ 전체 게시글 업로드 Orchestrator
# ---------------------------------------------------------
async def naver_publish_workflow(BLOG_ID, title, content, session_file):
    """
    기능:
        - 네이버 블로그 글쓰기 페이지 오픈부터 발행까지 전체 수행하는 워크플로우.
        - LangGraph에서 한 노드로 사용하거나 세분화된 노드로 연결할 수 있음.

    반환:
        dict:
            {
                "success": bool,
                "message": str
            }
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)

        try:
            frame, page = await open_editor_page(browser, BLOG_ID, session_file)

            await close_existing_popup(frame)
            await close_help_panel(frame)

            if not await fill_title(frame, title):
                return {"success": False, "message": "제목 입력 실패"}

            if not await fill_content(frame, content):
                return {"success": False, "message": "본문 입력 실패"}

            if not await publish_first_step(frame):
                return {"success": False, "message": "발행 1단계 실패"}

            if not await publish_final_step(frame):
                return {"success": False, "message": "발행 2단계 실패"}

            # 발행 완료 URL 확인
            await page.wait_for_url(lambda url: "/PostView.naver" in url, timeout=10000)

            return {"success": True, "message": "게시물 발행 완료"}

        except Exception as e:
            return {"success": False, "message": f"오류 발생: {e}"}

        finally:
            await browser.close()