from langchain_openai import ChatOpenAI
from langchain.schema import SystemMessage, HumanMessage


def get_llm(api_key: str):
    return ChatOpenAI(
        model="gpt-4o",
        api_key=api_key,
        # reasoning_effort="low",
        # verbosity="low"
    )


async def call_llm(api_key, system_prompt, input_prompt):
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=input_prompt),
    ]

    result = await get_llm(api_key=api_key).ainvoke(messages)

    # 결과값의 .content: 출력물
    return result.content.strip()
