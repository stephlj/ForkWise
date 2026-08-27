# Copyright (c) 2026 Stephanie Johnson
#
# Tests for webapp/app.py using Streamlit's AppTest harness.
#
# ForkDB and get_meals are mocked throughout: the DB layer already has its
# own integration tests in test_fork_db.py, so these tests only exercise
# app.py's own logic (login gating, validation, and rendering).
#
# Known gap: AppTest has no way to simulate a real click on a Plotly chart,
# so the actual "click a point -> selection appears in session_state" wiring
# is untested here. What IS tested is everything downstream of that: given a
# selection in session_state (however it got there), does the pie panel
# render correctly.

import os
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

import matplotlib

matplotlib.use("Agg")

from streamlit.testing.v1 import AppTest

from forkwise.fork_dataclasses import FoodProps, Meal, Recipe

# Resolved against this file's location, per AppTest.from_file's own convention.
APP_PATH = os.path.join(os.path.dirname(__file__), "..", "webapp", "app.py")


def _make_meal(name, cal, fat, protein, fiber, sugar, carb, servings_eaten, date_eaten):
    return Meal(
        recipes=[
            Recipe(
                name=name,
                servings=1.0,
                servings_amt=1.0,
                servings_units="unit",
                props=FoodProps(
                    cal=cal,
                    fat_grams=fat,
                    protein_grams=protein,
                    fiber_grams=fiber,
                    sugar_grams=sugar,
                    carb_grams=carb,
                    white_flour=False,
                    animal=False,
                ),
            )
        ],
        servings_eaten=[servings_eaten],
        date_eaten=date_eaten,
    )


def _logged_in_app():
    at = AppTest.from_file(APP_PATH)
    at.session_state["logged_in"] = True
    at.session_state["username"] = "me"
    at.session_state["pw"] = "pw"
    return at


class TestApp(unittest.TestCase):

    def test_shows_login_form_when_logged_out(self):
        at = AppTest.from_file(APP_PATH)
        at.run()

        self.assertEqual(len(at.exception), 0)
        self.assertEqual(at.title[0].value, "ForkWise Dashboard")
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
        self.assertEqual(len(at.date_input), 2)  # start/end date now visible

    @patch("forkwise.display_meal_totals.get_meals")
    def test_start_after_end_shows_error_without_querying(self, mock_get_meals):
        at = _logged_in_app()
        at.run()  # default start == end is valid, so this calls get_meals once
        mock_get_meals.reset_mock()

        at.date_input[0].set_value(date(2026, 7, 10))
        at.date_input[1].set_value(date(2026, 7, 1))
        at.run()

        self.assertEqual(len(at.error), 1)
        mock_get_meals.assert_not_called()

    @patch("forkwise.display_meal_totals.get_meals")
    def test_no_meals_shows_info_message(self, mock_get_meals):
        mock_get_meals.return_value = []

        at = _logged_in_app()
        at.run()

        self.assertEqual(len(at.exception), 0)
        self.assertTrue(any("No meals logged" in i.value for i in at.info))

    @patch("forkwise.display_meal_totals.get_meals")
    def test_dashboard_renders_five_charts(self, mock_get_meals):
        mock_get_meals.return_value = [
            _make_meal(
                "toast", cal=225.0, fat=1.0, protein=1.0, fiber=5.0,
                sugar=9.25, carb=28.0, servings_eaten=2.0, date_eaten=date(2026, 7, 5),
            ),
        ]

        at = _logged_in_app()
        at.run()

        self.assertEqual(len(at.exception), 0)
        self.assertEqual(len(at.get("plotly_chart")), 5)
        # No selection made yet -> prompt shown, no pie rendered.
        self.assertTrue(any("Click a point" in i.value for i in at.info))

    @patch("forkwise.display_meal_totals.get_meals")
    def test_selecting_a_point_renders_pie_breakdown(self, mock_get_meals):
        # AppTest can't fire a real Plotly on_select event, but the pie panel
        # is driven entirely by st.session_state["selected"], so seeding it
        # directly exercises the same rendering path a real click would.
        mock_get_meals.return_value = [
            _make_meal(
                "toast", cal=225.0, fat=1.0, protein=1.0, fiber=5.0,
                sugar=9.25, carb=28.0, servings_eaten=2.0, date_eaten=date(2026, 7, 5),
            ),
        ]

        at = _logged_in_app()
        at.run()  # establishes st.session_state["last_range"] for the default dates
        # Seeding "selected" only after last_range is already set matches how
        # a real click behaves: dashboard() clears "selected" whenever the
        # current date range doesn't match the last-seen one, which is only
        # true on this app's very first render of a session.
        at.session_state["selected"] = {
            "date": date(2026, 7, 5),
            "prop_key": "cal_list",
            "label": "Calories",
        }
        at.run()

        self.assertEqual(len(at.exception), 0)
        self.assertTrue(any("Calories on 2026-07-05" in s.value for s in at.subheader))

    @patch("forkwise.display_meal_totals.get_meals")
    def test_selection_cleared_when_date_range_changes(self, mock_get_meals):
        mock_get_meals.return_value = [
            _make_meal(
                "toast", cal=225.0, fat=1.0, protein=1.0, fiber=5.0,
                sugar=9.25, carb=28.0, servings_eaten=2.0, date_eaten=date(2026, 7, 5),
            ),
        ]

        at = _logged_in_app()
        at.run()  # establishes st.session_state["last_range"] for the default dates
        at.session_state["selected"] = {
            "date": date(2026, 7, 5),
            "prop_key": "cal_list",
            "label": "Calories",
        }
        at.run()
        at.date_input[0].set_value(date(2026, 6, 1))
        at.run()

        self.assertEqual(len(at.exception), 0)
        self.assertIsNone(at.session_state["selected"])


if __name__ == "__main__":
    unittest.main()
