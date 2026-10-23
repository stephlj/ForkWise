/*
Small change: rename ingredient_id to pantry_id in ingredients table for clarity and 
to match the rest of the schema.

Applied to prod: 2026-10-23.

Did not run as a script; just recording here to document the change.
*/

ALTER TABLE ingredients RENAME COLUMN ingredient_id TO pantry_id;