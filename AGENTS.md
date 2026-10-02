In all AGENTS.md files, "I", "me" and "my" mean Stephanie, the human developer; "you" means the agent.

Before working in `tests/` or `webapp/`, read the `AGENTS.md` in that directory.

# Conventions
- Prioritize code readability, not reducing line count, cleverness, etc.
- Use type hints in function definitions
- Add comments for design decisions or tradeoffs (e.g., "this implementation is faster but less accurate, acceptable here because ...")
- Do not proliferate little helper functions. Helper functions can be used to generalize code shared by at least two other calling functions, or for recursion, or if they make code more readable (moving core logic into helper functions makes code less readable, since the human has to scroll around to follow the logic).
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
- Forkwise depends on a package, `dbcommons`, that isn't on PyPI. **Running `uv sync --all-extras` uninstalls it.** After any `uv sync`, reinstall with `uv pip install "git+https://github.com/stephlj/DBCommons"`. This is also how to update it to a new version.
- Run tests with `pytest` (single test: `pytest tests/test_x.py::TestX::test_y`). Tests that create a test db (currently `test_data_loader.py`, `test_data_getter.py`) need the local Postgres server running.
- Launch the GUI with `streamlit run webapp/app.py`.

# Safety
- Never edit `src/forkwise/config.yml` (it points at my real db). Tests use `tests/fixtures/test_config.yml`.
- Never run the CLIs in `/src` against the real db, and never drop or modify any db other than the test db (`db_name` in `tests/fixtures/test_config.yml`).

# Finishing a task
- Run the full test suite before saying a task is complete, and report any failures.

# Planning
- When proposing a plan, include pros and cons and design tradeoffs.
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
    - List of `Meal` dataclasses in a date range: `get_meals_in_dates`. Each `Meal` has a list of Recipes, including recipe name and nutritional info per recipe per serving
    - `display_meal_totals.py` has utilities to calculate and plot daily nutritional totals
  - Additional utilities like `list_all_recipes` (lists all recipe names alphabetically), `list_all_ingredients` (list all names of what the db calls `pantry_items` but the UI calls `ingredients` - ie recipe components - alphabetically by name) in `fork_db.py`
