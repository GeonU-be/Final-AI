from app.services.llm.prompt_templates import TEMPLATES
from app.classes.models import ProductInfo, CompareableInfo


# 하나의 플랫폼 프롬프트 생성
def build_prompt(
    platform: str,
    keyword: str,
    tone: str,
    product_info: ProductInfo,
    compareable_info: CompareableInfo,
):
    """
    플랫폼에 따라 템플릿을 선택하고
    템플릿 내부 변수(product_name, keyword, tone)를 채워
    LLM에게 전달할 프롬프트를 생성하는 함수.

    입력(state):
      - product_name
      - keyword
      - tone
      - platform (naver / twitter)

    출력:
      { "prompt": "<LLM에 전달할 최종 프롬프트>" }
    """

    # platform 값 읽기
    # platform = state["platform"]

    # 플랫폼에 맞는 템플릿 선택
    template = TEMPLATES.get(platform)

    # 템플릿이 없으면 예외 처리
    if not template:
        raise ValueError(f"지원하지 않는 플랫폼: {platform}")

    # 템플릿 내부 변수 치환
    prompt = template.format(
        keyword=keyword,
        tone=tone,
        product_name=product_info.name,
        product_link=product_info.link,
        product_price=product_info.price,
        product_thumbnail=product_info.thumbnail_url,
        product_details=product_info.detail_specs,
        compareable_name=compareable_info.name,
        compareable_price=compareable_info.price,
        compareable_thumbnail=compareable_info.thumbnail_url,
    )

    # 다음 LangGraph 노드로 전달할 데이터
    return {"prompt": prompt}
