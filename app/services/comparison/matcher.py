"""
상품 매칭 모듈.

쿠팡과 싸다구몰 상품 간 유사한 상품 쌍을 찾아 매칭.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import List, Optional

from app.services.comparison.similarity import SimilarityCalculator

logger = logging.getLogger(__name__)


class ProductMatcher:
    """
    상품 매칭 서비스.
    
    비동기 방식으로 두 쇼핑몰의 상품을 비교하여 유사한 상품 쌍을 찾음.
    """
    
    DEFAULT_THRESHOLD = 0.4
    DEFAULT_MAX_WORKERS = 10
    
    def __init__(
        self,
        threshold: float = DEFAULT_THRESHOLD,
        max_workers: int = DEFAULT_MAX_WORKERS,
        similarity_calculator: Optional[SimilarityCalculator] = None
    ):
        """
        상품 매칭 서비스 초기화.
        
        Args:
            threshold: 유사도 임계값 (이 값 이상인 상품만 매칭)
            max_workers: 동시 처리할 최대 작업 수
            similarity_calculator: 유사도 계산기 (None이면 기본값 사용)
        """
        self.threshold = threshold
        self.max_workers = max_workers
        self.calculator = similarity_calculator or SimilarityCalculator()
    
    async def find_similar_products(
        self,
        products_coupang: List[dict],
        products_ssadagu: List[dict],
        progress_callback: Optional[callable] = None
    ) -> List[dict]:
        """
        쿠팡과 싸다구 상품 중 유사한 상품 쌍을 찾음.
        
        Args:
            products_coupang: 쿠팡 상품 리스트
            products_ssadagu: 싸다구 상품 리스트
            progress_callback: 진행 상황 콜백 함수 (progress: float, message: str)
        
        Returns:
            list: 유사한 상품 쌍 리스트
        """
        candidates = []
        
        # 비교 작업 리스트 생성 (썸네일이 있는 것만)
        comparison_tasks = [
            (p1, p2)
            for p1 in products_coupang
            for p2 in products_ssadagu
            if p1.get("thumbnail_url") and p2.get("thumbnail_url")
        ]
        
        total_comparisons = len(comparison_tasks)
        total_possible = len(products_coupang) * len(products_ssadagu)
        
        logger.info(
            "상품 비교 시작: %d개(쿠팡) × %d개(싸다구) = %d개 비교 (썸네일 있는 상품: %d개)",
            len(products_coupang), len(products_ssadagu), total_possible, total_comparisons
        )
        
        if not comparison_tasks:
            logger.warning("비교할 상품이 없습니다")
            return []
        
        start_time = time.time()
        completed = 0
        
        # 세마포어로 동시 실행 제한
        semaphore = asyncio.Semaphore(self.max_workers)
        
        async def process_comparison(p1: dict, p2: dict) -> Optional[dict]:
            """단일 상품 쌍 비교."""
            async with semaphore:
                try:
                    similarity = await self.calculator.calculate_combined_similarity(p1, p2)
                    
                    if similarity["combined_similarity"] >= self.threshold:
                        return {
                            "coupang_product": {
                                "title": p1.get("title", ""),
                                "price": p1.get("displayed_price") or p1.get("price") or p1.get("original_price", ""),
                                "thumbnail_url": p1.get("thumbnail_url", ""),
                                "product_link": p1.get("product_link", "")
                            },
                            "ssadagu_product": {
                                "title": p2.get("title", ""),
                                "price": p2.get("displayed_price") or p2.get("price") or p2.get("original_price", ""),
                                "thumbnail_url": p2.get("thumbnail_url", ""),
                                "product_link": p2.get("product_link", "")
                            },
                            "similarity": similarity
                        }
                except Exception as e:
                    logger.debug("비교 실패: %s", e)
                return None
        
        # 모든 비교 작업 생성
        tasks = [
            process_comparison(p1, p2)
            for p1, p2 in comparison_tasks
        ]
        
        # 배치로 처리하여 진행 상황 보고
        batch_size = max(1, total_comparisons // 10)
        
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            results = await asyncio.gather(*batch, return_exceptions=True)
            
            for result in results:
                if isinstance(result, dict):
                    candidates.append(result)
                completed += 1
            
            # 진행 상황 보고
            if progress_callback:
                progress = completed / total_comparisons
                elapsed = time.time() - start_time
                remaining = (elapsed / progress) * (1 - progress) if progress > 0 else 0
                
                await asyncio.to_thread(
                    progress_callback,
                    progress,
                    f"진행률: {progress*100:.1f}% ({completed}/{total_comparisons}) | "
                    f"경과: {elapsed/60:.1f}분 | 예상 남은: {remaining/60:.1f}분"
                )
        
        elapsed_total = time.time() - start_time
        logger.info(
            "상품 비교 완료: %d개 후보 발견 (임계값: %.2f 이상) | 소요 시간: %.1f분",
            len(candidates), self.threshold, elapsed_total / 60
        )
        
        return candidates
    
    async def find_top_matches(
        self,
        products_coupang: List[dict],
        products_ssadagu: List[dict],
        top_k: int = 3
    ) -> List[dict]:
        """
        가장 유사한 상위 K개 상품 쌍을 찾음.
        
        Args:
            products_coupang: 쿠팡 상품 리스트
            products_ssadagu: 싸다구 상품 리스트
            top_k: 반환할 최대 상품 쌍 수
        
        Returns:
            list: 상위 K개 유사 상품 쌍 (유사도 내림차순)
        """
        candidates = await self.find_similar_products(products_coupang, products_ssadagu)
        
        # 유사도 기준 정렬
        sorted_candidates = sorted(
            candidates,
            key=lambda x: x["similarity"]["combined_similarity"],
            reverse=True
        )
        
        return sorted_candidates[:top_k]

