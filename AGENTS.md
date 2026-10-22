In all AGENTS.md files, "I", "me" and "my" mean Stephanie, the human developer; "you" means the agent.

Before working in `tests/` or `webapp/`, read the `AGENTS.md` in that directory.

# Conventions
- Prioritize code readability, not reducing line count, cleverness, etc.
- Use type hints in function definitions
- Add comments for design decisions or tradeoffs (e.g., "this implementation is faster but less accurate, acceptable here because ...")
- Structure longer functions as a main function that reads as an outline of the overall flow, calling a few functions that each hold one conceptual chunk (e.g. "fetch the unit lists", "draw the ingredient rows", "validate and save"). A chunk should be big enough to make sense on its own, usually 5–30 lines. Don't split out one- or two-line helpers, or break a single idea across functions so the reader has to jump around to follow it. A helper with only one caller is fine if it's a real chunk.
- When chunks communicate through shared state rather than arguments and return values (e.g. `st.session_state`, instance attributes), say at the top of each function what it reads or sets, and which function is on the other side.
- New code or code changes should always be accompanied by new tests or new sub-tests.
- Docstrings, comments and chat responses should be concise, not verbose. Minimize technical jargon and shorthand (like "no-ops"); when necessary, include a brief parenthetical definition.
- New files you create (should mostly be in `webapp`): don't put "Copyright (c) Stephanie Johnson" at the top of the file. Put `Written by Claude` (or whichever product you are) instead.
- Use context managers (`with` statements) where possible (e.g. for classes that establish db connections)

# Git
- Develop on a separate worktree. Commit freely on your worktree branch.
- Before merging into main: merge main into your worktree branch and resolve conflicts there, then ask me before merging into main.
- Never push.

# Environment
- Activate the environment with `source .venv/bin/activate` before running anything (don't use `uv run`).
- In a worktree (no `.venv` of its own), activate the main checkout's environment and run with `PYTHONPATH=src`, since that environment otherwise imports `forkwise` from the main checkout, which may be on another branch. Don't reinstall packages in it without asking me; it's shared with my other work.
- Forkwise depends on a package, `dbcommons`, that isn't on PyPI; `pyproject.toml` installs it from GitHub and `uv.lock` pins its commit. Update it with `uv lock --upgrade-package dbcommons`.
- Run tests with `pytest` (single test: `pytest tests/test_x.py::TestX::test_y`). Tests that create a test db (currently `test_data_loader.py`, `test_data_getter.py`) need the local Postgres server running.
- Launch the GUI with `streamlit run webapp/app.py`.

# Safety
- Never edit `src/forkwise/config.yml` (it points at my real db). Tests use `tests/fixtures/test_config.yml`.
- Never run the CLIs in `/src` against the real db, and never drop or modify any db other than the test db (`db_name` in `tests/fixtures/test_config.yml`).
- `schema.sql` is only applied when a db is created. Tests build a fresh test db from it, so passing tests don't mean my prod db matches. Any change to `schema.sql` also needs a script in `migrations/` (see "Db migrations" in the README) that I'll run on prod. Never run migrations yourself.

# Finishing a task
- Run the full test suite before saying a task is complete, and report any failures.

# Planning
- When proposing a plan, include pros and cons and design tradeoffs.
- When asking me to choose between options, spell out the pros and cons of each option.
- Be concise. Plans do not need extensive repetition.
- Check that you're not proposing to reimplement functionality that exists elsewhere in the codebase. If existing code would work with some changes, propose those changes as part of the plan, rather than creating separate but nearly identical functionality.

# Structure
- `fork_db.py` contains all SQL queries (the schema is in `schema.sql`). `data_getter.py`, `data_loader.py` establish db connections via `ForkDB` objects but abstract the db schema (so only `ForkDB` needs to change if the schema changes).
- Tests are in `/tests`
- GUI is in `/webapp`; CLI is in `/src`
- Core API: in `/src`
  - Loading data into the database:
    - From csvs on disk: `add_ingredients_from_csv`, `add_recipe_from_csv`, `add_meals_via_staging` in `data_loader.py` (yes meals are currently special-cased); CLIs in `add_ingredients.py`, `add_recipe.py`, `add_meals.py`
    - From in-memory objects: `add_ingredients_via_staging`, `add_recipe_via_staging` (not available for meals)
    - Promote an existing `pantry_item` row to a recipe with `add_recipe_from_pantry`
    - Add an existing recipe as a `pantry_item` with `add_recipe_to_pantry`
  - Visualizing data:
    - Nutritional totals per serving for a recipe: `get_recipe_totals` in `data_getter.py` (CLI in `display_recipe_totals.py`)
    - Meals eaten in a date range: `get_totals_in_dates` in `data_getter.py` returns a DataFrame with one row per recipe eaten per date (`date_eaten`, `recipe_name`, and that row's nutritional totals for the servings eaten)
    - `display_meal_totals.py` has utilities to calculate and plot daily nutritional totals
  - Additional utilities like `list_all_recipes` (lists all recipe names alphabetically), `list_all_ingredients` (list all names of what the db calls `pantry_items` but the UI calls `ingredients` - ie recipe components - alphabetically by name) in `fork_db.py`
