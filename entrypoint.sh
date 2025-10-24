#!/bin/sh
set -e

# 데이터베이스 연결 정보는 환경 변수(DATABASE_URL)를 통해 전달되어야 합니다.

# 데이터베이스가 준비될 때까지 대기하는 로직 (필요 시 주석 해제)
# echo "Waiting for database..."
# while ! nc -z $DB_HOST $DB_PORT; do
#   sleep 1
# done
# echo "Database is up."

# 데이터베이스가 초기화되었는지 확인
# to_regclass 함수는 테이블이 존재하면 테이블명을, 없으면 NULL을 반환합니다.
# psql 명령어 실행을 위해 DATABASE_URL 환경변수가 필수입니다.
if [ -z "$DATABASE_URL" ]; then
  echo "Error: DATABASE_URL is not set. Cannot check database status."
  exit 1
fi

SCHEMA_MIGRATIONS_EXISTS=$(psql $DATABASE_URL -t -c "SELECT to_regclass('public.schema_migrations');" | tr -d '[:space:]')

if [ -z "$SCHEMA_MIGRATIONS_EXISTS" ]; then
  echo "Database not initialized. Initializing with schema.sql..."
  psql $DATABASE_URL < schema.sql
  echo "Database initialized successfully."
else
  echo "Database already initialized."
fi

# 데이터베이스 마이그레이션 실행
echo "Running database migrations..."
python migrate.py

# Flask 애플리케이션 실행
echo "Starting Gunicorn server..."
exec gunicorn -b 0.0.0.0:3000 run:app
