from dataclasses import dataclass
from typing import TypedDict, Annotated
import operator


@dataclass
class LlmSettings:
    apiKey: str
    model: str
    prompt: str
    targetLength: int


@dataclass
class PostData:
    title: str
    content: str


@dataclass
class GraphState(TypedDict, total=False):
    keyword: str
    need_keyword: bool
    keywords: list[str]
    settings: LlmSettings
    products: Annotated[dict[str, list[dict]], operator.or_]
    filtered_products: list[dict]
    need_more_products: bool
    need_retry: bool
    try_count: int
    failed: bool
