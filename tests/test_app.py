# Copyright (c) 2026 Stephanie Johnson
#
# Tests for webapp/app.py using Streamlit's AppTest harness.
#
# ForkDB and get_meals are mocked throughout: the DB layer already has its
# own integration tests in test_fork_db.py, so these tests only exercise
# app.py's own logic (login gating, validation, and rendering).
#
# Known gap: AppTest has no way to fire a real Plotly on_select click event.
# What CAN be verified is everything downstream of one: each plotly_chart's
# selection is stored under its own widget `key` in session_state, so seeding
# that key directly (mimicking what a real click would leave behind) exercises
# the exact same rendering path a real click would.

import json
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


def _set_date_range(at, start, end):
    if not at.date_input:
        at.run()  # first run instantiates the widgets
    at.date_input[0].set_value(start)
    at.date_input[1].set_value(end)
    at.run()


def _seed_point_selection(at, chart_key_prefix, start, end, x, **extra_point_fields):
    # Mirrors the shape a real Plotly on_select click leaves behind under a
    # plotly_chart's own widget key, confirmed empirically to round-trip
    # correctly through st.plotly_chart(..., key=...)'s return value.
    key = f"{chart_key_prefix}_{start.isoformat()}_{end.isoformat()}"
    point = {"x": x.isoformat(), "y": 0, "point_index": 0, "curve_number": 0, **extra_point_fields}
    at.session_state[key] = {"selection": {"points": [point]}}


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
    def test_dashboard_renders_calories_and_grams_charts(self, mock_get_meals):
        mock_get_meals.return_value = [
            _make_meal(
                "toast", cal=225.0, fat=1.0, protein=1.0, fiber=5.0,
                sugar=9.25, carb=28.0, servings_eaten=2.0, date_eaten=date(2026, 7, 5),
            ),
        ]

        at = _logged_in_app()
        at.run()

        self.assertEqual(len(at.exception), 0)
        # One chart for calories, one combined grouped-bar chart for the
        # four gram-based nutrients (protein/sugar/fiber/fat).
        self.assertEqual(len(at.get("plotly_chart")), 2)
        # Neither chart has a selection yet -> both prompts shown, no pie rendered.
        infos = [i.value for i in at.info]
        self.assertTrue(any("calories chart" in i for i in infos))
        self.assertTrue(any("Click a bar" in i for i in infos))
        self.assertEqual(len(at.subheader), 0)

    @patch("forkwise.display_meal_totals.get_meals")
    def test_grams_chart_uses_categorical_date_axis(self, mock_get_meals):
        # Regression test: Plotly auto-detects a date-like x column as a
        # continuous date axis, which for a grouped bar chart positions each
        # day's bars using real calendar spacing. If some day in the range
        # has no logged meals at all (a gap, as here on 7/31), that spacing
        # shifts and a bar can end up reporting the neighboring day when
        # clicked. Forcing a categorical axis (verified here via the actual
        # rendered figure spec, not just the app's own intent) is what
        # prevents that: every day gets an equal-width slot regardless of
        # gaps.
        mock_get_meals.return_value = [
            _make_meal(
                "toast", cal=225.0, fat=1.0, protein=1.0, fiber=5.0,
                sugar=9.25, carb=28.0, servings_eaten=2.0, date_eaten=date(2026, 7, 30),
            ),
            _make_meal(
                "salad", cal=150.0, fat=2.0, protein=3.0, fiber=4.0,
                sugar=1.0, carb=10.0, servings_eaten=1.0, date_eaten=date(2026, 8, 1),
            ),
        ]

        at = _logged_in_app()
        _set_date_range(at, date(2026, 7, 28), date(2026, 8, 3))

        self.assertEqual(len(at.exception), 0)
        charts = at.get("plotly_chart")
        self.assertEqual(len(charts), 2)
        grams_chart = charts[1]  # calories chart is rendered first, grams chart second
        spec = json.loads(grams_chart.proto.spec)
        self.assertEqual(spec["layout"]["xaxis"].get("type"), "category")

    @patch("forkwise.display_meal_totals.get_meals")
    def test_selecting_a_calories_point_renders_its_own_pie(self, mock_get_meals):
        mock_get_meals.return_value = [
            _make_meal(
                "toast", cal=225.0, fat=1.0, protein=1.0, fiber=5.0,
                sugar=9.25, carb=28.0, servings_eaten=2.0, date_eaten=date(2026, 7, 5),
            ),
        ]

        at = _logged_in_app()
        start, end = date(2026, 7, 1), date(2026, 7, 10)
        _set_date_range(at, start, end)
        _seed_point_selection(at, "chart_cal", start, end, x=date(2026, 7, 5))
        at.run()

        self.assertEqual(len(at.exception), 0)
        self.assertTrue(any("Calories on 2026-07-05" in s.value for s in at.subheader))
        # The grams chart has no selection of its own -> its placeholder still shows.
        self.assertTrue(any("Click a bar" in i.value for i in at.info))

    @patch("forkwise.display_meal_totals.get_meals")
    def test_selecting_a_gram_nutrient_uses_its_own_label(self, mock_get_meals):
        # The grams chart derives label/prop_key from PROP_LABELS via the
        # clicked bar's customdata, rather than a fixed per-chart label like
        # the calories chart uses. Seeding customdata exercises that lookup.
        mock_get_meals.return_value = [
            _make_meal(
                "toast", cal=225.0, fat=1.0, protein=1.0, fiber=5.0,
                sugar=9.25, carb=28.0, servings_eaten=2.0, date_eaten=date(2026, 7, 5),
            ),
        ]

        at = _logged_in_app()
        start, end = date(2026, 7, 1), date(2026, 7, 10)
        _set_date_range(at, start, end)
        _seed_point_selection(
            at, "chart_grams", start, end, x=date(2026, 7, 5), customdata=["sugar_list"]
        )
        at.run()

        self.assertEqual(len(at.exception), 0)
        self.assertTrue(any("Sugar (g) on 2026-07-05" in s.value for s in at.subheader))
        # The calories chart has no selection of its own -> its placeholder still shows.
        self.assertTrue(any("calories chart" in i.value for i in at.info))

    @patch("forkwise.display_meal_totals.get_meals")
    def test_both_pies_can_show_different_days_at_once(self, mock_get_meals):
        mock_get_meals.return_value = [
            _make_meal(
                "toast", cal=225.0, fat=1.0, protein=1.0, fiber=5.0,
                sugar=9.25, carb=28.0, servings_eaten=2.0, date_eaten=date(2026, 7, 5),
            ),
            _make_meal(
                "salad", cal=150.0, fat=2.0, protein=3.0, fiber=4.0,
                sugar=1.0, carb=10.0, servings_eaten=1.0, date_eaten=date(2026, 7, 6),
            ),
        ]

        at = _logged_in_app()
        start, end = date(2026, 7, 1), date(2026, 7, 10)
        _set_date_range(at, start, end)
        _seed_point_selection(at, "chart_cal", start, end, x=date(2026, 7, 5))
        _seed_point_selection(
            at, "chart_grams", start, end, x=date(2026, 7, 6), customdata=["fat_list"]
        )
        at.run()

        self.assertEqual(len(at.exception), 0)
        subheaders = [s.value for s in at.subheader]
        self.assertIn("Calories on 2026-07-05", subheaders)
        self.assertIn("Fat (g) on 2026-07-06", subheaders)

    @patch("forkwise.display_meal_totals.get_meals")
    def test_selection_does_not_carry_over_to_a_new_date_range(self, mock_get_meals):
        # Each chart's widget key includes the date range, so changing the
        # range gives it a brand new (unselected) widget rather than
        # reinterpreting the old selection against different data.
        mock_get_meals.return_value = [
            _make_meal(
                "toast", cal=225.0, fat=1.0, protein=1.0, fiber=5.0,
                sugar=9.25, carb=28.0, servings_eaten=2.0, date_eaten=date(2026, 7, 5),
            ),
        ]

        at = _logged_in_app()
        start, end = date(2026, 7, 1), date(2026, 7, 10)
        _set_date_range(at, start, end)
        _seed_point_selection(at, "chart_cal", start, end, x=date(2026, 7, 5))
        at.run()
        self.assertTrue(any("Calories on 2026-07-05" in s.value for s in at.subheader))

        _set_date_range(at, date(2026, 6, 1), date(2026, 6, 10))

        self.assertEqual(len(at.exception), 0)
        self.assertEqual(len(at.subheader), 0)
        self.assertTrue(any("calories chart" in i.value for i in at.info))


if __name__ == "__main__":
    unittest.main()
