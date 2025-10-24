import os
import sys
import psycopg2
import psycopg2.extras
from glob import glob
from os.path import basename, join, dirname

def get_db_connection():
    """데이터베이스 연결을 생성합니다."""
    try:
        conn = psycopg2.connect(os.environ.get("DATABASE_URL"))
        return conn
    except psycopg2.OperationalError as e:
        print(f"Error: Could not connect to the database: {e}", file=sys.stderr)
        sys.exit(1)

def get_applied_migrations(cursor):
    """이미 적용된 마이그레이션 목록을 가져옵니다."""
    try:
        cursor.execute("SELECT version FROM schema_migrations")
        return {row['version'] for row in cursor.fetchall()}
    except psycopg2.errors.UndefinedTable:
        # schema_migrations 테이블이 없는 초기 상태
        print("`schema_migrations` table not found. Assuming fresh database.")
        return set()

def run_sql_file(cursor, filepath):
    """SQL 파일을 실행합니다."""
    print(f"  -> Applying SQL: {basename(filepath)}")
    with open(filepath, 'r') as f:
        cursor.execute(f.read())

def run_python_script(filepath):
    """Python 마이그레이션 스크립트를 실행합니다."""
    print(f"  -> Applying Python script: {basename(filepath)}")
    # Python 스크립트를 별도 프로세스로 실행
    # 이렇게 하면 현재 마이그레이션 스크립트의 의존성과 충돌하지 않습니다.
    result = os.system(f'python "{filepath}"')
    if result != 0:
        raise RuntimeError(f"Python script {basename(filepath)} failed with exit code {result}")

def main():
    """마이그레이션을 실행하는 메인 함수"""
    conn = get_db_connection()
    
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            # `schema_migrations` 테이블이 없으면 생성
            cur.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version VARCHAR(255) PRIMARY KEY,
                    applied_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()

            applied_migrations = get_applied_migrations(cur)
            print(f"Applied migrations: {sorted(list(applied_migrations)) if applied_migrations else 'None'}")

            migrations_dir = join(dirname(__file__), 'migrations')
            all_scripts = sorted(glob(join(migrations_dir, '*.*')))
            
            new_migrations_applied = False
            for script_path in all_scripts:
                script_name = basename(script_path)
                
                if script_name not in applied_migrations:
                    print(f"Applying migration: {script_name}...")
                    
                    try:
                        if script_path.endswith('.sql'):
                            run_sql_file(cur, script_path)
                        elif script_path.endswith('.py'):
                            # Python 스크립트는 자체적으로 DB 연결을 관리하므로
                            # 현재 트랜잭션 커밋 후 실행
                            conn.commit()
                            run_python_script(script_path)
                            # Python 스크립트 실행 후 다시 트랜잭션 시작
                        else:
                            print(f"  -> Skipping unsupported file type: {script_name}")
                            continue

                        # 성공적으로 적용되면 버전 기록
                        cur.execute(
                            "INSERT INTO schema_migrations (version) VALUES (%s)",
                            (script_name,)
                        )
                        conn.commit()
                        print(f"Successfully applied {script_name}")
                        new_migrations_applied = True

                    except (Exception, psycopg2.Error) as e:
                        print(f"Error applying migration {script_name}: {e}", file=sys.stderr)
                        conn.rollback()
                        sys.exit(1)

            if not new_migrations_applied:
                print("Database is up to date.")

    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    if not os.environ.get("DATABASE_URL"):
        print("Error: DATABASE_URL environment variable not set.", file=sys.stderr)
        sys.exit(1)
    main()
