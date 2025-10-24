import os
import psycopg2
import psycopg2.extras
import json

def run_migration():
    """
    기존 퀴즈 데이터를 새로운 스키마 구조로 마이그레이션합니다.
    - quiz_options 테이블의 데이터를 quizzes.answers (JSONB)로 옮깁니다.
    - quizzes.correct_answer 필드를 채웁니다.
    - quizzes.quiz_type을 결정합니다.
    """
    conn = None
    try:
        conn = psycopg2.connect(os.environ.get("DATABASE_URL"))
        cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # 1. 모든 퀴즈를 가져옵니다.
        cur.execute("SELECT id, correct_option_id FROM quizzes WHERE answers IS NULL")
        quizzes = cur.fetchall()

        print(f"Found {len(quizzes)} quizzes to migrate.")

        for quiz in quizzes:
            # 2. 각 퀴즈에 연결된 옵션들을 가져옵니다.
            cur.execute(
                "SELECT id, option_text FROM quiz_options WHERE quiz_id = %s ORDER BY id",
                (quiz['id'],)
            )
            options = cur.fetchall()

            if not options:
                print(f"Skipping quiz {quiz['id']} as it has no options.")
                continue

            # 3. answers JSONB 형식으로 변환합니다.
            answers_list = [opt['option_text'] for opt in options]

            # 4. 정답 텍스트를 찾습니다.
            correct_answer_text = None
            for opt in options:
                if opt['id'] == quiz['correct_option_id']:
                    correct_answer_text = opt['option_text']
                    break
            
            if correct_answer_text is None:
                print(f"Warning: Could not find correct answer for quiz {quiz['id']}. Skipping.")
                continue

            # 5. 퀴즈 타입을 결정합니다.
            option_texts = {opt['option_text'].upper() for opt in options}
            is_ox = len(options) == 2 and option_texts == {'O', 'X'}
            quiz_type = 'ox' if is_ox else 'multiple_choice'

            # 6. quizzes 테이블을 업데이트합니다.
            cur.execute(
                """
                UPDATE quizzes
                SET quiz_type = %s, answers = %s, correct_answer = %s
                WHERE id = %s
                """,
                (quiz_type, json.dumps(answers_list), correct_answer_text, quiz['id'])
            )
            print(f"Migrated quiz {quiz['id']} as type '{quiz_type}'.")

        conn.commit()
        print("Quiz data migration completed successfully.")

    except psycopg2.Error as e:
        print(f"Database error: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    # DATABASE_URL 환경 변수가 설정되어 있어야 합니다.
    # 예: export DATABASE_URL="postgresql://user:password@host:port/dbname"
    if not os.environ.get("DATABASE_URL"):
        print("Error: DATABASE_URL environment variable not set.")
    else:
        run_migration()
