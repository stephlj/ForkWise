Always check subdirectories for additional `AGENTS.md` files specific to those directories.

# Conventions
- Prioritize code readability, not reducing line count, cleverness, etc.
- Use type hints in function definitions
- Add comments for design decisions or tradeoffs (e.g., "this implementation is faster but less accurate, acceptable here because ...")
- Do not proliferate little helper functions. Helper functions can be used to generalize code shared by at least two other calling functions, or for recursion, or if they make code more readable (moving core logic into helper functions makes code less readable, since the human has to scroll around to follow the logic).
- New code or code changes should always be accompanied by new tests or new sub-tests.
- Agents should develop on separate worktrees. Merge my main into your worktree branch and resolve conflicts there before merging into my main.
- Docstrings, comments and chat responses should be concise, not verbose. Minimize technical jargon and shorthand (like "no-ops"); when necessary, include a brief parenthetical definition.
- Any code you write wholesale (should mostly be in `webapp`), don't put "Copyright (c) Stephanie Johnson" at the top of the file. Put "Written by Claude" (or whichever product you are).
- Use context management where possible (e.g. for classes that establish db connections)

# Planning
- When proposing a plan, include pros and cons and design tradeoffs.
- Be concise. Plans do not need extensive repetition.
- Check that you're not proposing to reimplement functionality that exists elsewhere in the codebase. If existing code would work with some changes, propose those changes as part of the plan, rather than creating separate but nearly identical functionality.

# Structure
- Forkwise depends on a package, `dbcommons`, with special install instructions in the README. Follow these instructions if the environment needs to be updated with a new `dbcommons` version or recreated or similar.
- `fork_db.py` contains all SQL. `data_getter.py`, `data_loader.py` establish db connections via `ForkDB` objects but abstract the db schema (so only `ForkDB` needs to change if the schema changes).
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
    - List of Meals dataclasses in a date range: `get_meals_in_dates`. The Meals dataclass will have a list of Recipes, including recipe name and nutritional info per recipe per serving
    - `display_meal_totals.py` has utilities to calculate and plot daily nutritional totals
  - Additional utilities like `list_all_recipes` (lists all recipe names alphabetically), `list_all_ingredients` (list all names of what the db calls `pantry_items` but the UI calls `ingredients` - ie recipe components - alphabetically by name) in `fork_db.py`