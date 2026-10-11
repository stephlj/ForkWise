# Add recipes through the webapp

## Context
Right now the webapp only displays data. This adds a first data-loading feature: building a recipe from existing `pantry_items`.

Decisions so far:
- A separate "Add data" page.
- `servings_units` is a dropdown filled from `unit_conversions`.
- Ingredients are entered **row by row**. Each row's unit dropdown only lists units in the same category (weight, volume or unit) as the chosen pantry item, so a unit mismatch can't be submitted at all.

## 1. New queries in [fork_db.py](src/forkwise/fork_db.py)
These follow the `list_all_ingredients` pattern (simple methods on `ForkDB`).
- `list_all_units() -> List[str]`: units in `unit_conversions`, grouped by category and smallest to largest within each category (`ORDER BY category, factor`), e.g. `["unit", "tsp", "Tbsp", "c", ..., "g", "oz", "lbs"]`. Used for the serving-units dropdown.
  - Why not alphabetical: grouping keeps all units of one kind together, and size order is how people think about units. Alphabetical scatters them (`c`, `g`, `gallon`, `lbs`, ...).
- `list_compatible_units() -> dict[str, List[str]]`: maps **every** pantry item in the db to the units in its category, smallest to largest (same `factor` order as `list_all_units`), e.g. `{"Soy milk": ["tsp", "Tbsp", "c", ...], "Butter": [...], ...}`.
  - It doesn't depend on what the user has picked. It's a lookup table for all pantry items, built in one query that joins `pantry_items` → `unit_conversions` (matching the item's units, case-insensitive like `check_ingr_exist`) → `unit_conversions` (same category).
  - It's fetched once when the page loads. When the user picks an ingredient in a row, that row's unit dropdown immediately shows `compatible_units[ingredient]`, with no db call.
  - Tradeoff: querying per row instead would always be fresh, but would hit the db on every ingredient change. The table is small (pantry items × about 10 units per category), so loading it all at once is fine. Since this form can't add pantry items, it can't go stale while the page is open.
- Tests:
  - `list_all_units`: probably too simple to need a test, like `list_all_ingredients`.
  - `list_compatible_units`: standalone `test_list_compatible_units` in `test_data_getter.py`, where `ForkDB` queries are tested indirectly.
    - Seed it with new fixture pantry items that have distinctive names (one each in a weight, volume and "unit" unit, including a case mismatch such as "C" vs "c").
    - Assert the exact unit list, in order, for each seeded item. Only assert on the seeded items, so the result doesn't depend on test order.

## 2. Navigation ([app.py](webapp/app.py))
- After login, `st.navigation([st.Page(dashboard, title="Dashboard"), st.Page(add_data, title="Add data")])`.
- Both pages stay as functions in `app.py`, which keeps "app.py is the single entry point". Splitting into `webapp/pages/` can wait until the ingredient and meal loaders exist.

## 3. "Add data" page → recipe form
**Data loading:**
- On first load, open a `with ForkDB(...)` connection to fetch `list_all_units()` and `list_compatible_units()`.
  - The keys of `list_compatible_units()` are all pantry item names, which fill the ingredient dropdown. Its values fill each row's unit dropdown once an ingredient is picked.
- Cache these in `st.session_state`.

**Recipe header:**
- `st.text_input` for the recipe name.
- `st.number_input` for `servings` and `servings_amt` (minimum > 0).
- `st.selectbox` for `servings_units`.

**Ingredient rows:**
- `st.session_state` holds a list of row ids. "+ Add ingredient" appends one; each row's "✕" button removes it.
- Each row has three widgets keyed by its row id:
  - ingredient: `selectbox`, type-to-filter, options = pantry names
  - amount: `number_input`, minimum > 0
  - units: `selectbox`, options = `compatible_units[chosen ingredient]`
- When the ingredient changes and the old unit isn't valid for the new item, reset the unit.

**Why not `st.form`:**
- Forms hold back reruns until submit, so the unit list couldn't update when the ingredient changes.
- So each widget change reruns the page. That's cheap: only this page runs, and its lists are cached.
- Wrapping the ingredient rows in `@st.fragment` (so only that section reruns) is an option if the reruns feel sluggish. I won't do it up front.

**Save:**
- Check every field is filled in and the recipe name isn't blank. Checking that fields are filled counts as formatting, which `webapp/AGENTS.md` allows in the webapp.
- Build `List[Ingredient]` in row order.
- Call `DataLoader.add_recipe_via_staging(ingredients=..., name=..., servings=..., servings_amt=..., servings_units=...)` inside `with DataLoader(...)`.
- On success: show `st.success`, clear the form, and refresh the cached lists.
- On error: show `st.error`. This covers duplicate recipe names (`UniqueViolation`) and the duplicate-ingredient-set `ValueError`.

**Tradeoffs vs. an editable table:**
- More `app.py` code (bookkeeping for row ids)
- More vertical space
- But units are always valid, and each row is plain widgets, which AppTest can drive directly

## 4. Tests: making sure the recipe isn't scrambled
Two layers, each tested where it belongs. There's no test db in `test_app.py`.

**a. Webapp input → `add_recipe_via_staging` call (`test_app.py`, `DataLoader` and `ForkDB` mocked)**

One `test_add_recipe_page` with subtests:
- Entering 3 rows (including one added then removed) calls `add_recipe_via_staging` once.
  - Its `ingredients` are exactly the expected `[Ingredient(name, amt, units), ...]`, in order, with each name/amount/unit triple intact.
  - Its header arguments match exactly.
- Each row's unit dropdown lists only that ingredient's compatible units. Changing the ingredient changes the options.
- An incomplete row or a blank name shows an error, and `add_recipe_via_staging` is not called.
- An exception from `add_recipe_via_staging` is shown with `st.error`, and the entered data is kept.

**b. `add_recipe_via_staging` → db rows (`test_data_loader.py`, existing test db)**

New `test_add_recipe_via_staging`, building `Ingredient` objects in memory (the webapp's path, not the CSV path):
- Each `ingredients` row's (pantry item name, `ingredient_amt`, `ingredient_units`) comes back exactly as entered, with no rows mixed up between ingredients.
- The `recipes` row's `servings`, `servings_amt` and `servings_units` come back exactly as entered.
- Use new fixtures, not the existing ones (other tests may already have loaded those into the shared test db, depending on test order).
  - Add a new pantry item CSV with names no other fixture uses, loaded with `add_ingredients_from_csv`.
  - Use a recipe name no other test uses.
  - Assert only on rows for that recipe.

## Out of scope (later)
- Adding new pantry items from this form
- "Also add to pantry" (`add_recipe_to_pantry`)
- Meal and ingredient loaders

## Housekeeping
- Done: added the pros-and-cons rule to the "Planning" section of the root `AGENTS.md` (not committed).

## Verification
- `source .venv/bin/activate && pytest` (full suite, with local Postgres running). Report any failures.
- Manual check (Stephanie): `streamlit run webapp/app.py` against the test db only. Add a recipe, then confirm it on the dashboard or with `display_recipe_totals`.

## Git
- New worktree branch.
- Merge main into it, then ask before merging into main.
