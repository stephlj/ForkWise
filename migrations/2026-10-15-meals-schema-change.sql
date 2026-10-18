/*
In conjunction with a new way to load meal info from db:

1. Change meals column names: date -> date_eaten, recipe_servings->servings_eaten
2. Ad unique constraint to meals table UNIQUE (date_eaten, recipe_id)

Applied to prod: 2026-10-18.

Run with: psql -v ON_ERROR_STOP=1 -d <db> -f <this file>

NOT safe to re-run.
*/

BEGIN;

/* Stop before changing anything if cases violating the new UNIQUE constraint on meals exist.
   Find them with:
   SELECT date, recipe_id, COUNT(*) FROM meals GROUP BY date, recipe_id HAVING COUNT(*) > 1; */
DO $$
BEGIN
    IF EXISTS (
        SELECT date, recipe_id, COUNT(*) FROM meals GROUP BY date, recipe_id HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION 'meals table has duplicate (date, recipe_id); remove duplicates first';
    END IF;
END $$;

ALTER TABLE meals RENAME COLUMN date TO date_eaten;
ALTER TABLE meals RENAME COLUMN recipe_servings TO servings_eaten;
/* Same name Postgres gives the unnamed constraint in schema.sql, so prod and new dbs match */
ALTER TABLE meals ADD CONSTRAINT meals_date_eaten_recipe_id_key UNIQUE (date_eaten, recipe_id);

COMMIT;