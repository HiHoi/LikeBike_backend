-- 더 이상 사용하지 않는 quiz_options 테이블과 quizzes.correct_option_id 컬럼을 삭제합니다.
-- 이 스크립트는 0002_migrate_quiz_data.py가 성공적으로 실행된 후에 적용되어야 합니다.

-- 1. 외래 키 제약 조건이 있다면 먼저 삭제합니다.
--    (schema.sql 정의에 따라 quizzes.correct_option_id는 quiz_options.id를 참조했을 수 있습니다)
--    만약 제약조건 이름이 다르거나 없다면 이 부분은 실패할 수 있으며, 무시해도 됩니다.
ALTER TABLE quizzes DROP CONSTRAINT IF EXISTS quizzes_correct_option_id_fkey;

-- 2. 더 이상 사용하지 않는 컬럼을 삭제합니다.
ALTER TABLE quizzes DROP COLUMN IF EXISTS correct_option_id;

-- 3. 더 이상 사용하지 않는 테이블을 삭제합니다.
DROP TABLE IF EXISTS quiz_options;
