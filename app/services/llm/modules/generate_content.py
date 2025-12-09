# 글을 생성하는 파트입니다.
from app.services.llm.prompts.generate_content_prompt import (
    gc_system_prompt,
    INFORMATIONS,
)
from app.classes.models import ProductInfo, CompareableInfo, LlmSettings
from app.services.llm.openai_llm import call_llm


async def generate_content(
    platform: str,
    keyword: str,
    tone: str,
    product_info: ProductInfo,
    compareable_info: CompareableInfo,
    llm_settings: LlmSettings,
):
    system_prompt = gc_system_prompt(platform=platform)
    input_prompt = INFORMATIONS.format(
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

    return await call_llm(
        api_key=llm_settings.apiKey,
        system_prompt=system_prompt,
        input_prompt=input_prompt,
    )
