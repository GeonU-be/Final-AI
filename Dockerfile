FROM mcr.microsoft.com/playwright/python:v1.46.0-jammy

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DISPLAY=:99

WORKDIR /app

RUN apt-get update && apt-get install -y \
    xvfb \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt \
    && playwright install chromium

COPY . .

EXPOSE 8000

# ✅ 컨테이너 시작 시:
# 1) Xvfb :99 서버를 백그라운드로 띄우고
# 2) 그 DISPLAY에서 uvicorn 실행
CMD ["bash", "-c", "Xvfb :99 -screen 0 1280x1024x24 & exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"]
