from pydantic import BaseModel
from datetime import datetime, timezone
from enum import Enum
from typing import TypedDict, Annotated, Optional
import operator


class LlmSettings(BaseModel):
    """LLM 세팅들"""

    apiKey: str
    model: str
    prompt: str
    targetLength: int


class PostData(BaseModel):
    """게시글의 작성"""

    title: str
    content: str


class GraphState(TypedDict, total=False):
    """그래프에 저장되는 상태, 병렬 처리를 위해 TypeDict로 작성함"""

    keyword: str
    need_keyword: bool
    keywords: list[str]
    settings: LlmSettings
    products: Annotated[dict[str, list[dict]], operator.or_]
    filtered_products: list[dict]
    need_more_products: bool
    need_retry: bool
    try_count: int
    failed: bool


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
        logged_dt = logged_date or datetime.now()
        # 자바 LocalDateTime은 타임존 정보를 허용하지 않으므로 UTC로 맞춘 뒤 tz 제거
        if logged_dt.tzinfo:
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
