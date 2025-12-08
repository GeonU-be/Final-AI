"""
OCR 관련 서비스 모듈.

PaddleOCR을 사용한 이미지 텍스트 추출 기능 제공.
"""

from app.services.crawler.ocr.paddle_ocr import PaddleOCRService
from app.services.crawler.ocr.text_extractor import TextExtractor

__all__ = ["PaddleOCRService", "TextExtractor"]

