from datetime import datetime, timezone
from enum import Enum
from typing import TypedDict, Annotated, Optional, Any
import operator

from pydantic import BaseModel


class LlmSettings(BaseModel):
    """LLM 세팅들"""

    id: int
    userId: int
    name: str
    modelName: str
    status: bool
    maxTokens: str
    temperature: float
    prompt: str
    apiKey: str
    generationType: str
    createdAt: str
    updatedAt: str


class UploadChannelSettings(BaseModel):
    """업로드 채널 세팅들"""

    id: int
    userId: int
    name: str  # 채널의 name
    apiKey: str
    status: str
    createdAt: str
    updatedAt: str


class Settings(BaseModel):
    """세팅 두 개 묶음"""

    channelSettings: UploadChannelSettings
    llmSettings: LlmSettings


class PostData(BaseModel):
    """게시글의 작성"""

    title: str
    content: str


class GraphState(TypedDict, total=False):
    """그래프에 저장되는 상태, 병렬 처리를 위해 TypeDict로 작성함"""

    keyword: str
    jobId: str
    need_keyword: bool
    keywords: list[str]
    settings: Settings
    products: Annotated[dict[str, list[dict]], operator.or_]
    filtered_products: list[dict]
    need_more_products: bool
    need_retry: bool
    try_count: int
    failed: bool
    result: dict


class LogType(str, Enum):
    """지원되는 로그 타입."""

    INFO = "INFO"
    WARN = "WARN"
    ERROR = "ERROR"
    DEBUG = "DEBUG"


class LogPayload(BaseModel):
    """자바 서버가 기대하는 필드 구조."""

    userId: int
    logType: str
    loggedProcess: str
    loggedDate: str
    message: str
    submessage: str = ""
    jobId: str = ""

    @classmethod
    def build(
        cls,
        *,
        user_id: int,
        log_type: LogType | str,
        logged_process: str,
        message: str,
        submessage: str = "",
        job_id: Optional[str] = None,
        logged_date: Optional[datetime] = None,
    ) -> "LogPayload":
        logged_dt = logged_date or datetime.now(timezone.utc)
        # 자바 LocalDateTime은 타임존 정보를 허용하지 않으므로 UTC로 통일
        if logged_dt.tzinfo is None:
            # naive datetime은 UTC로 간주 (권장하지 않음)
            iso_logged_date = logged_dt.isoformat()
        else:
            # timezone-aware datetime은 UTC로 변환 후 tzinfo 제거
            logged_dt = logged_dt.astimezone(timezone.utc).replace(tzinfo=None)
            iso_logged_date = logged_dt.isoformat()

        return cls(
            userId=user_id,
            logType=log_type.value if isinstance(log_type, LogType) else str(log_type),
            loggedProcess=logged_process,
            loggedDate=iso_logged_date,
            message=message,
            submessage=submessage,
            jobId=job_id or "",
        )


class ProductInfo(BaseModel):
    name: str
    link: str
    detail_specs: dict[str, Any]
    price: int
    thumbnail_url: str


class CompareableInfo(BaseModel):
    name: str
    price: str
    thumbnail_url: str
