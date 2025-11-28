fw_system_prompt = """
당신은 탁월한 분석가 입니다.
입력으로 키워드와 상품의 정보가 주어진 후, 두 데이터가 서로 관련성이 있는지 없는지를 판단합니다.

markdown 문법을 사용하지 마십시오. 출력은 순수한 JSON으로 이루어져야 합니다.
JSON 형식을 제외한 다른 출력은 절대 금지합니다.
양식 이외의 추가적인 정보를 기입하지 마십시오.
판단의 이유는 최대한 간단하게 작성합니다. 최대 150자를 넘기지 마시오.

출력 양식은 다음과 같습니다:
{
  "isRelated": "(연관이 됐다면 y, 아니라면 n)"
  "reason": "그렇게 판단한 이유"
}
"""


def fw_input_prompt(keyword: str, product: dict) -> str:
    def filter_links(product: dict) -> dict:
        return {
            "title": product.get("title", "잘못된 제목!"),
            "price": product.get(
                "displayed_price",
                product.get("original_price", product.get("price", "잘못된 가격!")),
            ),
        }

    filtered = filter_links(product=product)
    return f"""
키워드: {keyword}

상품 정보:
  상품명: {filtered.get("title", "")}
  가격: {filtered.get("price", "")}
"""
