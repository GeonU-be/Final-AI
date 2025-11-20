# Repository Guidelines

## Project Structure & Module Organization
Core application code resides in `app/`, organized by FastAPI concerns: `routers/` for HTTP surfaces, `services/` for business logic, `models/` for Pydantic schemas, and `utils/` for shared helpers. Runtime configuration and logging live in `app/config.py` and `app/logs.py`. Tests mirror this tree under `test/`, where each `test_*.py` targets the similarly named feature folder. Exploratory notebooks or one-off scripts belong in `dev/`, while dependency control stays in `requirements.txt`. Keep generated assets out of version control; long-lived media or fixtures should be checked into a dedicated `app/assets/` subfolder if needed.

## Build, Test, and Development Commands
Use Python 3.11 with a local venv: `python3.11 -m venv .venv && source .venv/bin/activate`. Install dependencies via `pip install -r requirements.txt`, then provision browsers once per machine with `playwright install chromium`. Run the API locally using `uvicorn app.main:app --reload --port 8000`, which hot-reloads when `app/` files change. Execute targeted smoke tests with `pytest test/test_crawler.py -k instagram` or the full suite via `pytest`. When iterating on notebooks, pin kernels to the same `.venv` interpreter to avoid mismatch errors.

## Coding Style & Naming Conventions
Follow idiomatic FastAPI patterns with clear router prefixes (for example, `routers/trends.py` exposing `/trends`). Use 4-space indentation, snake_case for functions and modules, PascalCase for Pydantic models, and ALL_CAPS for environment-bound constants in `config.py`. Prefer type hints everywhere data crosses service or router boundaries. Sort imports using `isort` grouping (stdlib, third-party, local) and format code with `black` defaults before pushing. Keep logging structured through `app/logs.py` utilities instead of ad-hoc `print`.

## Testing Guidelines
All tests use `pytest`; files must be named `test_*.py`, and functions should describe behavior (`test_crawler_handles_empty_keyword`). Mock outbound APIs to keep suite deterministic, especially for Google or SNS crawlers. Add regression fixtures under `test/fixtures/` if input payloads grow. Aim for coverage across routers, services, and util functions whenever you touch them, and fail builds locally before opening a PR by running `pytest --maxfail=1 --disable-warnings`.

## Commit & Pull Request Guidelines
Follow the existing conventional prefixes (`feat:`, `fix:`, `chore:`, `docs:`) noted in `git log`. Write concise, English subject lines after the prefix, with optional Korean detail in the body if helpful. Squash trivial commits locally. Pull requests should summarize scope, list impacted routes or services, link issues, and attach evidence (CLI output, screenshots, or sample payloads) for crawler or LLM changes. Tag reviewers from the owning domain and confirm secrets stay outside the diff; point to any new environment variables in the PR checklist.
