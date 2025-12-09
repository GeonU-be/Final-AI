import random
import asyncio
import json
import os
import re
import requests

from langsmith import traceable

from app.classes.models import GraphState
from app.logs import log_info, log_warn, log_error

from app.services.llm.modules import filter_wrong, select_one
from app.utils.text_cleaner import try_repair_json

# 키워드 크롤러
from app.services.crawler.keywords.google_trend import (
    get_trend_keywords as get_google_trends,
)

# from app.services.crawler.keywords.twitter_crawler import get_trend_keywords as get_twitter_trends

# 상품 크롤러
from app.services.crawler.products.ssadagu_crawler import crawl_ssadagu_products
from app.services.crawler.products.coupang_crawler import crawl_coupang_products

from app.services.llm.modules.generate_content import generate_content
from app.services.llm.modules.generate_title import generate_title

from app.services.uploader.naver.workflow import (
    run_login_upload_workflow as naver_uploader,
)

from app.config import NAVER_ID, NAVER_PW, SESSION_FILE_DIR, JAVA_SERVER_ADDRESS

QUEUE_SIZE = 10


# 시작 노드
@traceable
async def entry_node(state: GraphState) -> GraphState:
    # 입력 키워드를 정제하고 없으면 다음 단계에 키워드를 요청한다.
    log_info("프로세스 시작 ", job_id=state["jobId"])
    keyword = (state.get("keyword") or "").strip()
    if not keyword:
        log_info("키워드 없음. 랜덤 키워드 추출 시도")
        return {"need_keyword": True}
    return {"keyword": keyword, "keywords": [keyword], "need_keyword": False}


# 키워드 없어서 가져오는 노드
@traceable
async def crawling_keywords_node(state: GraphState) -> GraphState:
    log_info("트렌드 키워드 크롤링 시작", job_id=state["jobId"])

    keywords: list[str] = []

    # Google Trends에서 키워드 수집
    try:
        log_info("Google Trends 키워드 수집 중...", job_id=state["jobId"])
        google_keywords = await get_google_trends(headless=True, max_trends=30)
        keywords.extend(google_keywords)
        log_info(
            f"Google Trends: {len(google_keywords)}개 키워드 수집",
            job_id=state["jobId"],
        )
    except Exception as e:
        log_warn(
            message="Google Trends 크롤링 실패",
            job_id=state["jobId"],
            submessage=str(e),
            logged_process="crawling_keywords",
        )

    # Twitter(X.com)에서 키워드 수집 (쿠키 파일 필요)
    # 주석 처리: 다른 소스로 대체 가능
    # twitter_cookie_file = "twitter_cookies.json"
    # if os.path.exists(twitter_cookie_file):
    #     try:
    #         log_info("Twitter 트렌드 키워드 수집 중...", job_id=state["jobId"])
    #         twitter_keywords = await get_twitter_trends(
    #             headless=True,
    #             max_trends=20,
    #             cookie_file=twitter_cookie_file,
    #         )
    #         keywords.extend(twitter_keywords)
    #         log_info(f"Twitter: {len(twitter_keywords)}개 키워드 수집", job_id=state["jobId"])
    #     except Exception as e:
    #         log_warn(
    #             message="Twitter 크롤링 실패",
    #             job_id=state["jobId"],
    #             submessage=str(e),
    #             logged_process="crawling_keywords",
    #         )
    # else:
    #     log_warn(
    #         message="Twitter 쿠키 파일 없음 - Twitter 트렌드 스킵",
    #         job_id=state["jobId"],
    #         submessage=f"쿠키 파일 경로: {twitter_cookie_file}",
    #         logged_process="crawling_keywords",
    #     )

    # 중복 제거
    keywords = list(dict.fromkeys(keywords))

    if not keywords:
        log_warn(
            message="수집된 키워드가 없습니다. 기본 키워드 사용",
            job_id=state["jobId"],
            logged_process="crawling_keywords",
        )
        keywords = ["스마트폰", "노트북", "무선이어폰"]

    log_info(f"총 {len(keywords)}개 키워드 수집 완료", job_id=state["jobId"])
    return {"keywords": keywords}


