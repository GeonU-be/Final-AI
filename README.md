# AURA : Automated Update & Review Assistant
    -> AI Trend Automation Platform

## Features
1. Google/SNS (twitter, instagram) 트렌드 자동 크롤링
2. LLM 기반 마케팅 콘텐츠 자동 생성
3. Instagram/Twitter/Blog 자동 업로드

## Tech Stack
- Python 3.11
- FastAPI
- LangChain + OpenAI + Upstage Solar
- Playwright + BeautifulSoup + pytrends
- SNS Upload: Twitter API, Instagram Graph API, Google Blogger API

## 세팅 가이드
### 1. Clone & Move
git clone https://github.com/KDT-Final-4/Final-AI.git
cd Final-AI

### 2. Create Virtual Environment
python3.11 -m venv .venv

### 3. Activate
source .venv/bin/activate

### 4. Install Packages
pip install -r requirements.txt

### 5. Install Playwright browsers
playwright install chromium

### 6. Start API
uvicorn app.main:app --reload --port 8000
