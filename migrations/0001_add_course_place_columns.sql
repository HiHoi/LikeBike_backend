-- 코스 추천 장소 테이블에 주소와 설명 컬럼을 추가합니다.
ALTER TABLE course_recommendation_places
ADD COLUMN IF NOT EXISTS address_name VARCHAR(255),
ADD COLUMN IF NOT EXISTS description TEXT;