@traceable
async def make_keyword_node(state: GraphState) -> GraphState:
    # 배열을 주고, 해당 배열 중 하나를 선택하고, 출력물로 하나의 품목을 검색하기 위한 키워드를 뱉음
    # LLM이 키워드를 정할 예정
    log_info("키워드 선택", job_id=state["jobId"])

    result = json.loads(await select_one(state.get("keywords", []), state["settings"]))
    keyword = result["real_keyword"]

    log_info(
        message=f"키워드 선택됨: {result['selected']} / 실제로 검색에 사용될 단어: {result['real_keyword']}",
        submessage=result["reason"],
        job_id=state["jobId"],
    )
    return {"keyword": keyword}


@traceable
async def keyword_join_node(state: GraphState) -> GraphState:
    log_info("키워드 도착", job_id=state["jobId"])
    # 그냥 모이는 노드
    keywords = state.get("keywords") or [""]
    if state.get("keyword", None) is None:
        return {"keyword": keywords[random.randrange(0, len(keywords))]}

    return {"keyword": state.get("keyword")}


@traceable
async def crawling_items_ssadagu_node(state: GraphState) -> GraphState:
    log_info("상품 크롤링 중 - ssadagu.kr", job_id=state["jobId"])

    keyword = state.get("keyword", "")
    if not keyword:
        log_warn(
            message="검색 키워드가 없습니다",
            job_id=state["jobId"],
            logged_process="crawling_ssadagu",
        )
        return {"products": {**state.get("products", {}), "ssadagu": []}}

    try:
        log_info(f"싸다구 상품 검색: '{keyword}'", job_id=state["jobId"])
        result = await crawl_ssadagu_products(
            keyword=keyword,
            max_products=30,
            headless=True,
        )
        log_info(f"싸다구 크롤링 완료: {len(result)}개 상품", job_id=state["jobId"])
    except Exception as e:
        log_warn(
            message="싸다구 크롤링 실패",
            job_id=state["jobId"],
            submessage=str(e),
            logged_process="crawling_ssadagu",
        )
        result = []

    return {"products": {**state.get("products", {}), "ssadagu": result}}


@traceable
async def crawling_items_coupang_node(state: GraphState) -> GraphState:
    log_info("상품 크롤링 중 - coupang.com", job_id=state["jobId"])

    keyword = state.get("keyword", "")
    if not keyword:
        log_warn(
            message="검색 키워드가 없습니다",
            job_id=state["jobId"],
            logged_process="crawling_coupang",
        )
        return {"products": {**state.get("products", {}), "coupang": []}}

    try:
        log_info(f"쿠팡 상품 검색: '{keyword}'", job_id=state["jobId"])
        result = await crawl_coupang_products(
            keyword=keyword,
            max_products=30,
            headless=True,
            fetch_detail_images=True,  # OCR을 위해 상세 이미지 수집
            use_ocr=True,  # OCR 텍스트 추출
            max_ocr_images=5,
        )
        log_info(f"쿠팡 크롤링 완료: {len(result)}개 상품", job_id=state["jobId"])
    except Exception as e:
        log_warn(
            message="쿠팡 크롤링 실패",
            job_id=state["jobId"],
            submessage=str(e),
            logged_process="crawling_coupang",
        )
        result = []

    return {"products": {**state.get("products", {}), "coupang": result}}


@traceable
async def filter_strange_node(state: GraphState) -> GraphState:
    log_info("이상한거 거르는 중", job_id=state["jobId"])
    products = state.get("products") or {}

    keyword = state.get("keyword")
    if not products:
        return {"products": {}, "filtered_products": [], "need_more_products": True}

    semaphore = asyncio.Semaphore(QUEUE_SIZE)

    async def filter_strange(product, keyword) -> dict:
        async with semaphore:
            # LLM에게 질문, 해당 제품이 키워드와 연관이 충분히 있는가?
            # 없으면 빈 칸 출력
            # 있으면 그대로 출력
            ans = await filter_wrong(
                keyword=keyword,
                product=product,
                llm_settings=state["settings"],
            )
            try:
                ans = json.loads(try_repair_json(ans))
                if ans["isRelated"] == "y":
                    return product
                return {}
            except Exception as e:
                log_warn(
                    message="Json 파싱 오류! 해당 상품에 대해서 재질문 합니다..",
                    job_id=state["jobId"],
                    submessage=e,
                    logged_process="Filtering",
                )
                return await filter_strange(product=product, keyword=keyword)

    async def run_filter(mall_name: str, product: dict):
        result = await filter_strange(product, keyword)
        return mall_name, result

    tasks = [
        run_filter(mall_name, product)
        for mall_name, mall_products in products.items()
        for product in mall_products
    ]
    if not tasks:
        return {
            "products": {},
            "filtered_products": [],
            "try_count": state.get("try_count", 0) + 1,
            "need_more_products": True,
        }

    filtered_products: dict[str, list[dict]] = {}
    for mall_name, product in await asyncio.gather(*tasks):
        if not product:
            continue
        filtered_products.setdefault(mall_name, []).append(product)

    filtered_products = {
        mall: items for mall, items in filtered_products.items() if items
    }
    expected_malls = {"ssadagu", "coupang"}
    need_more = any(mall not in filtered_products for mall in expected_malls)
    return {
        "products": filtered_products,
        "filtered_products": [
            {"mall": mall, "items": items} for mall, items in filtered_products.items()
        ],
        "try_count": 0 if not need_more else state.get("try_count", 0) + 1,
        "need_more_products": need_more,
    }


