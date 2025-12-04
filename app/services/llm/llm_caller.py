# app/services/llm/callers/llm_caller.py

import os
import requests

API_KEY = os.getenv("UPSTAGE_API_KEY")
if not API_KEY:
    raise ValueError("환경 변수 UPSTAGE_API_KEY가 설정되지 않았습니다.")

def call_llm(state: dict) -> dict[str, str]:
    """
    prompt_builder에서 생성한 prompt를 받아
    Upstage Solar-Pro API에 요청을 보내고
    LLM이 생성한 텍스트를 반환하는 함수.

    입력(state):
      - prompt: LLM에게 전달할 문자열

    출력:
      { "generated_content": "<LLM이 생성한 텍스트>" }
    """

    prompt = state["prompt"]

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }

    data = {
        "model": "solar-pro",
        "messages": [{"role": "user", "content": prompt}]
    }

    res = requests.post(
        "https://api.upstage.ai/v1/chat/completions",
        headers=headers, json=data, timeout=60
    )

    # HTTP 오류 시 예외 발생
    res.raise_for_status()

    result = res.json()

    try:
        text = result["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as e:
        raise ValueError(f"예상치 못한 API 응답 형식: {result}") from e

    return {"generated_content": text}