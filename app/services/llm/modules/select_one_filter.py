from app.services.llm.prompts.select_one_prompt import se_input_prompt, se_system_prompt
from app.classes.models import LlmSettings
from app.services.llm.openai_llm import call_llm


async def select_one(arrs: list[str], llm_settings: LlmSettings):
    system_prompt = se_system_prompt
    input_prompt = se_input_prompt(arrs=arrs)
    # model = llm_settings.model

    return await call_llm(
        api_key=llm_settings.apiKey,
        system_prompt=system_prompt,
        input_prompt=input_prompt,
    )


print("define select_one_filter")
