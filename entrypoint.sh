#!/bin/sh
set -e

# 데이터베이스가 준비될 때까지 대기하는 로직 (필요 시 주석 해제)
# echo "Waiting for database..."
# while ! nc -z $DB_HOST $DB_PORT; do
#   sleep 1
# done
# echo "Database is up."

# 데이터베이스 마이그레이션 실행
echo "Running database migrations..."
python migrate.py

# Flask 애플리케이션 실행
echo "Starting Gunicorn server..."
exec gunicorn -b 0.0.0.0:3000 run:app
