"""
상품 크롤러 패키지.

쿠팡, 싸다구몰 등 쇼핑몰 상품 크롤링 기능 제공.
"""

from app.services.crawler.products.coupang_crawler import (
    CoupangCrawler,
    crawl_coupang_products,
    build_search_url,
    clean_product_title,
)
from app.services.crawler.products.ssadagu_crawler import (
    crawl_ssadagu_products,
    build_search_url as build_ssadagu_search_url,
    clean_product_title as clean_ssadagu_product_title,
)

__all__ = [
    "CoupangCrawler",
    "crawl_coupang_products",
    "crawl_ssadagu_products",
    "build_search_url",
    "build_ssadagu_search_url",
    "clean_product_title",
    "clean_ssadagu_product_title",
]
