from app.classes.models import LlmSettings
from app.services.llm.prompts.filter_wrong_prompt import (
    fw_system_prompt,
    fw_input_prompt,
)
from app.services.llm.openai_llm import call_llm


async def filter_wrong(keyword: str, product: dict, llm_settings: LlmSettings):
    system_prompt = fw_system_prompt
    input_prompt = fw_input_prompt(keyword=keyword, product=product)
    return await call_llm(
        api_key=llm_settings.apiKey,
        system_prompt=system_prompt,
        input_prompt=input_prompt,
    )


print("define filter_wrong_products")
