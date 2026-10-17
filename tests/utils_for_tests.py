import os

from streamlit.testing.v1 import AppTest

TEST_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "test_config.yml")
TEST_DATA_PATH = os.path.join(os.path.dirname(__file__), "fixtures")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "forkwise", "schema.sql")
APP_PATH = os.path.join(os.path.dirname(__file__), "..", "webapp", "app.py")


def logged_in_app() -> AppTest:
    # AppTest for the webapp with login already done (skips the login form). Not yet run.
    at = AppTest.from_file(APP_PATH)
    at.session_state["logged_in"] = True
    at.session_state["username"] = "me"
    at.session_state["pw"] = "pw"
    at.session_state["db_name"] = "my_db"
    return at
