"""
PaddleOCR 서비스 모듈.

이미지에서 텍스트를 추출하는 비동기 OCR 서비스.
PaddleOCR은 스레드 안전하지 않으므로 단일 스레드에서 순차 처리.
"""

from __future__ import annotations

import asyncio
import logging
import os
import platform
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from typing import List, Optional

import aiohttp
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class PaddleOCRService:
    """
    PaddleOCR 기반 비동기 OCR 서비스.
    
    PaddleOCR은 내부적으로 멀티스레딩을 사용하므로,
    외부에서 병렬 처리하면 커널 크래시가 발생할 수 있음.
    따라서 단일 스레드 풀에서 순차 처리.
    """
    
    def __init__(self, model_dir: Optional[str] = None, lang: str = "korean"):
        """
        OCR 서비스 초기화.
        
        Args:
            model_dir: PaddleOCR 모델 저장 디렉토리 (None이면 프로젝트 루트 사용)
            lang: OCR 언어 (기본값: korean)
        """
        self.lang = lang
        self.ocr_engine = None
        self._initialized = False
        self._executor = ThreadPoolExecutor(max_workers=1)  # 단일 스레드
        
        # 모델 디렉토리 설정
        if model_dir:
            self.model_dir = model_dir
        else:
            # 프로젝트 루트에 .paddleocr 폴더 생성
            project_root = Path(__file__).parent.parent.parent.parent.parent
            self.model_dir = str(project_root / ".paddleocr")
        
        # 환경 변수 설정 (import 전에 필요)
        self._setup_environment()
    
    def _setup_environment(self) -> None:
        """PaddleOCR 환경 변수 설정."""
        os.makedirs(self.model_dir, exist_ok=True)
        
        os.environ['PADDLE_OCR_BASE_DIR'] = self.model_dir
        os.environ['PADDLEX_HOME'] = self.model_dir
        os.environ['PADDLEOCR_HOME'] = self.model_dir
        
        # 크로스 플랫폼 호환성
        project_root = Path(self.model_dir).parent
        os.environ['HOME'] = str(project_root)
        
        if platform.system() == 'Windows':
            os.environ['USERPROFILE'] = str(project_root)
        
        logger.debug("PaddleOCR 환경 설정 완료: %s", self.model_dir)
    
    async def initialize(self) -> bool:
        """
        OCR 엔진 비동기 초기화.
        
        Returns:
            bool: 초기화 성공 여부
        """
        if self._initialized:
            return True
        
        loop = asyncio.get_event_loop()
        
        def _init_ocr():
            try:
                from paddleocr import PaddleOCR
                
                # 한국어 모델 시도
                try:
                    engine = PaddleOCR(lang=self.lang, use_angle_cls=True)
                    logger.info("PaddleOCR 초기화 완료 (%s 모델)", self.lang)
                    return engine
                except Exception as e:
                    logger.warning("한국어 모델 초기화 실패: %s, 영어 모델로 재시도", e)
                    engine = PaddleOCR(use_angle_cls=True)
                    logger.info("PaddleOCR 초기화 완료 (영어 모델)")
                    return engine
            except Exception as e:
                logger.error("PaddleOCR 초기화 실패: %s", e)
                return None
        
        self.ocr_engine = await loop.run_in_executor(self._executor, _init_ocr)
        self._initialized = self.ocr_engine is not None
        return self._initialized
    
    async def extract_text_from_url(
        self,
        image_url: str,
        max_size: int = 1500,
        timeout: float = 15.0
    ) -> str:
        """
        이미지 URL에서 텍스트 추출.
        
        Args:
            image_url: 이미지 URL
            max_size: 이미지 최대 크기 (가로/세로 중 긴 쪽, 기본값: 1500px)
            timeout: 이미지 다운로드 타임아웃 (초)
        
        Returns:
            str: 추출된 텍스트 (실패 시 에러 메시지)
        """
        if not self._initialized:
            await self.initialize()
        
        if self.ocr_engine is None:
            return "[OCR 엔진이 초기화되지 않았습니다]"
        
        try:
            # 이미지 다운로드 (비동기)
            async with aiohttp.ClientSession() as session:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                async with session.get(
                    image_url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    if response.status != 200:
                        return f"[이미지 다운로드 실패: HTTP {response.status}]"
                    content = await response.read()
            
            # 이미지 처리 및 OCR (스레드 풀에서 실행)
            loop = asyncio.get_event_loop()
            
            def _process_ocr():
                return self._extract_text_from_bytes(content, max_size)
            
            return await loop.run_in_executor(self._executor, _process_ocr)
        
        except asyncio.TimeoutError:
            return "[이미지 다운로드 타임아웃]"
        except aiohttp.ClientError as e:
            return f"[이미지 다운로드 실패: {e}]"
        except Exception as e:
            return f"[OCR 실패: {e}]"
    
    def _extract_text_from_bytes(self, image_bytes: bytes, max_size: int) -> str:
        """
        바이트 데이터에서 텍스트 추출 (동기).
        
        Args:
            image_bytes: 이미지 바이트 데이터
            max_size: 이미지 최대 크기
        
        Returns:
            str: 추출된 텍스트
        """
        try:
            # PIL Image로 변환
            img = Image.open(BytesIO(image_bytes))
            img = img.convert('RGB')
            
            # 이미지 리사이징 (OCR 속도 향상)
            width, height = img.size
            if width > max_size or height > max_size:
                if width > height:
                    new_width = max_size
                    new_height = int(height * (max_size / width))
                else:
                    new_height = max_size
                    new_width = int(width * (max_size / height))
                img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # numpy 배열로 변환
            img_array = np.array(img)
            
            # OCR 실행
            try:
                result = self.ocr_engine.ocr(img_array, cls=True)
            except TypeError:
                result = self.ocr_engine.ocr(img_array)
            
            # 텍스트 추출
            texts = self._parse_ocr_result(result)
            
            return ' '.join(texts) if texts else '[텍스트 없음]'
        
        except Exception as e:
            return f'[OCR 처리 실패: {e}]'
    
    def _parse_ocr_result(self, result) -> List[str]:
        """
        OCR 결과 파싱.
        
        PaddleOCR 버전에 따라 다양한 형식 지원.
        """
        texts = []
        
        if not isinstance(result, list) or len(result) == 0:
            return texts
        
        first_elem = result[0]
        
        # 딕셔너리 형식 (PaddleX OCRResult)
        if hasattr(first_elem, 'get'):
            for key in ['rec_text', 'rec_texts', 'text']:
                value = first_elem.get(key)
                if value:
                    if isinstance(value, list):
                        texts.extend([str(t).strip() for t in value if t and str(t).strip()])
                    elif isinstance(value, str) and value.strip():
                        texts.append(value.strip())
                    if texts:
                        break
        
        # 속성 접근
        if not texts and hasattr(first_elem, 'rec_text'):
            rec_text = first_elem.rec_text
            if isinstance(rec_text, list):
                texts.extend([str(t).strip() for t in rec_text if t and str(t).strip()])
        
        # 구버전 형식: 리스트의 리스트
        if not texts and isinstance(first_elem, list):
            for line in first_elem:
                if line and len(line) >= 2:
                    if isinstance(line[1], tuple):
                        text = line[1][0]
                    elif isinstance(line[1], str):
                        text = line[1]
                    elif isinstance(line[1], (list, tuple)) and len(line[1]) > 0:
                        text = str(line[1][0])
                    else:
                        continue
                    if text and len(text.strip()) > 0:
                        texts.append(text.strip())
        
        return texts
    
    async def extract_texts_from_urls(
        self,
        image_urls: List[str],
        max_images: Optional[int] = 5
    ) -> dict:
        """
        여러 이미지 URL에서 텍스트 추출.
        
        첫 이미지와 마지막 이미지는 무조건 포함하고,
        나머지는 균등하게 선택.
        
        Args:
            image_urls: 이미지 URL 리스트
            max_images: 처리할 최대 이미지 수 (None이면 전체)
        
        Returns:
            dict: {
                'combined': 전체 텍스트,
                'texts': [이미지별 텍스트 리스트],
                'count': 처리된 이미지 수
            }
        """
        if not image_urls:
            return {'combined': '', 'texts': [], 'count': 0}
        
        # 이미지 선택
        urls_to_process = self._select_images(image_urls, max_images)
        
        # 순차 처리 (PaddleOCR은 병렬 처리 시 크래시)
        all_texts = []
        
        logger.info("OCR 처리 시작 (총 %d개 이미지)", len(urls_to_process))
        
        for idx, url in enumerate(urls_to_process, 1):
            logger.debug("OCR 처리 중: %d/%d", idx, len(urls_to_process))
            
            text = await self.extract_text_from_url(url)
            
            # 유효한 텍스트만 추가
            if text and not text.startswith('['):
                all_texts.append(text)
        
        logger.info("OCR 완료: %d개 이미지에서 텍스트 추출", len(all_texts))
        
        return {
            'combined': ' | '.join(all_texts) if all_texts else '',
            'texts': all_texts,
            'count': len(urls_to_process)
        }
    
    def _select_images(
        self,
        image_urls: List[str],
        max_images: Optional[int]
    ) -> List[str]:
        """
        처리할 이미지 선택 (첫/마지막 포함 + 중간 균등 선택).
        """
        if max_images is None or len(image_urls) <= max_images:
            return image_urls
        
        urls_to_process = []
        
        # 첫 이미지 무조건 포함
        urls_to_process.append(image_urls[0])
        
        # 중간 이미지 선택
        if max_images > 2:
            middle_count = max_images - 2
            middle_start = 1
            middle_end = len(image_urls) - 1
            
            if middle_count > 0:
                step = (middle_end - middle_start) / (middle_count + 1)
                for i in range(1, middle_count + 1):
                    idx = int(middle_start + step * i)
                    if idx < middle_end:
                        urls_to_process.append(image_urls[idx])
        
        # 마지막 이미지 무조건 포함
        urls_to_process.append(image_urls[-1])
        
        # 중복 제거
        seen = set()
        unique_urls = []
        for url in urls_to_process:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)
        
        return unique_urls
    
    async def close(self) -> None:
        """리소스 정리."""
        self._executor.shutdown(wait=False)
        self.ocr_engine = None
        self._initialized = False

