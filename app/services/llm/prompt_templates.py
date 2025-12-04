# app/services/llm/prompt_templates.py

# 네이버 블로그용 템플릿
NAVER_TEMPLATE = """
당신은 네이버 블로그 홍보글 전문 카피라이터입니다.
아래 정보로 SEO 최적화된 2000~3000자 HTML 블로그 글을 작성하세요.

[제품 정보]
- 제품명: {product_name}
- 키워드: {keyword}

[작성 규칙]
1. 총 분량은 2000자 이상
2. 서론 → 본문(소제목 5~6개) → 결론 → 해시태그 20개 이상
3. <h3> 태그로 소제목 작성
4. HTML 태그 적극 활용 (<b>, <br>, <ul>, <li>)
5. 문체 톤: {tone}
6. (이미지: 제품 삽입 위치 표시)

[출력 형식]
- 네이버 블로그에 그대로 복사 가능한 HTML 텍스트
"""


# 트위터용 템플릿
TWITTER_TEMPLATE = """
당신은 SNS(트위터) 전문 카피라이터입니다.
아래 정보를 기반으로 150자 내외의 짧고 강력한 홍보글을 작성하세요.

[정보]
- 제품명: {product_name}
- 키워드: {keyword}
- 톤: {tone}

[규칙]
1. 자연스러운 한 문단
2. 해시태그 최소 7개 포함
3. 광고 느낌보다 추천/후기 느낌 강조
4. CTA 1개 포함
"""

# 플랫폼별 템플릿을 하나의 dict 에 저장
TEMPLATES = {
    "naver": NAVER_TEMPLATE,
    "twitter": TWITTER_TEMPLATE
}