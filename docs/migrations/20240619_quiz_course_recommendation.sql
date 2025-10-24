BEGIN;

CREATE TABLE IF NOT EXISTS course_recommendation_places (
    id SERIAL PRIMARY KEY,
    recommendation_id INTEGER NOT NULL REFERENCES course_recommendations (id) ON DELETE CASCADE,
    sequence_order INTEGER NOT NULL CHECK (sequence_order >= 1),
    name VARCHAR(255) NOT NULL,
    latitude DECIMAL(9, 6),
    longitude DECIMAL(9, 6),
    photo_url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

DO
$$
BEGIN
    IF to_regclass('public.course_recommendation_points') IS NOT NULL THEN
        EXECUTE $$
            INSERT INTO course_recommendation_places (recommendation_id, sequence_order, name, latitude, longitude, photo_url, created_at)
            SELECT
                c.recommendation_id,
                p.sequence_order,
                p.name,
                p.latitude,
                p.longitude,
                p.photo_url,
                p.created_at
            FROM course_recommendation_points AS p
            JOIN course_recommendation_courses AS c ON p.course_id = c.id
            WHERE NOT EXISTS (
                SELECT 1
                FROM course_recommendation_places AS existing
                WHERE existing.recommendation_id = c.recommendation_id
                  AND existing.sequence_order = p.sequence_order
                  AND existing.name = p.name
            )
            ORDER BY c.recommendation_id, p.sequence_order, p.id;
        $$;
        EXECUTE 'DROP TABLE course_recommendation_points';
    END IF;
END
$$;

DO
$$
BEGIN
    IF to_regclass('public.course_recommendation_courses') IS NOT NULL THEN
        EXECUTE 'DROP TABLE course_recommendation_courses';
    END IF;
END
$$;

COMMIT;
