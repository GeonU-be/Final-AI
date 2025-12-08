"""
상품 비교 서비스 모듈.

쿠팡과 싸다구몰 상품 간 유사도 계산 및 매칭 기능 제공.
"""

from app.services.comparison.keywords import KeywordExtractor
from app.services.comparison.similarity import SimilarityCalculator
from app.services.comparison.matcher import ProductMatcher

__all__ = ["KeywordExtractor", "SimilarityCalculator", "ProductMatcher"]

