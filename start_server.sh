#!/bin/bash

# 프로덕션 서버 시작 스크립트

# 가상 환경 활성화
source venv/bin/activate

# 환경변수 로드
export $(cat .env | xargs)

# 포트 설정 (기본값: 8000)
PORT=${PORT:-8000}
WORKERS=${WORKERS:-4}

echo "🚀 프로덕션 서버 시작..."
echo "포트: $PORT"
echo "워커: $WORKERS"
echo "환경: production"

# Gunicorn으로 서버 시작
gunicorn \
  --workers=$WORKERS \
  --worker-class=sync \
  --bind=0.0.0.0:$PORT \
  --timeout=120 \
  --access-logfile=- \
  --error-logfile=- \
  --log-level=info \
  app:app
