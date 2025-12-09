import requests
import asyncio
from app.config import JAVA_SERVER_ADDRESS
from app.services.uploader.naver.login_service import naver_auto_login
from app.services.uploader.naver.upload_service import naver_publish_workflow


# ---------------------------------------------------------
# ① 자동 로그인 수행
# ---------------------------------------------------------
async def workflow_login_step(login_id, login_pw, session_file):
    """
    기능:
        - auto_login() 기능을 workflow-friendly 형태로 래핑한 노드.
        - 세션 파일 검사 → 기존 세션 검증 → 신규 로그인까지 포함.

    입력:
        login_id: 네이버 ID
        login_pw: 네이버 PW
        session_file: 세션 저장 파일 경로

    반환(dict):
        {
            "success": bool,     # 로그인 성공 여부
            "message": str       # 성공/실패 메시지
        }
    """
    success = await naver_auto_login(login_id, login_pw, session_file)

    if success:
        return {"success": True, "message": "로그인 성공"}
    else:
        return {"success": False, "message": "로그인 실패"}


# ---------------------------------------------------------
# ② 자동 업로드 수행
# ---------------------------------------------------------
async def workflow_upload_step(BLOG_ID, title, content, session_file):
    """
    기능:
        - naver_publish_workflow() 기능을 노드 형태로 래핑.
        - 글쓰기 페이지 이동 → 팝업 닫기 → 제목/본문 입력 → 발행까지 수행.

    입력:
        BLOG_ID: 네이버 블로그 ID
        title: 게시글 제목
        content: 게시글 내용
        session_file: 로그인 세션 파일

    반환(dict):
        {
            "success": bool,       # 업로드 성공 여부
            "message": str         # 상세 결과 메시지
        }
    """
    result = await naver_publish_workflow(BLOG_ID, title, content, session_file)
    return result


# ---------------------------------------------------------
# ③ 전체 자동 로그인 + 자동 업로드 통합 Workflow (Orchestrator)
# ---------------------------------------------------------
async def run_login_upload_workflow(
    login_id, login_pw, session_file, BLOG_ID, title, content, jobId, max_retries=3
):
    """
    기능:
        - 자동 로그인 실행
        - 로그인 성공하면 자동 업로드 실행
        - 업로드 실패 시 설정한 횟수만큼 재시도
        - LangGraph의 최종 node 또는 router에서 직접 실행하기 적합한 오케스트레이터

    입력:
        login_id: 네이버 ID
        login_pw: 네이버 PW
        session_file: 세션 파일
        BLOG_ID: 블로그 ID
        title: 업로드 제목
        content: 업로드 본문
        max_retries: 업로드 실패 시 재시도 횟수

    반환(dict):
        {
            "success": bool,           # 전체 프로세스 성공 여부
            "message": str,            # 결과 메시지
            "attempts": int            # 업로드 시도 횟수
        }
    """

    # STEP 1. 로그인
    login_result = await workflow_login_step(login_id, login_pw, session_file)

    if not login_result["success"]:
        print("login failed")
        return {
            "success": False,
            "message": f"로그인 단계 실패 → {login_result['message']}",
            "attempts": 0,
        }

    print("login successed")
    # STEP 2. 업로드 (재시도 포함)
    for attempt in range(1, max_retries + 1):
        print("uploaded attempt: ", attempt)
        upload_result = await workflow_upload_step(
            BLOG_ID, title, content, session_file
        )

        if upload_result["success"]:
            requests.patch(
                url=JAVA_SERVER_ADDRESS,
                data={"jobId": jobId, "url": upload_result["message"].split(",")[1]},
                timeout=10000,
            )
            return {
                "success": True,
                "message": "전체 자동 업로드 프로세스 성공",
                "url": upload_result["message"].split(",")[1],
                "attempts": attempt,
            }

        # 실패한 경우 재시도
        if attempt < max_retries:
            await asyncio.sleep(3)

    # 모든 재시도 실패
    print("workflow was failed!")
    raise Exception("Naver Uploading workflow was failed.")
    # return {
    #     "success": False,
    #     "message": "모든 업로드 시도 실패",
    #     "attempts": max_retries,
    # }
