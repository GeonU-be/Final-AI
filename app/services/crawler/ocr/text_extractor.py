"""
텍스트 추출 및 정제 유틸리티.

OCR 결과에서 노이즈를 제거하고 유용한 정보를 추출.
"""

from __future__ import annotations

import re
from typing import List, Set


def clean_ocr_text(ocr_text: str) -> str:
    """
    OCR 텍스트에서 노이즈를 제거하고 중요한 사양 정보만 추출.
    
    Args:
        ocr_text: 원본 OCR 텍스트
    
    Returns:
        str: 정제된 텍스트
    """
    if not ocr_text:
        return ""
    
    # 마케팅 문구 제거 패턴
    marketing_patterns = [
        r'배송.*?|도착.*?|출고.*?|당일.*?',
        r'특가|할인|프로모션|이벤트|증정|사은품',
        r'고객센터.*?|문의.*?|카카오톡.*?',
        r'AS.*?|보증.*?|무상.*?',
        r'게이밍.*?RGB.*?|LED.*?',
        r'PUBG|BATTLEGROUNDS|GTA5|OVERWATCH|LOSTARK|BLACKDESERT|FIFA',
        r'배틀그라운드|오버워치|로스트아크|블랙데저트|피파',
    ]
    
    cleaned = ocr_text
    for pattern in marketing_patterns:
        cleaned = re.sub(pattern, ' ', cleaned, flags=re.IGNORECASE)
    
    # 연속된 공백 제거
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    return cleaned


def remove_marketing_words(text: str) -> str:
    """
    상품명에서 마케팅 문구를 제거.
    
    Args:
        text: 원본 텍스트
    
    Returns:
        str: 마케팅 문구가 제거된 텍스트
    """
    if not text:
        return ""
    
    marketing_words = [
        "최신형", "신상품", "신제품", "신규", "신작",
        "특가", "할인", "세일", "프로모션", "이벤트",
        "무료배송", "로켓배송", "당일배송", "빠른배송",
        "인기", "추천", "베스트", "핫딜", "초특가",
        "프리미엄", "고급형", "럭셔리",
        "무료", "증정", "사은품", "혜택", "쿠폰",
        "할인가", "특가가", "세일가", "할인가격",
        "지금", "오늘", "오늘만", "한정", "한정수량",
        "품절임박", "재고부족", "마감임박", "서둘러",
        "ad", "advertisement", "광고"
    ]
    
    cleaned_text = text.lower()
    
    for word in marketing_words:
        cleaned_text = cleaned_text.replace(word.lower(), " ")
    
    # 연속된 공백을 하나로 통합
    cleaned_text = re.sub(r'\s+', ' ', cleaned_text).strip()
    
    return cleaned_text


class TextExtractor:
    """OCR 텍스트에서 구조화된 정보 추출."""
    
    @staticmethod
    def clean_text(text: str) -> str:
        """텍스트 정제."""
        return clean_ocr_text(text)
    
    @staticmethod
    def remove_marketing(text: str) -> str:
        """마케팅 문구 제거."""
        return remove_marketing_words(text)

