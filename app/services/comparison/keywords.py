"""
제품 사양 키워드 추출 모듈.

상품명, OCR 텍스트, 상세 정보에서 제품 사양 키워드를 추출.
모든 제품 카테고리에 적용 가능한 범용 패턴 사용.
"""

from __future__ import annotations

import re
from typing import Set


class KeywordExtractor:
    """제품 사양 키워드 추출기."""
    
    # 용량/크기 패턴
    CAPACITY_PATTERNS = [
        r'\d+\s*GB',   # 예: 16GB, 512GB
        r'\d+\s*TB',   # 예: 1TB, 2TB
        r'\d+\s*MB',   # 예: 128MB
    ]
    
    # 무게 패턴
    WEIGHT_PATTERNS = [
        r'\d+\.?\d*\s*kg',  # 예: 1.5kg, 2kg
        r'\d+\s*g\b',       # 예: 500g, 1000g
    ]
    
    # 부피/용량 패턴
    VOLUME_PATTERNS = [
        r'\d+\s*ml',  # 예: 500ml
        r'\d+\s*l\b', # 예: 1l, 2l
    ]
    
    # 길이/크기 패턴
    SIZE_PATTERNS = [
        r'\d+\.?\d*\s*cm',    # 예: 15.6cm
        r'\d+\.?\d*\s*mm',    # 예: 8.6mm
        r'\d+\.?\d*\s*inch',  # 예: 15.6inch
        r'\d+\.?\d*\s*인치',  # 예: 15.6인치
    ]
    
    # 치수 패턴
    DIMENSION_PATTERNS = [
        r'\d+\s*x\s*\d+',  # 예: 1920x1080
        r'\d+\s*X\s*\d+',  # 대문자 X
    ]
    
    # 모델 번호 패턴
    MODEL_PATTERNS = [
        r'[A-Za-z]+\s*\d+[-\s]?\d*',     # 예: iPhone14, i5-12400
        r'[A-Za-z]+\s*[A-Za-z]+\s*\d+',  # 예: Nike Air 1
    ]
    
    # 컴퓨터/전자제품 전용 패턴
    COMPUTER_PATTERNS = [
        r'i\d+[-\s]?\d+',  # CPU 모델 (예: i5-12400)
        r'RTX\s*\d+',      # GPU 모델 (예: RTX 3060)
        r'GTX\s*\d+',      # GPU 모델 (예: GTX 1660)
        r'SSD\s*\d+',      # SSD 용량
        r'\d+\s*세대',     # CPU 세대
    ]
    
    # 수량/개수 패턴
    QUANTITY_PATTERNS = [
        r'\d+\s*개', r'\d+\s*EA', r'\d+\s*SET', r'\d+\s*세트', r'\d+\s*팩',
        r'\d+\s*입', r'\d+\s*매', r'\d+\s*장', r'\d+\s*병', r'\d+\s*봉',
        r'\d+\s*박스', r'\d+\s*box',
    ]
    
    # 인증/표준 패턴
    CERTIFICATION_PATTERNS = [
        r'KC\s*인증', r'CE\s*인증', r'FDA\s*승인', r'ISO\s*\d+', r'KS\s*인증',
        r'HACCP', r'GMP', r'UL\s*인증', r'친환경', r'유기농', r'무농약',
    ]
    
    # 등급/품질 패턴
    GRADE_PATTERNS = [
        r'\d+\s*등급', r'[A-F]\s*급', r'특\s*\d+\s*급', r'\d+\+\+?',
    ]
    
    # 날짜 패턴
    DATE_PATTERNS = [
        r'\d{4}[-\s./]\d{1,2}[-\s./]\d{1,2}',
    ]
    
    # 색상 키워드
    COLOR_KEYWORDS = [
        '블랙', '화이트', '실버', '골드', '로즈골드',
        '레드', '블루', '그린', '옐로우', '퍼플',
        '핑크', '그레이', '베이지', '브라운', '네이비',
        '아이보리', '오렌지', '민트', '카키', '버건디',
        'black', 'white', 'silver', 'gold', 'red', 'blue', 'green', 'pink', 'gray', 'brown'
    ]
    
    # 재질/소재 키워드
    MATERIAL_KEYWORDS = [
        # 의류/직물
        '면', '폴리에스터', '나일론', '레이온', '린넨', '울', '캐시미어',
        '데님', '코튼', '실크', '새틴', '벨벳', '니트', '스웨이드', '모달',
        '스판', '폴리', '아크릴', '비스코스', '텐셀',
        # 가구/인테리어
        '나무', '원목', '합판', 'MDF', '파티클보드', '강화유리', '유리',
        '스테인리스', '스틸', '알루미늄', '철', '철제', '플라스틱', 'PVC',
        '가죽', '인조가죽', 'PU', '천', '원단', '패브릭',
        # 식품/포장
        'PET', 'PP', 'PE', 'PS', '종이', '스티로폼',
        # 기타
        '세라믹', '도자기', '고무', '실리콘', '메탈', '크롬', '황동', '구리',
        # 영어
        'cotton', 'polyester', 'leather', 'wood', 'metal', 'plastic', 'glass', 'ceramic', 'stainless'
    ]
    
    # 원산지/국가 키워드
    ORIGIN_KEYWORDS = [
        '한국', '국산', '국내산', '중국', '미국', '일본', '독일', '이탈리아',
        '베트남', '태국', '인도네시아', '필리핀', '인도', '대만', '프랑스', '스페인',
        'korea', 'china', 'usa', 'japan', 'germany', 'italy', 'vietnam', 'france',
        'made in', '제조국', '원산지', '수입', '직수입'
    ]
    
    # 등급 키워드
    GRADE_KEYWORDS = [
        '프리미엄', '고급', '일반', '표준', '특급', '최상급',
        'premium', 'grade', 'quality', '명품'
    ]
    
    # 기능/특성 키워드
    FEATURE_KEYWORDS = [
        '방수', '방진', '내열', '내구', '방오', '방취', '항균',
        '방충', '방습', '통기', '흡수', '흡습', '속건', '보온', '냉감',
        '무선', '유선', '충전식', '건전지', '자동', '수동',
        'waterproof', 'dustproof', 'heatproof', 'durable', 'wireless', 'auto'
    ]
    
    # 날짜 키워드
    DATE_KEYWORDS = [
        '유통기한', '제조일자', '제조일', '소비기한', '신선', '당일'
    ]
    
    # 사이즈/의류 키워드
    SIZE_KEYWORDS = [
        'XS', 'S', 'M', 'L', 'XL', 'XXL', 'XXXL', '2XL', '3XL', '4XL',
        'FREE', '프리사이즈', '단일사이즈',
        '소', '중', '대', '특대',
        '85', '90', '95', '100', '105', '110',
        '44', '55', '66', '77', '88',
    ]
    
    @classmethod
    def extract(cls, text: str) -> Set[str]:
        """
        텍스트에서 제품 사양 키워드를 추출.
        
        Args:
            text: 원본 텍스트
        
        Returns:
            set: 추출된 키워드 집합
        """
        if not text:
            return set()
        
        keywords: Set[str] = set()
        
        # 모든 정규식 패턴 적용
        all_patterns = (
            cls.CAPACITY_PATTERNS + cls.WEIGHT_PATTERNS + cls.VOLUME_PATTERNS +
            cls.SIZE_PATTERNS + cls.DIMENSION_PATTERNS + cls.MODEL_PATTERNS +
            cls.COMPUTER_PATTERNS + cls.QUANTITY_PATTERNS + cls.CERTIFICATION_PATTERNS +
            cls.GRADE_PATTERNS + cls.DATE_PATTERNS
        )
        
        for pattern in all_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                # 공백 제거 및 정규화
                normalized = re.sub(r'\s+', '', str(match).upper())
                if normalized and len(normalized) > 1:
                    keywords.add(normalized)
        
        # 키워드 리스트 매칭 (대소문자 무시)
        text_lower = text.lower()
        
        # 색상 키워드
        for color in cls.COLOR_KEYWORDS:
            if color.lower() in text_lower:
                keywords.add(color.upper())
        
        # 재질/소재 키워드
        for material in cls.MATERIAL_KEYWORDS:
            if material.lower() in text_lower:
                keywords.add(material.upper())
        
        # 원산지 키워드
        for origin in cls.ORIGIN_KEYWORDS:
            if origin.lower() in text_lower:
                keywords.add(origin.upper())
        
        # 등급 키워드
        for grade in cls.GRADE_KEYWORDS:
            if grade.lower() in text_lower:
                keywords.add(grade.upper())
        
        # 기능/특성 키워드
        for feature in cls.FEATURE_KEYWORDS:
            if feature.lower() in text_lower:
                keywords.add(feature.upper())
        
        # 날짜 키워드
        for date_kw in cls.DATE_KEYWORDS:
            if date_kw.lower() in text_lower:
                keywords.add(date_kw.upper())
        
        # 사이즈 키워드 (한 글자는 단어 경계 기준)
        for size in cls.SIZE_KEYWORDS:
            if len(size) == 1:
                if re.search(rf'\b{re.escape(size.lower())}\b', text_lower):
                    keywords.add(size.upper())
            else:
                if size.lower() in text_lower:
                    keywords.add(size.upper())
        
        return keywords
    
    @staticmethod
    def normalize_keyword(keyword: str) -> str:
        """
        키워드를 정규화하여 비교 가능하게 만듦.
        
        Args:
            keyword: 원본 키워드
        
        Returns:
            str: 정규화된 키워드
        """
        if not keyword:
            return ""
        normalized = keyword.lower().strip()
        # 공백, 하이픈, 언더스코어 제거
        normalized = re.sub(r'[\s\-_]+', '', normalized)
        return normalized

