"""
이미지 처리 유틸리티 모듈.

이미지 해싱, 다운로드, 리사이징 등 공통 이미지 처리 기능.
"""

from __future__ import annotations

import asyncio
import logging
from io import BytesIO
from typing import Dict, Optional, Tuple

import aiohttp
import imagehash
from PIL import Image

logger = logging.getLogger(__name__)


class ImageHashCache:
    """이미지 해시 캐시 관리자."""
    
    def __init__(self):
        self._cache: Dict[str, Optional[imagehash.ImageHash]] = {}
    
    def get(self, url: str) -> Optional[imagehash.ImageHash]:
        """캐시에서 해시 조회."""
        return self._cache.get(url)
    
    def set(self, url: str, hash_value: Optional[imagehash.ImageHash]) -> None:
        """캐시에 해시 저장."""
        self._cache[url] = hash_value
    
    def has(self, url: str) -> bool:
        """캐시에 URL이 있는지 확인."""
        return url in self._cache
    
    def clear(self) -> None:
        """캐시 초기화."""
        self._cache.clear()
    
    def size(self) -> int:
        """캐시 크기 반환."""
        return len(self._cache)


# 전역 캐시 인스턴스
_global_hash_cache = ImageHashCache()


async def download_image(
    url: str,
    timeout: float = 10.0,
    headers: Optional[dict] = None
) -> Optional[bytes]:
    """
    이미지 URL에서 바이트 데이터 다운로드.
    
    Args:
        url: 이미지 URL
        timeout: 요청 타임아웃 (초)
        headers: 요청 헤더
    
    Returns:
        bytes: 이미지 바이트 데이터 (실패 시 None)
    """
    if not url:
        return None
    
    default_headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    request_headers = {**default_headers, **(headers or {})}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=request_headers,
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                if response.status != 200:
                    logger.debug("이미지 다운로드 실패: HTTP %d (%s)", response.status, url[:50])
                    return None
                return await response.read()
    except asyncio.TimeoutError:
        logger.debug("이미지 다운로드 타임아웃: %s", url[:50])
        return None
    except aiohttp.ClientError as e:
        logger.debug("이미지 다운로드 오류 (%s): %s", url[:50], e)
        return None
    except Exception as e:
        logger.debug("이미지 다운로드 예외 (%s): %s", url[:50], e)
        return None


def resize_image(
    image: Image.Image,
    max_size: int = 1500
) -> Image.Image:
    """
    이미지를 최대 크기에 맞게 리사이즈 (비율 유지).
    
    Args:
        image: PIL Image 객체
        max_size: 가로/세로 중 긴 쪽의 최대 크기
    
    Returns:
        Image.Image: 리사이즈된 이미지
    """
    width, height = image.size
    
    if width <= max_size and height <= max_size:
        return image
    
    if width > height:
        new_width = max_size
        new_height = int(height * (max_size / width))
    else:
        new_height = max_size
        new_width = int(width * (max_size / height))
    
    return image.resize((new_width, new_height), Image.Resampling.LANCZOS)


def compute_phash(image_bytes: bytes) -> Optional[imagehash.ImageHash]:
    """
    이미지 바이트 데이터에서 perceptual hash 계산.
    
    Args:
        image_bytes: 이미지 바이트 데이터
    
    Returns:
        imagehash.ImageHash: 이미지 해시 (실패 시 None)
    """
    try:
        img = Image.open(BytesIO(image_bytes))
        return imagehash.phash(img)
    except Exception as e:
        logger.debug("이미지 해시 계산 실패: %s", e)
        return None


async def get_image_hash(
    url: str,
    timeout: float = 3.0,
    use_cache: bool = True
) -> Optional[imagehash.ImageHash]:
    """
    이미지 URL에서 perceptual hash 계산 (캐싱 지원).
    
    Args:
        url: 이미지 URL
        timeout: 요청 타임아웃 (초)
        use_cache: 캐시 사용 여부
    
    Returns:
        imagehash.ImageHash: 이미지 해시 (실패 시 None)
    """
    if not url:
        return None
    
    # 캐시 확인
    if use_cache and _global_hash_cache.has(url):
        return _global_hash_cache.get(url)
    
    # 이미지 다운로드
    image_bytes = await download_image(url, timeout=timeout)
    if not image_bytes:
        if use_cache:
            _global_hash_cache.set(url, None)
        return None
    
    # 해시 계산 (스레드 풀에서)
    loop = asyncio.get_event_loop()
    hash_value = await loop.run_in_executor(None, compute_phash, image_bytes)
    
    # 캐시에 저장
    if use_cache:
        _global_hash_cache.set(url, hash_value)
    
    return hash_value


async def calculate_image_similarity(
    url1: str,
    url2: str,
    timeout: float = 3.0
) -> float:
    """
    두 이미지의 유사도 계산 (0-1, 1에 가까울수록 유사).
    
    Args:
        url1: 첫 번째 이미지 URL
        url2: 두 번째 이미지 URL
        timeout: 요청 타임아웃 (초)
    
    Returns:
        float: 유사도 (0.0-1.0)
    """
    if not url1 or not url2:
        return 0.0
    
    # 병렬로 해시 계산
    hash1, hash2 = await asyncio.gather(
        get_image_hash(url1, timeout=timeout),
        get_image_hash(url2, timeout=timeout)
    )
    
    if hash1 is None or hash2 is None:
        return 0.0
    
    # Hamming distance 계산 (0-64)
    difference = hash1 - hash2
    
    # 유사도로 변환 (0-1)
    similarity = 1 - (difference / 64.0)
    return max(0.0, min(1.0, similarity))


def get_image_dimensions(image_bytes: bytes) -> Optional[Tuple[int, int]]:
    """
    이미지 바이트 데이터에서 크기 정보 추출.
    
    Args:
        image_bytes: 이미지 바이트 데이터
    
    Returns:
        tuple: (width, height) 또는 None
    """
    try:
        img = Image.open(BytesIO(image_bytes))
        return img.size
    except Exception:
        return None


def clear_hash_cache() -> None:
    """전역 이미지 해시 캐시 초기화."""
    _global_hash_cache.clear()
    logger.debug("이미지 해시 캐시 초기화됨")


def get_hash_cache_size() -> int:
    """전역 이미지 해시 캐시 크기 반환."""
    return _global_hash_cache.size()

