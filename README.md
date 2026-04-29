# ForkWise: Nutrition tracking app

![Schema diagram](img/schema.png)

*Schema diagram made at [QuickDataBaseDiagrams.com](https://app.quickdatabasediagrams.com), using SQL_to_EDL.py from [FinTracker](https://github.com/stephlj/FinTrackr) (so inconsistency with actual db schema is possible!)*

## Inputs

User provides csv of meals eaten on particular dates. Format TBD.

Security: the database runs locally, nothing leaves your machine.

## Example usage

### Add meals

### View nutritional totals

## Getting started

One-time-only setup: initialize a new db:

```
config_path = "./src/forkwise/config.yml"
schema_path = "./src/forkwise/schema.sql"
python dbcommons.init_db $config_path $schema_path
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

Use `pytest` to run the tests. (For quick debugging: Add `-s` or `--capture=no` to print print statements to console.)