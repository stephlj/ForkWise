# Tests for webapp/pages/dashboard.py using Streamlit's AppTest harness.
#
# DataGetter is mocked throughout: the db layer has its own integration tests
# in test_data_getter.py, so these tests only exercise the page's own logic
# (validation and rendering).
#
# Known gap: AppTest has no way to fire a real Plotly on_select click event.
# What CAN be verified is everything downstream of one: each plotly_chart's
# selection is stored under its own widget `key` in session_state, so seeding
# that key directly (mimicking what a real click would leave behind) exercises
# the same rendering path a real click would.
#
# Written by Claude Code

import base64
import json
import unittest
import matplotlib
import numpy as np
import pandas as pd

from datetime import date
from unittest.mock import patch
from streamlit.testing.v1 import AppTest

from utils_for_tests import logged_in_app

matplotlib.use("Agg")

# Two recipes on 7/5 and one on 7/6, so daily totals differ from per-recipe values.
# Columns match what DataGetter.get_totals_in_dates returns.
MEALS_DF = pd.DataFrame({
    "date_eaten": [date(2026, 7, 5), date(2026, 7, 5), date(2026, 7, 6)],
    "recipe_name": ["toast", "salad", "toast"],
    "cal": [225.0, 150.0, 100.0],
    "fat_grams": [1.0, 2.0, 0.5],
    "protein_grams": [1.0, 3.0, 0.5],
    "fiber_grams": [5.0, 4.0, 2.5],
    "sugar_grams": [9.25, 1.0, 4.0],
    "carb_grams": [28.0, 10.0, 14.0],
    "animal": [0, 0, 0],
    "white_flour": [1, 0, 1],
})


