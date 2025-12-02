from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any, Dict, Optional

import requests

from app.classes.models import LogPayload, LogType
from app.config import JAVA_SERVER_ADDRESS, LOG_HTTP_TIMEOUT, LOG_LEVEL, LOG_USER_ID

logger = logging.getLogger("app.logs")
if not logger.handlers:
    # 간단한 콘솔 핸들러만 붙여 FastAPI 서버 콘솔에도 로그가 노출되도록 한다.
    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("[%(asctime)s] %(levelname)s in %(name)s: %(message)s")
    )
    logger.addHandler(handler)

logger.setLevel(LOG_LEVEL)


def _build_endpoint() -> str:
    """환경변수에서 엔드포인트를 만든다. 미설정 시 즉시 예외 발생."""
    if not JAVA_SERVER_ADDRESS:
        raise RuntimeError("JAVA_SERVER_ADDRESS env 값이 설정되지 않았습니다.")
    return f"{JAVA_SERVER_ADDRESS.rstrip('/')}/api/log"


def send_log(
    *,
    message: str,
    submessage: str = "",
    log_type: LogType | str = LogType.INFO,
    logged_process: str = "Log",
    job_id: Optional[str] = None,
    user_id: Optional[int] = None,
    session: Optional[requests.Session] = None,
) -> requests.Response:
    """자바 서버로 로그를 전송한다.

    Args:
        message: 메인 메시지.
        submessage: 추가 설명. 기본값은 빈 문자열.
        log_type: LogType 혹은 문자열. 기본은 INFO.
        logged_process: 어떤 프로세스에서 발생한 로그인지.
        job_id: 연관 작업 식별자.
        user_id: 명시적 사용자 ID(int). 없으면 LOG_USER_ID 사용.
        session: requests.Session 재사용 시 지정.
    """

    user = user_id or LOG_USER_ID
    if not user:
        raise ValueError("user_id 또는 LOG_USER_ID 환경 변수가 필요합니다.")

    payload = LogPayload.build(
        user_id=user,
        log_type=log_type,
        logged_process=logged_process,
        message=message,
        submessage=submessage,
        job_id=job_id,
    )

    body: Dict[str, Any] = asdict(payload)
    client = session or requests.Session()

    try:
        # requests.post에 json=을 넘겨 Content-Type과 직렬화를 동시에 처리
        response = client.post(
            _build_endpoint(),
            json=body,
            timeout=LOG_HTTP_TIMEOUT,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        logger.error("원격 로그 전송 실패: %s", exc)
        raise
    finally:
        if session is None:
            client.close()

    return response


def log_info(message: str, **kwargs: Any) -> requests.Response:
    """INFO 로그 전송. kwargs는 send_log 인자(submessage, job_id 등)를 그대로 전달한다."""
    return send_log(message=message, log_type=LogType.INFO, **kwargs)


def log_warn(message: str, **kwargs: Any) -> requests.Response:
    """WARN 로그 전송. kwargs는 send_log 인자로 위임된다."""
    return send_log(message=message, log_type=LogType.WARN, **kwargs)


def log_error(message: str, **kwargs: Any) -> requests.Response:
    """ERROR 로그 전송. kwargs는 send_log 인자로 위임된다."""
    return send_log(message=message, log_type=LogType.ERROR, **kwargs)


print("load logger")
