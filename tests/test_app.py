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
    @patch("forkwise.fork_db.ForkDB")
    @patch("forkwise.data_getter.DataGetter")
    def test_login(self, mock_dg_class, mock_forkdb_class):
        # The dashboard uses DataGetter, and the add-recipe page uses ForkDB, as context managers
        mock_dg_class.return_value.__enter__.return_value.get_totals_in_dates.return_value = pd.DataFrame()
        db = mock_forkdb_class.return_value.__enter__.return_value
        db.list_all_units.return_value = []
        db.list_compatible_units.return_value = {}

        with self.subTest("When logged out, the login form is shown and the dashboard isn't."):
            at = AppTest.from_file(APP_PATH)
            at.run()
            self.assertEqual(len(at.exception), 0)
            self.assertEqual(at.title[0].value, DASHBOARD_TITLE)
            self.assertEqual(len(at.text_input), 2)  # username, password
            self.assertEqual(len(at.date_input), 0)

        # A db call each page makes when it opens, to check that it did open
        page_db_calls = {
            "views/dashboard.py": mock_dg_class.return_value.__enter__.return_value.get_totals_in_dates,
            "views/add_data.py": db.list_all_units,
        }
        for page, page_db_call in page_db_calls.items():
            with self.subTest(f"When logged out, opening {page} shows the login form instead of the page."):
                # switch_page can only open pages that are currently registered, and when
                # logged out only the login page is. So open the page while logged in, then
                # log out: the next run requests a page that isn't registered, as when a
                # logged-out browser opens the page's URL.
                at = AppTest.from_file(APP_PATH)
                at.run()
                at.text_input[0].set_value("me")
                at.text_input[1].set_value("correct pw")
                at.button[0].click().run()
                page_db_call.reset_mock()
                at.switch_page(page).run()
                page_db_call.assert_called()
                at.session_state["logged_in"] = False
                mock_dg_class.reset_mock()
                mock_forkdb_class.reset_mock()
                at.run()
                self.assertEqual(len(at.exception), 0)
                self.assertEqual(at.title[0].value, DASHBOARD_TITLE)
                self.assertEqual(len(at.text_input), 2)  # username, password
                mock_dg_class.assert_not_called()
                mock_forkdb_class.assert_not_called()

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

        with self.subTest("Good credentials reach the dashboard and store the db name, targets and checked gram nutrients from config."):
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
            # The test config also lists cal, which isn't in grams, so it's dropped
            self.assertEqual(at.session_state["gram_nutrients"],
                             ["protein_grams", "sugar_grams", "fiber_grams", "fat_grams"])
            mock_dg_class.assert_any_call(user="me", pw="correct pw", db_name="test_fork_db")
            self.assertEqual(len(at.date_input), 2)  # dashboard is the default page: start/end date now visible
