# ForkWise: Nutrition tracking app

![Schema diagram](img/schema.png)

*Schema diagram made at [QuickDataBaseDiagrams.com](https://app.quickdatabasediagrams.com), using SQL_to_EDL.py from [FinTracker](https://github.com/stephlj/FinTrackr) (so inconsistency with actual db schema is possible!)*

## Inputs

MVP: User provides csv of meals eaten on particular dates. Format TBD.

v2: Extract recipes from URLs, get ingredient nutritional info from web search.

Security: the database runs locally, nothing leaves your machine.

## Example usage

### Add ingredients

Ingredients are loaded from a csv. The csv must have columns:

- `Name`: Item name, e.g. "black beans"
- `Unitary amount`: Amount for which calories, etc are calculated
- `Units`: Units for amount; e.g. `oz`
- `Calories`: Calories in the unitary amount of this ingredient
- `Fiber`: g of fiber in the unitary amount of this ingredient
- `Sugar`: g of sugar; includes white flour
- `Protien`: g
- `Fat`: g
- `Carbs`: g of carbohydrate, total (incl sugar and dietary fiber)
- `Animal`: bool, is any part of the ingredient derived from animal products or not.

E.g. for a can of black beans, `name` might be "black beans", `unitary amount` might be 24, `units` might be "oz". `Animal` would be True only if the beans were cooked in animal fat, for example.

### Add recipe

### Add meals

### View nutritional totals

## Getting started

One-time-only setup: initialize a new db:

```
config_path='./src/forkwise/config.yml'
schema_path='./src/forkwise/schema.sql'
python -m dbcommons.init_db '<owner_pw>' $config_path $schema_path
```

## Dev

This package uses `uv` for package and virtual environment management, based on the very helpful tutorials at [Sebastia Agramunt Puig's blog](https://agramunt.me/posts/python-virtual-environments-with-uv/).

Create the environment with `uv venv .venv` and then run `uv sync --all-extras` (to get developer extras).

Activate with `source .venv/bin/activate`.

Add dependencies with `uv add <package1> <package2>`. If you get an error that looks like:

```
No solution found when resolving dependencies:
  ╰─▶ Because there are no versions of unittest and your project depends on unittest, we can conclude that your project's requirements are
      unsatisfiable.
```
you already have the package (e.g. it's a package that comes with all python installs). I love `uv` but its error messages can be quite unhelpful.

To update to the latest version of the DBCommons repo, run:
```
uv pip install "git+https://github.com/stephlj/DBCommons"
```

Use `pytest` to run the tests. (For quick debugging: Add `-s` or `--capture=no` to print print statements to console.)