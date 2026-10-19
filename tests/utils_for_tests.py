import os
import yaml

from streamlit.testing.v1 import AppTest

TEST_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "test_config.yml")
TEST_DATA_PATH = os.path.join(os.path.dirname(__file__), "fixtures")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "forkwise", "schema.sql")
APP_PATH = os.path.join(os.path.dirname(__file__), "..", "webapp", "app.py")


def logged_in_app() -> AppTest:
    # AppTest for the webapp with login already done (skips the login form), mimicking
    # what login leaves in session_state, using the test config. Not yet run.
    with open(TEST_CONFIG_PATH, "r") as config_file:
        config = yaml.safe_load(config_file)
    at = AppTest.from_file(APP_PATH)
    at.session_state["logged_in"] = True
    at.session_state["username"] = "me"
    at.session_state["pw"] = "pw"
    at.session_state["db_name"] = config["db"]["db_name"]
    at.session_state["targets"] = config["targets"]
    return at
