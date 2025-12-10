from app.classes.models import LlmSettings
from app.services.llm.openai_llm import call_llm


async def generate_title(content: str, llm_settings: LlmSettings) -> str:
    return await call_llm(
        api_key=llm_settings.apiKey,
        system_prompt="""
    당신은 탁월한 네이버 블로그 제목 작성자입니다.
    제공되는 글을 보고 네이버 블로그의 제목을 작성해주십시오.

    출력은 평문 한 줄로 작성하십시오.
    """,
        input_prompt=content,
    )