class TestDashboard(unittest.TestCase):

    def _set_meals(self, mock_dg_class, meals_df: pd.DataFrame) -> None:
        # The page uses DataGetter as a context manager
        mock_dg_class.return_value.__enter__.return_value.get_totals_in_dates.return_value = meals_df

    def _set_date_range(self, at: AppTest, start: date, end: date) -> None:
        if not at.date_input:
            at.run()  # first run instantiates the widgets
        at.date_input[0].set_value(start)
        at.date_input[1].set_value(end)
        at.run()

    def _seed_point_selection(self, at: AppTest, chart_key_prefix: str, start: date, end: date, x: date,
                              **extra_point_fields) -> None:
        # Mirrors the shape a real Plotly on_select click leaves behind under a
        # plotly_chart's own widget key.
        key = f"{chart_key_prefix}_{start.isoformat()}_{end.isoformat()}"
        point = {"x": x.isoformat(), "y": 0, "point_index": 0, "curve_number": 0, **extra_point_fields}
        at.session_state[key] = {"selection": {"points": [point]}}

    def _plotted_values(self, encoded: dict | list) -> list:
        # Plotly stores numeric arrays in the chart spec as base64-encoded bytes
        if isinstance(encoded, list):
            return encoded
        return np.frombuffer(base64.b64decode(encoded["bdata"]), dtype=encoded["dtype"]).tolist()

    @patch("forkwise.data_getter.DataGetter")
    def test_dashboard(self, mock_dg_class):
        start, end = date(2026, 7, 1), date(2026, 7, 10)

        with self.subTest("A start date after the end date shows an error without querying the db."):
            at = logged_in_app()
            at.run()  # default start == end is valid, so this queries once
            mock_dg_class.reset_mock()
            self._set_date_range(at, end, start)
            self.assertEqual(len(at.error), 1)
            mock_dg_class.assert_not_called()

        with self.subTest("No meals in the date range shows a message instead of charts."):
            self._set_meals(mock_dg_class, pd.DataFrame())
            at = logged_in_app()
            at.run()
            self.assertEqual(len(at.exception), 0)
            self.assertTrue(any("No meals logged" in i.value for i in at.info))
            self.assertEqual(len(at.get("plotly_chart")), 0)

        with self.subTest("Meals in the chosen date range are queried and drawn as two charts with no pies yet."):
            self._set_meals(mock_dg_class, MEALS_DF)
            at = logged_in_app()
            self._set_date_range(at, start, end)
            self.assertEqual(len(at.exception), 0)
            mock_dg_class.return_value.__enter__.return_value.get_totals_in_dates.assert_called_with(
                date_range=[start, end])
            self.assertEqual(len(at.get("plotly_chart")), 2)
            # Columns are start/end dates, then (chart, pie) for calories and for grams.
            # Each chart gets twice the width of its pie.
            chart_pie_weights = [round(c.weight, 2) for c in at.columns[2:]]
            self.assertEqual(chart_pie_weights, [0.67, 0.33, 0.67, 0.33])
            infos = [i.value for i in at.info]
            self.assertTrue(any("calories chart" in i for i in infos))
            self.assertTrue(any("Click a bar" in i for i in infos))
            self.assertEqual(len(at.subheader), 0)

        with self.subTest("Both charts' pies can show different days at once."):
            at = logged_in_app()
            self._set_date_range(at, start, end)
            self._seed_point_selection(at, "chart_cal", start, end, x=date(2026, 7, 5))
            self._seed_point_selection(at, "chart_grams", start, end, x=date(2026, 7, 6), customdata=["fat_grams"])
            at.run()
            self.assertEqual(len(at.exception), 0)
            subheaders = [s.value for s in at.subheader]
            self.assertIn("Calories on 2026-07-05", subheaders)
            self.assertIn("Fat (g) on 2026-07-06", subheaders)

        with self.subTest("Changing the date range clears a chart's selection."):
            # Each chart's widget key includes the date range, so a new range gives
            # it a new (unselected) widget rather than reusing the old selection.
            at = logged_in_app()
            self._set_date_range(at, start, end)
            self._seed_point_selection(at, "chart_cal", start, end, x=date(2026, 7, 5))
            at.run()
            self.assertTrue(any("Calories on 2026-07-05" in s.value for s in at.subheader))
            self._set_date_range(at, date(2026, 7, 2), date(2026, 7, 9))
            self.assertEqual(len(at.exception), 0)
            self.assertEqual(len(at.subheader), 0)
            self.assertTrue(any("calories chart" in i.value for i in at.info))

    @patch("forkwise.data_getter.DataGetter")
    def test_calories_chart(self, mock_dg_class):
        self._set_meals(mock_dg_class, MEALS_DF)
        at = logged_in_app()
        at.run()
        self.assertEqual(len(at.exception), 0)
        cal_spec = json.loads(at.get("plotly_chart")[0].proto.spec)

        with self.subTest("There is one point per day, at that day's total calories."):
            self.assertEqual(cal_spec["data"][0]["x"], ["2026-07-05", "2026-07-06"])
            self.assertEqual(self._plotted_values(cal_spec["data"][0]["y"]), [375.0, 100.0])

        with self.subTest("The calorie target is a dashed line in the same color as the points."):
            shapes = cal_spec["layout"]["shapes"]
            self.assertEqual(len(shapes), 1)
            self.assertEqual(shapes[0]["y0"], 2000)  # fixtures/test_config.yml targets.cal
            self.assertEqual(shapes[0]["line"]["dash"], "dash")
            self.assertEqual(shapes[0]["line"]["color"], cal_spec["data"][0]["marker"]["color"])

    @patch("forkwise.data_getter.DataGetter")
    def test_grams_chart(self, mock_dg_class):
        self._set_meals(mock_dg_class, MEALS_DF)
        at = logged_in_app()
        at.run()
        self.assertEqual(len(at.exception), 0)
        grams_spec = json.loads(at.get("plotly_chart")[1].proto.spec)  # calories chart is first
        traces = {trace["name"]: trace for trace in grams_spec["data"]}

        with self.subTest("There is one series per gram-based nutrient (no carbs), each at that day's totals."):
            self.assertEqual(set(traces), {"Protein (g)", "Sugar (g)", "Fiber (g)", "Fat (g)"})
            self.assertEqual(self._plotted_values(traces["Fiber (g)"]["y"]), [9.0, 2.5])
            self.assertEqual(self._plotted_values(traces["Sugar (g)"]["y"]), [10.25, 4.0])

        with self.subTest("Each bar carries its nutrient's column name, for tracing a click back to it."):
            self.assertEqual(traces["Fiber (g)"]["customdata"], [["fiber_grams"], ["fiber_grams"]])

        with self.subTest("The date axis is categorical, so clicked bars report their own date."):
            # Regression test: with a continuous date axis, a day with no meals
            # shifts the bar spacing and a click can report the neighboring day.
            self.assertEqual(grams_spec["layout"]["xaxis"].get("type"), "category")

        with self.subTest("Only nutrients with a target get a dashed target line, in that nutrient's color."):
            # fixtures/test_config.yml has targets for protein (60) and fiber (30) only
            shapes = grams_spec["layout"]["shapes"]
            self.assertEqual(len(shapes), 2)
            shapes_by_y = {shape["y0"]: shape for shape in shapes}
            self.assertEqual(shapes_by_y[60]["line"]["color"], traces["Protein (g)"]["marker"]["color"])
            self.assertEqual(shapes_by_y[30]["line"]["color"], traces["Fiber (g)"]["marker"]["color"])
            for shape in shapes:
                self.assertEqual(shape["line"]["dash"], "dash")

    @patch("forkwise.display_meal_totals.plot_pie")
    @patch("forkwise.data_getter.DataGetter")
    def test_breakdown_pie(self, mock_dg_class, mock_plot_pie):
        self._set_meals(mock_dg_class, MEALS_DF)
        start, end = date(2026, 7, 1), date(2026, 7, 10)

        with self.subTest("Selecting a calories point shows that day's calories by recipe."):
            mock_plot_pie.reset_mock()
            at = logged_in_app()
            self._set_date_range(at, start, end)
            self._seed_point_selection(at, "chart_cal", start, end, x=date(2026, 7, 5))
            at.run()
            self.assertEqual(len(at.exception), 0)
            self.assertIn("Calories on 2026-07-05", [s.value for s in at.subheader])
            mock_plot_pie.assert_called_once_with(prop_totals=[225.0, 150.0], recipe_names=["toast", "salad"])
            # The grams chart has no selection of its own, so its placeholder still shows
            self.assertTrue(any("Click a bar" in i.value for i in at.info))

        with self.subTest("Selecting a bar shows that bar's nutrient for that day."):
            mock_plot_pie.reset_mock()
            at = logged_in_app()
            self._set_date_range(at, start, end)
            self._seed_point_selection(at, "chart_grams", start, end, x=date(2026, 7, 6), customdata=["sugar_grams"])
            at.run()
            self.assertEqual(len(at.exception), 0)
            self.assertIn("Sugar (g) on 2026-07-06", [s.value for s in at.subheader])
            mock_plot_pie.assert_called_once_with(prop_totals=[4.0], recipe_names=["toast"])
            self.assertTrue(any("calories chart" in i.value for i in at.info))

        with self.subTest("A selected date with no meals shows a warning instead of a pie."):
            mock_plot_pie.reset_mock()
            at = logged_in_app()
            self._set_date_range(at, start, end)
            self._seed_point_selection(at, "chart_cal", start, end, x=date(2026, 7, 8))
            at.run()
            self.assertEqual(len(at.warning), 1)
            mock_plot_pie.assert_not_called()
