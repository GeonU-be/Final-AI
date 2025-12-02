# 구조 및 이상 징후 리포트

## 치명적/즉시 확인 필요
- `app/routers/health_router.py`, `app/routers/crawler_router.py`, `app/routers/llm_router.py` 모두 빈 파일입니다. FastAPI 라우터를 분리하도록 설계했지만 `app/main.py`(1~33)에서만 엔드포인트를 정의하고 있어 모듈 구조 지침을 어깁니다. 빈 라우터가 누락된 기능으로 착각될 수 있습니다.
- `app/models/trend_model.py`, `app/models/content_model.py`와 `app/models/__init__.py`가 전부 비어 있어 Pydantic 모델이 없습니다. 현재는 `app/classes/models.py`의 dataclass를 요청 바디에 사용 중인데, FastAPI의 검증·스키마 생성이 제대로 동작하지 않아 입력 유효성 문제 및 OpenAPI 문서 누락이 발생합니다.
- LangGraph 노드 다수가 `return` 없이 `None`을 반환합니다(`app/services/llm/graph/nodes.py`: 18, 33, 44, 57, 88, 136). `edges.py`에서 이 노드들을 워크플로에 등록해 `StateGraph`를 `compile()`하지만, 실행 시 상태 병합이 실패하거나 조건 분기에서 `NoneType` 접근 오류가 날 수 있습니다.
- 크롤러·업로더 서비스 스텁만 존재합니다(`app/services/crawler/*.py`, `app/services/uploader/*.py` 모두 빈 파일). README에 명시된 기능(트렌드 크롤링·SNS 업로드)을 제공하지 못하고, 임포트 시 `ImportError`는 없지만 호출하면 즉시 실패합니다.

## 구조적/유지보수 위험
- `app/classes/models.py`에 LLM 설정, 그래프 상태, 로깅 payload가 한데 모여 있어(1~58) 책임이 섞였습니다. 로깅용 `LogPayload`와 LLM 흐름 타입을 분리하지 않아 순환 의존·확장 시 리스크가 큽니다.
- `app/main.py`에서 요청 스키마로 dataclass(`WritePostRequest`, `UploadPostRequest`)를 사용하지만 FastAPI 표준인 `pydantic.BaseModel`이 아니고, 응답을 반환하지 않아 항상 `null` 200을 돌려줍니다. API 소비자는 정상 동작으로 오인할 수 있습니다.
- 유틸리티 일부가 빈 스텁(`app/utils/token_manager.py`, `app/utils/image_downloader.py`, `app/utils/log_requester.py`)으로 남아 있어 실제 호출 시 `AttributeError` 가능성이 있습니다. `log_requester.py`는 주석만 존재해 호출 즉시 크래시 납니다.
- 테스트 스위트가 모두 비어 있습니다(`test/test_crawler.py`, `test/test_llm.py`). CI나 로컬에서 `pytest`를 돌려도 성공하지만 검증이 전무해 회귀 방지 기능이 없습니다.
- `requirements.txt`에 `playwright`가 두 번(핀/비핀) 명시되어 버전 충돌 경고 및 불필요 재설치 가능성이 있습니다.

## 응답 및 남은 조치
- 크롤러/업로더 빈 파일: dev 디렉토리의 테스트 코드를 이식할 예정이라고 하셨으므로 현재 빈 상태는 의도된 것으로 간주합니다(해결됨).
- API 응답이 `null 200`: 서버 내부 통신만 고려한 설계라고 하셨으므로 문제 없음으로 처리합니다(해결됨).
- config 정리: `app/config.py`에 모든 `getenv`를 모아 기본값/타입을 선언했습니다(FASTAPI CORS, 로그 레벨/타임아웃, Java 서버 주소, 로그 사용자 ID). 관련 이슈 해결됨.
- 유틸 스텁: dev에서 코드 이식 예정이므로 현재 상태는 의도된 스텁으로 기록합니다. 실제 호출 전 이식 일정/우선순위 결정 필요(미결).
- 테스트 스위트: dev 기반으로 실행 가능한 테스트를 어디까지 옮길지 결정 필요. 최소 스모크라도 pytest로 옮기면 회귀 검증 가능. 방향성 미정(미결).
- 라우터/모델 디렉토리: 외부가 만든 구조라면 두 가지 선택이 있습니다. 1) 불필요하면 제거해 단순화, 2) 유지하며 기능을 채워 FastAPI 관례와 맞추기. 팀 합의 필요(미결).
- LangGraph 노드 `None` 반환: 미완성 상태임을 인지했습니다. 워크플로 실행 테스트용이라도 기본 state shape을 반환하도록 최소 더미 값을 넣지 않으면 런타임 예외가 날 수 있으니, 실행 테스트 시 안전장치 여부만 확인 필요(미결).
