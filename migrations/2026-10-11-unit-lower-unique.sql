/*
Written by Claude

Make unit names unique ignoring case (no "c" and "C"), replacing
UNIQUE (unit, category, factor) on unit_conversions.
Applied to prod: 2026-10-11.

Run with: psql -v ON_ERROR_STOP=1 -d <db> -f <this file>

Safe to re-run: IF EXISTS / IF NOT EXISTS make the drop and create
do nothing if they've already been done.
*/

BEGIN;

/* Stop before changing anything if case duplicates exist; the index can't be built over them.
   Find them with:
   SELECT LOWER(unit), COUNT(*) FROM unit_conversions GROUP BY LOWER(unit) HAVING COUNT(*) > 1; */
DO $$
BEGIN
    IF EXISTS (
        SELECT LOWER(unit) FROM unit_conversions GROUP BY LOWER(unit) HAVING COUNT(*) > 1
    ) THEN
        RAISE EXCEPTION 'unit_conversions has unit names that differ only by case; remove duplicates first';
    END IF;
END $$;

ALTER TABLE unit_conversions DROP CONSTRAINT IF EXISTS unit_conversions_unit_category_factor_key;
CREATE UNIQUE INDEX IF NOT EXISTS unit_conversions_unit_lower_key ON unit_conversions (LOWER(unit));

COMMIT;
