# app/services/llm/callers/llm_caller.py

import os
import requests

API_KEY = os.getenv("UPSTAGE_API_KEY")

def call_llm(state):
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
        headers=headers, json=data
    )

    result = res.json()
    text = result["choices"][0]["message"]["content"]

    return {"generated_content": text}