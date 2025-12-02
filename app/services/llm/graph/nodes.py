from app.classes.models import GraphState


# 시작 노드
async def entry_node(state: GraphState) -> GraphState:
    # 입력 키워드를 정제하고 없으면 다음 단계에 키워드를 요청한다.
    keyword = (state.get("keyword") or "").strip()
    if not keyword:
        return {"need_keyword": True}
    return {"keyword": keyword, "keywords": [keyword], "need_keyword": False}


# 키워드 없어서 가져오는 노드
async def crawling_keywords_node(state: GraphState) -> GraphState:
    # state.get("target_channel", "")에
    # x가 포함되어있다면 x에서 키워드 가져오기
    # i가 포함되어있다면 instagram에서 해시태그 가져오기
    # g가 포함되어있다면 google trend에서 크롤링

    # TODO: 예시 결과입니다. 실제 로직으로 수정 필요
    # keywords = ["평택대", "bangladesh vs ireland", "나경원", "중앙대학교", "강백호", "메이플", "조달청", "국립중앙박물관", "마이애미 대 골든 스테이트", "한국장학재단"]
    # return {"keywords": keywords}
    return


async def make_keyword_node(state: GraphState) -> GraphState:
    # 배열을 주고, 해당 배열 중 하나를 선택하고, 출력물로 하나의 품목을 검색하기 위한 키워드를 뱉음
    # LLM이 키워드를 정할 예정
    keyword = "캐릭터 볼펜"
    return {"keyword": keyword}


async def get_keyword_node(state: GraphState) -> GraphState:
    # keywords = state.get("keywords") or [""]

    # # TODO: 랜덤으로 하나 뽑기. 나중에 수정하고싶으면 상의하세요
    # keyword = keywords[random.randrange(0, len(keywords))]
    # return {"keyword": keyword}
    return


async def crawling_items_ssadagu_node(state: GraphState) -> GraphState:
    # 싸다구 몰에서 아이템 크롤링
    # TODO: 예시 결과입니다. 실제 로직으로 수정 필요
    # result = [
    #   {
    #     "title": "2025 새로운 국경 스마트 폰 I16PROMax 안드로이드 전화 AliExpress 핫 세일 새로운 공장 도매",
    #     "price": "41800",
    #     "product_link": "https://ssadagu.kr/shop/view.php?platform=1688&num_iid=901876889270&ss_tx=스마트폰",
    #     "thumbnail_url": "https://cbu01.alicdn.com/img/ibank/O1CN01Kkep2t2MGSUYrhH3X_!!2217178229800-0-cib.jpg",
    #     "sales_count": "0"
    #   },
    # ]
    # return {"products": {**state.get("products", {}), "ssadagu":result}}
    return


async def crawling_items_coupang_node(state: GraphState) -> GraphState:
    # 쿠팡에서 크롤링
    # TODO: 예시 결과입니다. 실제 로직으로 수정 필요
    # 크롤링 테스트가 나오면 예시도 수정이 필요합니다.
    # result = [
    #   {
    #     "title": "2025 새로운 국경 스마트 폰 I16PROMax 안드로이드 전화 AliExpress 핫 세일 새로운 공장 도매",
    #     "price": "41800",
    #     "product_link": "https://ssadagu.kr/shop/view.php?platform=1688&num_iid=901876889270&ss_tx=스마트폰",
    #     "thumbnail_url": "https://cbu01.alicdn.com/img/ibank/O1CN01Kkep2t2MGSUYrhH3X_!!2217178229800-0-cib.jpg",
    #     "sales_count": "0"
    #   },
    # ]
    # return {"products": {**state.get("products", {}), "coupang":result}}
    return


async def filter_strange_node(state: GraphState) -> GraphState:
    # products = state.get("products") or {}
    # # products가 비어있다면?
    # # 이거 무슨 동작이지..?
    # if not products:
    #   products = {
    #     key: value
    #     for key, value in state.items()
    #     if isinstance(value, list)
    #     and value
    #     and isinstance(value[0], dict)
    #     and "title" in value[0]
    #   }

    # keyword = state.get("keyword")
    # if not products:
    #   return {"products": {}, "filtered_products": [], "need_more_products": True}

    # semaphore = asyncio.Semaphore(queue_size)

    # async def filter_strange(product, keyword) -> dict:
    #   async with semaphore:
    #     # LLM에게 질문, 해당 제품이 키워드와 연관이 충분히 있는가?
    #       # 없으면 빈 칸 출력
    #       # 있으면 그대로 출력
    #     return product

    # async def run_filter(mall_name: str, product: dict):
    #   result = await filter_strange(product, keyword)
    #   return mall_name, result

    # tasks = [
    #   run_filter(mall_name, product)
    #   for mall_name, mall_products in products.items()
    #   for product in mall_products
    # ]
    # if not tasks:
    #   return {"products": {}, "filtered_products": [], "need_more_products": True}

    # filtered_products: dict[str, list[dict]] = {}
    # for mall_name, product in await asyncio.gather(*tasks):
    #   if not product:
    #     continue
    #   filtered_products.setdefault(mall_name, []).append(product)

    # filtered_products = {
    #   mall: items
    #   for mall, items in filtered_products.items()
    #   if items
    # }
    # expected_malls = {"ssadagu", "coupang"}
    # need_more = any(mall not in filtered_products for mall in expected_malls)
    # return {
    #   "products": filtered_products,
    #   "filtered_products": [
    #     {"mall": mall, "items": items}
    #     for mall, items in filtered_products.items()
    #   ],
    #   "need_more_products": need_more
    # }
    return


async def product_check(state: GraphState) -> GraphState:
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
    # return {"need_retry": False}
    return


async def job_failed(state: GraphState) -> GraphState:
    return {"failed": True}


async def generate_ads(state: GraphState) -> GraphState:
    # # TODO: 설정 갖고 각 플랫폼의 성격에 맞게 LLM이 글 쓰기
    # # 이건 그냥 if 문으로 순회해도 될 듯? 어짜피 값을 요구하는게 아니라 로직 돌고 있다고 나중에 통보만 할거라
    # content1={
    #   "title": "블로그 제목",
    #   "content": "블로그 내용",
    #   "tags": ["#해시", "#태그들"]
    # }
    # content2={
    #   "content": "트윗 내용",
    #   "images": ["이미지 링크. 없으면 빈칸"]
    # }
    # content3={
    #   "content": "쓰레드 내용",
    #   "images": ["이미지 링크. 없으면 빈칸"]
    # }

    # # 실제로는 이렇게 단순하게 보내진 않습니다. 예시 출력이 다음과 같다 이 말입니다.
    # return {
    #   "result": {
    #     "blog": content1,
    #     "x": content2,
    #     "thread": content3
    #   }
    # }
    return


print("define nodes")