@traceable
async def product_check(state: GraphState) -> GraphState:
    log_info("유사도 검증 중", job_id=state["jobId"])
    # malls = state.get("filtered_products", [])

    # # 만약 malls가 2개 미만이라면? 다시 돌기
    # if len(malls) < 2:
    #   return {
    #     "need_retry": True,
    #     "try_count": state.get("try_count", 0) + 1
    #   }

    # # TODO: 각 검색한 상품들이 유사한가?
    #   # 유사하지 않다면 다시 돌기
    #   # 유사하면 그냥 넘기기
    return {"need_retry": False}


@traceable
async def job_failed(state: GraphState) -> GraphState:
    log_error(
        message="작업을 실패했습니다!",
        job_id=state["jobId"],
        submessage=f"키워드: {state.get('keyword')}",
        logged_process="END",
    )
    return {"failed": True}


@traceable
async def generate_ads(state: GraphState) -> GraphState:
    log_info("글 생성 중", job_id=state["jobId"])
    llmSetting = state.get("settings").llmSettings
    channelSetting = state.get("settings").channelSettings

    product_info = {}
    compareable_info = {}

    title = ""
    content = await generate_content(
        platform=channelSetting.name,
        keyword=state.get("keyword"),
        tone=llmSetting.prompt,
        product_info=product_info,
        compareable_info=compareable_info,
        llm_settings=llmSetting,
    )

    if channelSetting.name == "naver":
        title = await generate_title(content=content, llm_settings=llmSetting)

    post = {"title": title, "content": content}

    def extract_first_https_link(text: str) -> str | None:
        match = re.search(r"https://[^\s)>'\"]+", text)
        return match.group(0) if match else None

    def find_product_by_link(products: dict, link: str) -> dict | None:
        for mall_products in products.values():
            for product in mall_products:
                if product.get("link") == link:
                    return {k: v for k, v in product.items() if k != "category"}
        return None

    products_in_state = state.get("products") or {}
    target_link = extract_first_https_link(content)
    matched_product = (
        find_product_by_link(products_in_state, target_link) if target_link else None
    )

    requests.post(
        url=JAVA_SERVER_ADDRESS,
        headers={"Content-Type": "application/json"},
        json={
            "jobId": state["jobId"],
            "uploadChannelId": channelSetting.id,
            "userId": channelSetting.userId,
            "title": title,
            "body": content,
            "status": "PENDING",
            "generationType": llmSetting.generationType,
            "link": "",
            "keyword": state["keyword"],
            "product": matched_product
            or {
                "title": "string",
                "link": "string",
                "thumbnail": "string",
                "price": 0,
                "category": "string",
            },
        },
        timeout=15000,
    )

    print(post)
    if llmSetting.generationType == "AUTO":
        # TODO: 아이디, 비번 자바에서 제공하도록 변경하기
        if channelSetting.name == "naver":
            await naver_uploader(
                login_id=NAVER_ID,
                login_pw=NAVER_PW,
                session_file=SESSION_FILE_DIR,
                BLOG_ID=NAVER_ID,
                title=title,
                content=content,
                jobId=state["jobId"],
                max_retries=3,
            )
        elif channelSetting.name == "twitter" or "x":
            # 트위터 업로드 로직
            0
    return {"result": post}


print("define nodes")
