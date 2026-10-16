/*
In conjunction with a new way to load meal info from db:

1. Change meals column name: date -> date_eaten
2. Ad unique constraint to meals table UNIQUE (date_eaten, recipe_id)

Applied to prod: 2026-10-15.

Run with: psql -v ON_ERROR_STOP=1 -d <db> -f <this file>

Safe to re-run: IF EXISTS / IF NOT EXISTS make the drop and create
do nothing if they've already been done.
*/

BEGIN;

/* Stop before changing anything if cases violating the new UNIQUE constraint on meals exist.
   Find them with:
   SELECT date, recipe_id, COUNT(*) FROM meals GROUP BY date, recipe_id HAVING COUNT(*) > 1; */
DO $$
BEGIN
    IF EXISTS (
        SELECT date, recipe_id, COUNT(*) FROM meals GROUP BY date, recipe_id HAVING COUNT(*) > 1;
    ) THEN
        RAISE EXCEPTION 'meals table has duplicate (date, recipe_id); remove duplicates first';
    END IF;
END $$;

ALTER TABLE meals RENAME COLUMN date TO date_eaten;
ALTER TABLE meals ADD CONSTRAINT date_eaten_recipe_id_key UNIQUE (date_eaten, recipe_id)

COMMIT;