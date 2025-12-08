
def postprocess(state: dict) -> dict[str, str]:
    """
    플랫폼별로 LLM의 결과물을 최종 업로드 가능한 형태로 정리.

    입력(state):
      - generated_content: LLM이 생성한 텍스트
      - platform: naver / twitter

    출력:
      { "final_content": "<가공된 최종 텍스트>" }
    """

    txt = state["generated_content"]
    platform = state["platform"]

    # 네이버: HTML 태그 기반 줄바꿈 보정
    if platform == "naver":
        txt = txt.replace("\n\n", "<br><br>")

    # 트위터: 줄바꿈 제거 후 한 문단 형태로 변환
    elif platform == "twitter":
        txt = txt.replace("\n", " ").strip()

    return {"final_content": txt}


