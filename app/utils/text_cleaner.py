import json
import re


def try_repair_json(raw: str):
    fixed = raw.strip()

    # 마크다운 제거
    fixed = re.sub(r"```json\s*", "", fixed, flags=re.IGNORECASE)
    fixed = fixed.replace("```", "")

    # 따옴표 짝 맞추기
    quote_count = len(re.findall(r'"', fixed))
    if quote_count % 2 != 0:
        fixed += '"'

    # 괄호 스택 기반 보정
    stack = []
    for char in fixed:
        if char in ["{", "["]:
            stack.append(char)
        elif char == "}" and stack and stack[-1] == "{":
            stack.pop()
        elif char == "]" and stack and stack[-1] == "[":
            stack.pop()

    # 스택에 남은 것들 역순으로 닫기
    while stack:
        open_bracket = stack.pop()
        if open_bracket == "{":
            fixed += "}"
        elif open_bracket == "[":
            fixed += "]"

    # 쉼표 제거
    fixed = re.sub(r",\s*$", "", fixed)

    # JSON 검증
    try:
        json.loads(fixed)
        return fixed
    except json.JSONDecodeError:
        return None
