# Tests for webapp/app.py (login and navigation) using Streamlit's AppTest harness.
# Each page in webapp/pages/ has its own test module.
#
# ForkDB and get_meals are mocked: the DB layer already has its own
# integration tests in test_data_loader.py and test_data_getter.py, so
# these tests only exercise app.py's own logic.
#
# Written by Claude Code

import unittest

from unittest.mock import MagicMock, patch
from streamlit.testing.v1 import AppTest

from forkwise.utils import DASHBOARD_TITLE

from utils_for_tests import APP_PATH, TEST_CONFIG_PATH


class TestApp(unittest.TestCase):

    def test_shows_login_form_when_logged_out(self):
        at = AppTest.from_file(APP_PATH)
        at.run()

        self.assertEqual(len(at.exception), 0)
        self.assertEqual(at.title[0].value, DASHBOARD_TITLE)
        self.assertEqual(len(at.text_input), 2)  # username, password
        self.assertEqual(len(at.date_input), 0)  # dashboard not shown yet

    @patch("forkwise.fork_db.ForkDB")
    def test_login_failure_shows_error(self, mock_forkdb):
        mock_forkdb.side_effect = Exception("bad credentials")

        at = AppTest.from_file(APP_PATH)
        at.run()
        at.text_input[0].set_value("nobody")
        at.text_input[1].set_value("wrong pw")
        at.button[0].click().run()

        self.assertEqual(len(at.error), 1)
        self.assertNotIn("logged_in", at.session_state)

    @patch("forkwise.utils.CONFIG_PATH", TEST_CONFIG_PATH)
    @patch("forkwise.display_meal_totals.get_meals")
    @patch("forkwise.fork_db.ForkDB")
    def test_login_success_reaches_dashboard(self, mock_forkdb, mock_get_meals):
        # get_meals is mocked here too, not just ForkDB: display_meal_totals
        # only binds its own `from forkwise.fork_db import ForkDB` name once,
        # the first time that module is ever imported in the process, so
        # patching forkwise.fork_db.ForkDB doesn't reliably reach a real call
        # made from inside get_meals() once the dashboard renders.
        mock_forkdb.return_value = MagicMock()
        mock_get_meals.return_value = []

        at = AppTest.from_file(APP_PATH)
        at.run()
        at.text_input[0].set_value("me")
        at.text_input[1].set_value("correct pw")
        at.button[0].click().run()

        self.assertEqual(len(at.exception), 0)
        self.assertTrue(at.session_state["logged_in"])
        # Pages connect with the db_name stored at login, so it must match the config's
        self.assertEqual(at.session_state["db_name"], "test_fork_db")
        self.assertEqual(mock_forkdb.call_args.kwargs["db_name"], "test_fork_db")
        self.assertEqual(len(at.date_input), 2)  # dashboard is the default page: start/end date now visible
