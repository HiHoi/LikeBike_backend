import os
import sys
import psycopg2

def initialize_database():
    """
    'schema_migrations' 테이블의 존재 여부로 데이터베이스 초기화 상태를 확인합니다.
    테이블이 없으면 'schema.sql'을 실행하여 데이터베이스를 초기화합니다.
    """
    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("Error: DATABASE_URL is not set.", file=sys.stderr)
        sys.exit(1)

    conn = None
    try:
        conn = psycopg2.connect(db_url)
        with conn.cursor() as cur:
            # 'schema_migrations' 테이블이 있는지 확인
            cur.execute("SELECT to_regclass('public.schema_migrations');")
            table_exists = cur.fetchone()[0]

            if table_exists:
                print("Database already initialized.")
            else:
                print("Database not initialized. Initializing with schema.sql...")
                # schema.sql 파일 읽고 실행
                with open('schema.sql', 'r', encoding='utf-8') as f:
                    schema_sql = f.read()
                    cur.execute(schema_sql)
                conn.commit()
                print("Database initialized successfully.")

    except psycopg2.Error as e:
        print(f"Database error during initialization: {e}", file=sys.stderr)
        if conn:
            conn.rollback()
        sys.exit(1)
    except FileNotFoundError:
        print("Error: schema.sql not found.", file=sys.stderr)
        sys.exit(1)
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    initialize_database()
