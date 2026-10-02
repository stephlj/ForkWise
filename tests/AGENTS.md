# Conventions
- Tests use `unittest` and are run with `pytest`. Do not include an `if __name__ == __main__:` in testing files.
- Use `subTest("<informative full-sentence docstring>")` to test cases within a unit test.
- Testing coverage should be comprehensive without proliferating tests. Lots of tests does not mean comprehensive coverage.
- Tests should test code logic, business logic, and content of outputs, not just output shape and not tautologies.

# Structure
- Every module in `src` or `webapp` should have a testing module `/tests/test_module_name.py`.
- With some limited exceptions, every method or function should have a unit test, called `test_func_name()`.
- Unit tests for a module are collected in a subclass of `unittest` called `ModuleName(unittest.TestCase)`.
- Integration tests can be written in the same `unittest.TestCase` classes as related unit tests, if they need the same setup or teardown functionality (e.g. connetion to a test db instance)
- There are some manual tests detailed in the README for core API; ask me to run them if we've changed the core API.