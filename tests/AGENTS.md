# Conventions
- Tests use `unittest` and are run with `pytest`. Do not include an `if __name__ == "__main__":` in testing files.
- Use `with self.subTest("<full-sentence description of the case>")` to test cases within a unit test.
- Testing coverage should be comprehensive without proliferating tests. Lots of tests does not mean comprehensive coverage.
- Tests should test code logic, business logic, and content of outputs, not just output shape and not tautologies.
- Only connect to a test db when the test needs one (e.g. testing SQL or data loading/getting end to end). Otherwise mock the db layer (`unittest.mock`), as `test_app.py` does.

# Structure
- Every module in `src` or `webapp` should have a testing module `/tests/test_module_name.py`. Exceptions:
  - `fork_db.py`, `fork_init.py`, `add_fork_user.py`: tested indirectly through the `data_loader`/`data_getter` tests.
  - CLI wrapper scripts (`add_ingredients.py`, `add_recipe.py`, `add_meals.py`, `display_recipe_totals.py`): the functions they call are tested instead, and there's no additional business logic in the calling functions.
- Every method or function should have a unit test, called `test_func_name()`. Exceptions: private helpers, CLI `main()` wrappers, and trivial getters.
- Unit tests for a module are collected in a class `TestModuleName(unittest.TestCase)`.
- Integration tests can be written in the same `unittest.TestCase` classes as related unit tests, if they need the same setup or teardown functionality (e.g. connection to a test db instance)
- Reuse the existing test db setup/teardown (see `setUpClass`/`tearDownClass` in `test_data_getter.py`) and paths in `utils_for_tests.py`. Reuse data in `fixtures/` rather than writing new files when possible.
- `test_app.py` uses Streamlit's testing tool (`AppTest`), which can't simulate browser interactions like clicking on a plot. When a change depends on those, ask me to test it by hand.
- There are some manual tests detailed in the README for core API; ask me to run them if we've changed the core API.
