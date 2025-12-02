# Repository Guidelines

## Project Structure & Module Organization
- 핵심 코드는 `app/` 아래에 있으며 FastAPI 관점으로 정리: `routers/`(HTTP 라우트), `services/`(비즈니스 로직), `models/`(Pydantic 스키마), `utils/`(공용 헬퍼).
- 설정과 로깅은 `app/config.py`, `app/logs.py`에 위치. 지속 보관이 필요한 자산은 `app/assets/`, 임시 스크립트나 노트북은 `dev/`에 둡니다.
- 테스트는 `test/`가 미러 구조로 가지며 각 `test_*.py`가 대응 기능을 다룹니다.
- 종속성은 `requirements.txt`로 관리하며 생성물은 버전에 포함하지 않습니다.

## Build, Test, and Development Commands
- 가상환경: `python3.11 -m venv .venv && source .venv/bin/activate`
- 의존성 설치: `pip install -r requirements.txt`
- 브라우저 준비(1회): `playwright install chromium`
- 로컬 실행: `uvicorn app.main:app --reload --port 8000` (코드 변경 시 자동 재시작)
- 전체 테스트: `pytest` / 특정 케이스: `pytest test/test_crawler.py -k instagram`

## Coding Style & Naming Conventions
- 파이썬 4-space 인덴트, snake_case 함수/모듈, PascalCase Pydantic 모델, 환경 변수는 `config.py`에서 ALL_CAPS 상수로 관리.
- 타입 힌트는 서비스·라우터 경계에서 필수. 로그는 `app/logs.py` 유틸 사용; `print` 지양.
- 포맷터: `black`; import 정렬: `isort`(표준/서드파티/로컬 순).
- 라우터는 명확한 prefix 사용 예: `routers/trends.py` → `/trends`.

## Testing Guidelines
- 프레임워크: `pytest`; 파일명 `test_*.py`, 함수명은 동작 서술형 예) `test_crawler_handles_empty_keyword`.
- 외부 API(SNS/Google)는 모킹해 결정적 테스트 유지. 회귀 입력은 `test/fixtures/`에 추가.
- 변경 시 최소 스모크: `pytest --maxfail=1 --disable-warnings`; 가능하면 전체 스위트 실행.

## Commit & Pull Request Guidelines
- 커밋 prefix: `feat:`, `fix:`, `chore:`, `docs:`. 영어 주제행, 필요 시 본문에 한국어 상세 가능. 사소한 커밋은 스쿼시 권장.
- PR에는 범위 요약, 영향받는 라우트/서비스, 연관 이슈 링크 포함. 크롤러/LLM 변경 시 CLI 출력·샘플 요청/응답 스크린샷 등 증빙 첨부.
- 새 환경변수나 비밀키가 없다면 명시적으로 언급. 관련 도메인 리뷰어 태그.

## Security & Configuration Tips
- 비밀키는 코드/커밋에 포함하지 말고 환경 변수로 주입. 예제 필요 시 더미 값 사용.
- 노트북 커널은 `.venv` 인터프리터와 일치시켜 의존성 불일치 방지.
