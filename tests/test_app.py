# Tests for webapp/app.py (login and navigation) using Streamlit's AppTest harness.
# Each page in webapp/views/ has its own test module.
#
# DataGetter is mocked: the db layer has its own integration tests in
# test_data_getter.py, so these tests only exercise app.py's own logic.
#
# Written by Claude Code

import unittest
import pandas as pd

from unittest.mock import patch
from streamlit.testing.v1 import AppTest

from forkwise.utils import DASHBOARD_TITLE

from utils_for_tests import APP_PATH, TEST_CONFIG_PATH


class TestApp(unittest.TestCase):

    @patch("forkwise.utils.CONFIG_PATH", TEST_CONFIG_PATH)
    @patch("forkwise.data_getter.DataGetter")
    def test_login(self, mock_dg_class):
        with self.subTest("When logged out, the login form is shown and the dashboard isn't."):
            at = AppTest.from_file(APP_PATH)
            at.run()
            self.assertEqual(len(at.exception), 0)
            self.assertEqual(at.title[0].value, DASHBOARD_TITLE)
            self.assertEqual(len(at.text_input), 2)  # username, password
            self.assertEqual(len(at.date_input), 0)

        for page in ["views/dashboard.py", "views/add_data.py"]:
            with self.subTest(f"When logged out, opening {page} shows the login form instead of the page."):
                at = AppTest.from_file(APP_PATH)
                at.run()
                at.switch_page(page).run()
                self.assertEqual(len(at.exception), 0)
                self.assertEqual(at.title[0].value, DASHBOARD_TITLE)
                self.assertEqual(len(at.text_input), 2)  # username, password
                mock_dg_class.assert_not_called()

        with self.subTest("Bad credentials show an error and stay logged out."):
            mock_dg_class.side_effect = Exception("bad credentials")
            at = AppTest.from_file(APP_PATH)
            at.run()
            at.text_input[0].set_value("nobody")
            at.text_input[1].set_value("wrong pw")
            at.button[0].click().run()
            self.assertEqual(len(at.error), 1)
            self.assertNotIn("logged_in", at.session_state)
            mock_dg_class.side_effect = None

        with self.subTest("Good credentials reach the dashboard and store the db name and targets from config."):
            # The dashboard uses DataGetter as a context manager
            mock_dg_class.return_value.__enter__.return_value.get_totals_in_dates.return_value = pd.DataFrame()
            at = AppTest.from_file(APP_PATH)
            at.run()
            at.text_input[0].set_value("me")
            at.text_input[1].set_value("correct pw")
            at.button[0].click().run()
            self.assertEqual(len(at.exception), 0)
            self.assertTrue(at.session_state["logged_in"])
            # Pages connect with the db_name stored at login, so it must match the config's
            self.assertEqual(at.session_state["db_name"], "test_fork_db")
            self.assertEqual(at.session_state["targets"], {"cal": 2000, "protein_grams": 60, "fiber_grams": 30})
            mock_dg_class.assert_any_call(user="me", pw="correct pw", db_name="test_fork_db")
            self.assertEqual(len(at.date_input), 2)  # dashboard is the default page: start/end date now visible
