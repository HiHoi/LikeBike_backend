#!/bin/sh
set -e

# 데이터베이스 연결 정보는 환경 변수(DATABASE_URL)를 통해 전달되어야 합니다.

# 데이터베이스가 준비될 때까지 대기하는 로직 (필요 시 주석 해제)
# echo "Waiting for database..."
# while ! nc -z $DB_HOST $DB_PORT; do
#   sleep 1
# done
# echo "Database is up."

# Python 스크립트를 사용하여 데이터베이스 초기화 확인 및 실행
echo "Checking database initialization..."
python init_db.py

# 데이터베이스 마이그레이션 실행
echo "Running database migrations..."
python migrate.py

# Flask 애플리케이션 실행
echo "Starting Gunicorn server..."
exec gunicorn -b 0.0.0.0:3000 run:app
