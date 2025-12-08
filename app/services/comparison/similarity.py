"""
유사도 계산 모듈.

이미지, 상품명, 가격, 상세정보의 유사도를 계산.
"""

from __future__ import annotations

import asyncio
import logging
import re
from difflib import SequenceMatcher
from io import BytesIO
from typing import Dict, List, Optional, Set, Tuple

import aiohttp
import imagehash
from PIL import Image

from app.services.comparison.keywords import KeywordExtractor
from app.services.crawler.ocr.text_extractor import clean_ocr_text, remove_marketing_words

logger = logging.getLogger(__name__)


class SimilarityCalculator:
    """
    상품 유사도 계산기.
    
    비동기 방식으로 이미지, 상품명, 가격, 상세정보의 유사도를 계산.
    """
    
    # 기본 가중치 설정
    DEFAULT_IMAGE_WEIGHT = 0.35
    DEFAULT_PRICE_WEIGHT = 0.15
    DEFAULT_TITLE_WEIGHT = 0.25
    DEFAULT_OCR_SPECS_WEIGHT = 0.25
    
    def __init__(
        self,
        image_weight: float = DEFAULT_IMAGE_WEIGHT,
        price_weight: float = DEFAULT_PRICE_WEIGHT,
        title_weight: float = DEFAULT_TITLE_WEIGHT,
        ocr_specs_weight: float = DEFAULT_OCR_SPECS_WEIGHT
    ):
        """
        유사도 계산기 초기화.
        
        Args:
            image_weight: 이미지 유사도 가중치
            price_weight: 가격 유사도 가중치
            title_weight: 상품명 유사도 가중치
            ocr_specs_weight: 상세정보 유사도 가중치
        """
        self.image_weight = image_weight
        self.price_weight = price_weight
        self.title_weight = title_weight
        self.ocr_specs_weight = ocr_specs_weight
        self.total_weight = image_weight + price_weight + title_weight + ocr_specs_weight
        
        # 이미지 해시 캐시
        self._image_hash_cache: Dict[str, Optional[imagehash.ImageHash]] = {}
    
    async def get_image_hash(
        self,
        image_url: str,
        timeout: float = 3.0
    ) -> Optional[imagehash.ImageHash]:
        """
        이미지 URL에서 perceptual hash 계산 (캐싱 포함).
        
        Args:
            image_url: 이미지 URL
            timeout: 요청 타임아웃 (초)
        
        Returns:
            imagehash.ImageHash 또는 None (실패 시)
        """
        # 캐시 확인
        if image_url in self._image_hash_cache:
            return self._image_hash_cache[image_url]
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    image_url,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    if response.status != 200:
                        return None
                    content = await response.read()
            
            # 이미지 해시 계산 (스레드 풀에서)
            loop = asyncio.get_event_loop()
            
            def _compute_hash():
                img = Image.open(BytesIO(content))
                return imagehash.phash(img)
            
            hash_value = await loop.run_in_executor(None, _compute_hash)
            
            # 캐시에 저장
            self._image_hash_cache[image_url] = hash_value
            return hash_value
        
        except Exception as e:
            logger.debug("이미지 해시 계산 실패 (%s): %s", image_url[:50], e)
            return None
    
    async def calculate_image_similarity(
        self,
        url1: str,
        url2: str
    ) -> float:
        """
        두 이미지의 유사도 계산 (0-1, 1에 가까울수록 유사).
        
        Args:
            url1: 첫 번째 이미지 URL
            url2: 두 번째 이미지 URL
        
        Returns:
            float: 유사도 (0.0-1.0)
        """
        if not url1 or not url2:
            return 0.0
        
        # 병렬로 해시 계산
        hash1, hash2 = await asyncio.gather(
            self.get_image_hash(url1),
            self.get_image_hash(url2)
        )
        
        if hash1 is None or hash2 is None:
            return 0.0
        
        # Hamming distance 계산 (0-64)
        difference = hash1 - hash2
        
        # 유사도로 변환 (0-1)
        similarity = 1 - (difference / 64.0)
        return max(0.0, min(1.0, similarity))
    
    def calculate_title_similarity(self, title1: str, title2: str) -> float:
        """
        두 상품명의 유사도 계산 (단어 기반, 0-1).
        
        Args:
            title1: 첫 번째 상품명
            title2: 두 번째 상품명
        
        Returns:
            float: 유사도 (0.0-1.0)
        """
        if not title1 or not title2:
            return 0.0
        
        # 마케팅 문구 제거
        title1_cleaned = remove_marketing_words(title1)
        title2_cleaned = remove_marketing_words(title2)
        
        if not title1_cleaned or not title2_cleaned:
            return 0.0
        
        # 단어로 분리 (1글자 단어 제외)
        words1 = set(word for word in title1_cleaned.split() if len(word) > 1)
        words2 = set(word for word in title2_cleaned.split() if len(word) > 1)
        
        if not words1 or not words2:
            return 0.0
        
        # Jaccard 유사도 (단어 집합 기반)
        intersection = words1 & words2
        union = words1 | words2
        jaccard_sim = len(intersection) / len(union) if union else 0.0
        
        # SequenceMatcher 유사도 (부분 일치 고려)
        sequence_sim = SequenceMatcher(None, title1_cleaned, title2_cleaned).ratio()
        
        # 제품 사양 키워드 매칭
        spec_keywords1 = KeywordExtractor.extract(title1)
        spec_keywords2 = KeywordExtractor.extract(title2)
        
        spec_sim = 0.0
        if spec_keywords1 or spec_keywords2:
            spec_common = spec_keywords1 & spec_keywords2
            spec_total = spec_keywords1 | spec_keywords2
            spec_sim = len(spec_common) / len(spec_total) if spec_total else 0.0
        
        # 가중 평균 (단어 50%, 시퀀스 30%, 키워드 20%)
        if spec_sim > 0:
            combined = (jaccard_sim * 0.5) + (sequence_sim * 0.3) + (spec_sim * 0.2)
        else:
            combined = (jaccard_sim * 0.6) + (sequence_sim * 0.4)
        
        return max(0.0, min(1.0, combined))
    
    def calculate_price_similarity(
        self,
        price1: Optional[str],
        price2: Optional[str]
    ) -> float:
        """
        두 가격의 유사도 계산 (0-1).
        
        Args:
            price1: 첫 번째 가격 (문자열 또는 숫자)
            price2: 두 번째 가격
        
        Returns:
            float: 유사도 (0.0-1.0)
        """
        p1 = self._parse_price(price1)
        p2 = self._parse_price(price2)
        
        if p1 is None or p2 is None or max(p1, p2) == 0:
            return 0.0
        
        diff_ratio = abs(p1 - p2) / max(p1, p2)
        return max(0.0, 1 - diff_ratio)
    
    def _parse_price(self, price_value) -> Optional[float]:
        """가격 문자열을 float로 변환."""
        if price_value is None:
            return None
        if isinstance(price_value, (int, float)):
            return float(price_value)
        cleaned = re.sub(r"[^0-9.]", "", str(price_value))
        if not cleaned:
            return None
        try:
            return float(cleaned)
        except ValueError:
            return None
    
    def calculate_ocr_specs_similarity(
        self,
        ocr_text: str,
        detail_specs: dict
    ) -> float:
        """
        쿠팡 OCR 텍스트와 싸다구 상세 정보의 유사도 계산 (하이브리드 접근).
        
        Args:
            ocr_text: 쿠팡 OCR 텍스트 (문자열)
            detail_specs: 싸다구 상세 정보 (딕셔너리)
        
        Returns:
            float: 유사도 (0.0-1.0)
        """
        # 싸다구 상세 정보를 텍스트로 변환
        specs_text = self._convert_specs_to_text(detail_specs)
        
        if not ocr_text or not specs_text:
            return 0.0
        
        # OCR 텍스트 정제
        cleaned_ocr = clean_ocr_text(ocr_text)
        
        # 키워드 매칭
        ocr_keywords = KeywordExtractor.extract(cleaned_ocr)
        specs_keywords = KeywordExtractor.extract(specs_text)
        
        keyword_sim = 0.0
        if ocr_keywords or specs_keywords:
            # 정규화된 키워드 세트
            normalized_ocr = {KeywordExtractor.normalize_keyword(k) for k in ocr_keywords}
            normalized_specs = {KeywordExtractor.normalize_keyword(k) for k in specs_keywords}
            
            # 정확히 일치하는 키워드
            exact_matches = normalized_ocr & normalized_specs
            
            # 부분 매칭
            partial_matches = 0
            remaining_ocr = normalized_ocr - exact_matches
            remaining_specs = normalized_specs - exact_matches
            
            for k1 in list(remaining_ocr):
                for k2 in list(remaining_specs):
                    if k1 in k2 or k2 in k1:
                        partial_matches += 1
                        remaining_ocr.discard(k1)
                        remaining_specs.discard(k2)
                        break
            
            # Fuzzy 매칭
            fuzzy_matches = 0
            for k1 in list(remaining_ocr):
                best_sim = 0.0
                best_match = None
                
                for k2 in list(remaining_specs):
                    sim = SequenceMatcher(None, k1, k2).ratio()
                    if sim > 0.65 and sim > best_sim:
                        best_match = k2
                        best_sim = sim
                
                if best_match:
                    fuzzy_matches += 1
                    remaining_ocr.discard(k1)
                    remaining_specs.discard(best_match)
            
            # Jaccard 유사도 기반 계산
            matched_keywords = len(exact_matches) + (partial_matches * 0.8) + (fuzzy_matches * 0.6)
            total_unique = len(normalized_ocr | normalized_specs)
            
            if total_unique > 0:
                keyword_sim = matched_keywords / total_unique
            
            keyword_sim = min(1.0, keyword_sim)
        
        # 텍스트 유사도 계산
        if ocr_keywords and specs_keywords:
            # 키워드 주변 텍스트 추출
            ocr_keyword_contexts = self._extract_keyword_contexts(cleaned_ocr, ocr_keywords)
            specs_keyword_contexts = self._extract_keyword_contexts(specs_text, specs_keywords)
            
            context_sim = 0.0
            if ocr_keyword_contexts and specs_keyword_contexts:
                context_text_ocr = ' '.join(ocr_keyword_contexts)
                context_text_specs = ' '.join(specs_keyword_contexts)
                context_sim = SequenceMatcher(
                    None, context_text_ocr.lower(), context_text_specs.lower()
                ).ratio()
            
            full_text_sim = SequenceMatcher(
                None, cleaned_ocr.lower(), specs_text.lower()
            ).ratio()
            
            text_sim = (context_sim * 0.7) + (full_text_sim * 0.3)
        else:
            text_sim = SequenceMatcher(
                None, cleaned_ocr.lower(), specs_text.lower()
            ).ratio()
        
        # 최종 가중 평균 (키워드 60%, 텍스트 40%)
        if keyword_sim > 0:
            combined = (keyword_sim * 0.6) + (text_sim * 0.4)
        else:
            combined = text_sim * 0.7
        
        return max(0.0, min(1.0, combined))
    
    def _convert_specs_to_text(self, detail_specs: dict) -> str:
        """싸다구의 구조화된 상세 정보를 텍스트로 변환."""
        if not detail_specs or not isinstance(detail_specs, dict):
            return ""
        
        # 중요한 사양 키만 추출
        important_keys = [
            # 공통
            "상표", "브랜드", "모델", "모델명", "제조사", "제조국", "원산지",
            "색상", "색깔", "컬러", "무게", "중량", "제품 크기", "크기", "사이즈", "규격",
            # 컴퓨터/전자제품
            "CPU 유형", "프로세서", "CPU 주파수", "프로세서 주파수", "프로세서 코어",
            "메모리 용량", "RAM", "하드 드라이브 용량", "저장 유형", "SSD", "HDD",
            "화면 크기", "해상도", "그래픽 카드", "GPU", "운영 체제", "OS", "배터리",
            # 의류/패션
            "소재", "재질", "원단", "혼용률", "세탁방법", "시즌", "핏",
            # 식품/음료
            "용량", "내용량", "유통기한", "소비기한", "제조일자", "칼로리", "열량",
            "성분", "원재료", "알레르기", "보관방법", "영양정보",
            # 가구/인테리어
            "재료", "프레임", "쿠션", "높이", "너비", "깊이", "두께",
            # 화장품/뷰티
            "피부타입", "용도", "효능", "향",
            # 인증/등급
            "인증", "등급", "에너지등급"
        ]
        
        noise_values = [
            "선택 사항", "기계를 보세요", "N/A", "", "포함되지 않습니다", "포함하지 않음",
            "기타", "다른", "다른 크기", "다른 저장 유형", "다른 프로세서"
        ]
        
        text_parts = []
        for key in important_keys:
            if key in detail_specs:
                value = str(detail_specs[key]).strip()
                if value and value not in noise_values:
                    text_parts.append(f"{key} {value}")
        
        return " ".join(text_parts)
    
    def _extract_keyword_contexts(
        self,
        text: str,
        keywords: Set[str],
        context_size: int = 20
    ) -> List[str]:
        """키워드 주변 텍스트 추출."""
        contexts = []
        for keyword in keywords:
            keyword_lower = keyword.lower()
            idx = text.lower().find(keyword_lower)
            if idx != -1:
                start = max(0, idx - context_size)
                end = min(len(text), idx + len(keyword) + context_size)
                contexts.append(text[start:end])
        return contexts
    
    async def calculate_combined_similarity(
        self,
        product1: dict,
        product2: dict
    ) -> dict:
        """
        이미지, 가격, 상품명, 상세정보 유사도를 종합하여 계산.
        
        Args:
            product1: 첫 번째 상품 정보 (쿠팡 상품)
            product2: 두 번째 상품 정보 (싸다구 상품)
        
        Returns:
            dict: {
                "combined_similarity": 종합 유사도,
                "image_similarity": 이미지 유사도,
                "price_similarity": 가격 유사도,
                "title_similarity": 상품명 유사도,
                "ocr_specs_similarity": 상세정보 유사도
            }
        """
        # 이미지 유사도 계산 (비동기)
        img_url1 = product1.get("thumbnail_url", "")
        img_url2 = product2.get("thumbnail_url", "")
        image_sim = await self.calculate_image_similarity(img_url1, img_url2)
        
        # 상품명 유사도 계산
        title1 = product1.get("title", "")
        title2 = product2.get("title", "")
        title_sim = self.calculate_title_similarity(title1, title2)
        
        # 가격 유사도 계산
        price1 = product1.get("displayed_price") or product1.get("price") or product1.get("original_price")
        price2 = product2.get("displayed_price") or product2.get("price") or product2.get("original_price")
        price_sim = self.calculate_price_similarity(price1, price2)
        
        # 상세 정보 유사도 계산
        ocr_text = product1.get("ocr_text", "")
        detail_specs = product2.get("detail_specs", {})
        ocr_specs_sim = self.calculate_ocr_specs_similarity(ocr_text, detail_specs) if ocr_text and detail_specs else 0.0
        
        # 가중 평균으로 종합 유사도 계산
        weighted_sum = (
            image_sim * self.image_weight +
            price_sim * self.price_weight +
            title_sim * self.title_weight +
            ocr_specs_sim * self.ocr_specs_weight
        )
        combined = weighted_sum / self.total_weight if self.total_weight else 0.0
        
        return {
            "combined_similarity": combined,
            "image_similarity": image_sim,
            "price_similarity": price_sim,
            "title_similarity": title_sim,
            "ocr_specs_similarity": ocr_specs_sim
        }
    
    def clear_cache(self) -> None:
        """이미지 해시 캐시 초기화."""
        self._image_hash_cache.clear()

