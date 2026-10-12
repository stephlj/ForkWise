# Tests for webapp/app.py using Streamlit's AppTest harness.
#
# ForkDB, DataLoader and get_meals are mocked throughout: the DB layer already has its
# own integration tests in test_data_loader.py and test_data_getter.py, so these tests only exercise
# app.py's own logic (login gating, validation, and rendering).
#
# Known gap: AppTest has no way to fire a real Plotly on_select click event.
# What CAN be verified is everything downstream of one: each plotly_chart's
# selection is stored under its own widget `key` in session_state, so seeding
# that key directly (mimicking what a real click would leave behind) exercises
# the exact same rendering path a real click would.
#
# Written by Claude Code

import json
import os
import unittest
import matplotlib

from datetime import date
from unittest.mock import MagicMock, patch
from streamlit.testing.v1 import AppTest
from streamlit.util import calc_hash

from forkwise.fork_dataclasses import FoodProps, Ingredient, Meal, Recipe
from forkwise.utils import DASHBOARD_TITLE

from utils_for_tests import TEST_CONFIG_PATH

matplotlib.use("Agg")

# Resolved against this file's location, per AppTest.from_file's own convention.
APP_PATH = os.path.join(os.path.dirname(__file__), "..", "webapp", "app.py")


class TestApp(unittest.TestCase):

    def _make_meal(self, name, cal, fat, protein, fiber, sugar, carb, servings_eaten, date_eaten):
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


    def _logged_in_app(self):
        at = AppTest.from_file(APP_PATH)
        at.session_state["logged_in"] = True
        at.session_state["username"] = "me"
        at.session_state["pw"] = "pw"
        return at


    def _set_date_range(self, at, start, end):
        if not at.date_input:
            at.run()  # first run instantiates the widgets
        at.date_input[0].set_value(start)
        at.date_input[1].set_value(end)
        at.run()


    def _seed_point_selection(self, at, chart_key_prefix, start, end, x, **extra_point_fields):
        # Mirrors the shape a real Plotly on_select click leaves behind under a
        # plotly_chart's own widget key, confirmed empirically to round-trip
        # correctly through st.plotly_chart(..., key=...)'s return value.
        key = f"{chart_key_prefix}_{start.isoformat()}_{end.isoformat()}"
        point = {"x": x.isoformat(), "y": 0, "point_index": 0, "curve_number": 0, **extra_point_fields}
        at.session_state[key] = {"selection": {"points": [point]}}

    def _add_data_app(self):
        # AppTest.switch_page only works for file-based pages, and app.py's
        # pages are functions. A function page's hash is calc_hash of its url
        # path (the function name), so set AppTest's (private) page hash directly.
        at = self._logged_in_app()
        at._page_hash = calc_hash("add_data")
        at.run()
        return at

    def _click(self, at, label):
        [b for b in at.button if b.label == label][0].click().run()

    def _fill_recipe_header(self, at, name):
        at.text_input(key="recipe_name").set_value(name)
        at.number_input(key="servings").set_value(2.0)
        at.number_input(key="servings_amt").set_value(1.0)
        at.selectbox(key="servings_units").set_value("c")

    def _fill_ingr_row(self, at, row_id, ingr, amt, units):
        # Run after picking the ingredient so the row's unit options update
        at.selectbox(key=f"ingr_{row_id}").set_value(ingr).run()
        at.number_input(key=f"amt_{row_id}").set_value(amt)
        at.selectbox(key=f"units_{row_id}").set_value(units).run()

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
        at = self._logged_in_app()
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

        at = self._logged_in_app()
        at.run()

        self.assertEqual(len(at.exception), 0)
        self.assertTrue(any("No meals logged" in i.value for i in at.info))

    @patch("forkwise.display_meal_totals.get_meals")
    def test_dashboard_renders_calories_and_grams_charts(self, mock_get_meals):
        mock_get_meals.return_value = [
            self._make_meal(
                "toast", cal=225.0, fat=1.0, protein=1.0, fiber=5.0,
                sugar=9.25, carb=28.0, servings_eaten=2.0, date_eaten=date(2026, 7, 5),
            ),
        ]

        at = self._logged_in_app()
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
            self._make_meal(
                "toast", cal=225.0, fat=1.0, protein=1.0, fiber=5.0,
                sugar=9.25, carb=28.0, servings_eaten=2.0, date_eaten=date(2026, 7, 30),
            ),
            self._make_meal(
                "salad", cal=150.0, fat=2.0, protein=3.0, fiber=4.0,
                sugar=1.0, carb=10.0, servings_eaten=1.0, date_eaten=date(2026, 8, 1),
            ),
        ]

        at = self._logged_in_app()
        self._set_date_range(at, date(2026, 7, 28), date(2026, 8, 3))

        self.assertEqual(len(at.exception), 0)
        charts = at.get("plotly_chart")
        self.assertEqual(len(charts), 2)
        grams_chart = charts[1]  # calories chart is rendered first, grams chart second
        spec = json.loads(grams_chart.proto.spec)
        self.assertEqual(spec["layout"]["xaxis"].get("type"), "category")

    @patch("forkwise.display_meal_totals.get_meals")
    @patch("forkwise.utils.CONFIG_PATH", TEST_CONFIG_PATH)
    def test_calories_chart_draws_target_line_matching_series_color(self, mock_get_meals):
        mock_get_meals.return_value = [
            self._make_meal(
                "toast", cal=225.0, fat=1.0, protein=1.0, fiber=5.0,
                sugar=9.25, carb=28.0, servings_eaten=2.0, date_eaten=date(2026, 7, 5),
            ),
        ]

        at = self._logged_in_app()
        at.run()

        self.assertEqual(len(at.exception), 0)
        cal_spec = json.loads(at.get("plotly_chart")[0].proto.spec)
        shapes = cal_spec["layout"]["shapes"]
        self.assertEqual(len(shapes), 1)
        self.assertEqual(shapes[0]["y0"], 2000)  # fixtures/test_config.yml targets.cal
        self.assertEqual(shapes[0]["line"]["dash"], "dash")
        self.assertEqual(shapes[0]["line"]["color"], cal_spec["data"][0]["marker"]["color"])

    @patch("forkwise.display_meal_totals.get_meals")
    @patch("forkwise.utils.CONFIG_PATH", TEST_CONFIG_PATH)
    def test_grams_chart_draws_target_lines_for_configured_nutrients_only(self, mock_get_meals):
        mock_get_meals.return_value = [
            self._make_meal(
                "toast", cal=225.0, fat=1.0, protein=1.0, fiber=5.0,
                sugar=9.25, carb=28.0, servings_eaten=2.0, date_eaten=date(2026, 7, 5),
            ),
        ]

        at = self._logged_in_app()
        at.run()

        self.assertEqual(len(at.exception), 0)
        grams_spec = json.loads(at.get("plotly_chart")[1].proto.spec)
        trace_colors = {trace["name"]: trace["marker"]["color"] for trace in grams_spec["data"]}
        shapes = grams_spec["layout"]["shapes"]

        # fixtures/test_config.yml only sets targets for protein_grams (60) and
        # fiber_grams (30); sugar and fat have no configured target, so should
        # draw no line.
        self.assertEqual(len(shapes), 2)
        shapes_by_y = {shape["y0"]: shape for shape in shapes}
        self.assertEqual(shapes_by_y[60]["line"]["color"], trace_colors["Protein (g)"])
        self.assertEqual(shapes_by_y[30]["line"]["color"], trace_colors["Fiber (g)"])
        for shape in shapes:
            self.assertEqual(shape["line"]["dash"], "dash")

    @patch("forkwise.display_meal_totals.get_meals")
    def test_selecting_a_calories_point_renders_its_own_pie(self, mock_get_meals):
        mock_get_meals.return_value = [
            self._make_meal(
                "toast", cal=225.0, fat=1.0, protein=1.0, fiber=5.0,
                sugar=9.25, carb=28.0, servings_eaten=2.0, date_eaten=date(2026, 7, 5),
            ),
        ]

        at = self._logged_in_app()
        start, end = date(2026, 7, 1), date(2026, 7, 10)
        self._set_date_range(at, start, end)
        self._seed_point_selection(at, "chart_cal", start, end, x=date(2026, 7, 5))
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
            self._make_meal(
                "toast", cal=225.0, fat=1.0, protein=1.0, fiber=5.0,
                sugar=9.25, carb=28.0, servings_eaten=2.0, date_eaten=date(2026, 7, 5),
            ),
        ]

        at = self._logged_in_app()
        start, end = date(2026, 7, 1), date(2026, 7, 10)
        self._set_date_range(at, start, end)
        self._seed_point_selection(
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
            self._make_meal(
                "toast", cal=225.0, fat=1.0, protein=1.0, fiber=5.0,
                sugar=9.25, carb=28.0, servings_eaten=2.0, date_eaten=date(2026, 7, 5),
            ),
            self._make_meal(
                "salad", cal=150.0, fat=2.0, protein=3.0, fiber=4.0,
                sugar=1.0, carb=10.0, servings_eaten=1.0, date_eaten=date(2026, 7, 6),
            ),
        ]

        at = self._logged_in_app()
        start, end = date(2026, 7, 1), date(2026, 7, 10)
        self._set_date_range(at, start, end)
        self._seed_point_selection(at, "chart_cal", start, end, x=date(2026, 7, 5))
        self._seed_point_selection(
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
            self._make_meal(
                "toast", cal=225.0, fat=1.0, protein=1.0, fiber=5.0,
                sugar=9.25, carb=28.0, servings_eaten=2.0, date_eaten=date(2026, 7, 5),
            ),
        ]

        at = self._logged_in_app()
        start, end = date(2026, 7, 1), date(2026, 7, 10)
        self._set_date_range(at, start, end)
        self._seed_point_selection(at, "chart_cal", start, end, x=date(2026, 7, 5))
        at.run()
        self.assertTrue(any("Calories on 2026-07-05" in s.value for s in at.subheader))

        self._set_date_range(at, date(2026, 6, 1), date(2026, 6, 10))

        self.assertEqual(len(at.exception), 0)
        self.assertEqual(len(at.subheader), 0)
        self.assertTrue(any("calories chart" in i.value for i in at.info))

    @patch("forkwise.utils.CONFIG_PATH", TEST_CONFIG_PATH)
    @patch("forkwise.data_loader.DataLoader")
    @patch("forkwise.fork_db.ForkDB")
    def test_add_recipe_page(self, mock_forkdb, mock_dataloader):
        db = mock_forkdb.return_value.__enter__.return_value
        db.list_all_units.return_value = ["unit", "tsp", "Tbsp", "c", "g", "oz", "lbs"]
        db.list_compatible_units.return_value = {
            "Soy milk": ["tsp", "Tbsp", "c"],
            "Butter": ["g", "oz", "lbs"],
            "Carrot": ["unit"],
            "Flour": ["g", "oz", "lbs"],
        }
        loader = mock_dataloader.return_value.__enter__.return_value

        with self.subTest("Rows entered (with one added then removed) reach add_recipe_via_staging intact and in order"):
            at = self._add_data_app()
            self._fill_recipe_header(at, "  Pancakes ")
            self._fill_ingr_row(at, 0, "Soy milk", 1.5, "c")
            self._click(at, "+ Add ingredient")
            self._fill_ingr_row(at, 1, "Butter", 2.0, "oz")
            self._click(at, "+ Add ingredient")
            self._fill_ingr_row(at, 2, "Carrot", 3.0, "unit")
            self._click(at, "+ Add ingredient")
            self._fill_ingr_row(at, 3, "Flour", 200.0, "g")
            # Remove a filled middle row: the rows after it must keep their own values
            at.button(key="remove_1").click().run()
            self._click(at, "Save recipe")

            self.assertEqual(len(at.exception), 0)
            self.assertEqual(mock_dataloader.call_args.kwargs["db_name"], "test_fork_db")
            loader.add_recipe_via_staging.assert_called_once_with(
                ingredients=[
                    Ingredient(ingr_name="Soy milk", ingredient_amt=1.5, ingredient_units="c"),
                    Ingredient(ingr_name="Carrot", ingredient_amt=3.0, ingredient_units="unit"),
                    Ingredient(ingr_name="Flour", ingredient_amt=200.0, ingredient_units="g"),
                ],
                name="Pancakes", servings=2.0, servings_amt=1.0, servings_units="c",
            )
            self.assertTrue(any("Pancakes" in s.value for s in at.success))
            # Form is cleared after a successful save
            self.assertEqual(at.text_input(key="recipe_name").value, "")
            self.assertIsNone(at.selectbox(key="ingr_0").value)
            self.assertEqual(len(at.selectbox), 3)  # serving units + one empty row's ingredient and units

        mock_forkdb.reset_mock()
        loader.reset_mock()
        with self.subTest("Each row's unit options are only the chosen ingredient's compatible units"):
            at = self._add_data_app()
            self.assertEqual(at.selectbox(key="units_0").options, [])
            self._fill_ingr_row(at, 0, "Soy milk", 1.0, "c")
            self.assertEqual(at.selectbox(key="units_0").options, ["tsp", "Tbsp", "c"])

            at.selectbox(key="ingr_0").set_value("Butter").run()
            self.assertEqual(at.selectbox(key="units_0").options, ["g", "oz", "lbs"])
            self.assertIsNone(at.selectbox(key="units_0").value)  # "c" isn't a weight unit
            # Ingredient dropdown lists pantry items alphabetically; lists are fetched once, not per rerun
            self.assertEqual(at.selectbox(key="ingr_0").options, ["Butter", "Carrot", "Flour", "Soy milk"])
            db.list_compatible_units.assert_called_once()

        loader.reset_mock()
        with self.subTest("An incomplete row shows an error and nothing is saved"):
            at = self._add_data_app()
            self._fill_recipe_header(at, "Pancakes")
            at.selectbox(key="ingr_0").set_value("Soy milk").run()  # no amount or units
            self._click(at, "Save recipe")

            self.assertEqual(len(at.error), 1)
            loader.add_recipe_via_staging.assert_not_called()

        with self.subTest("A blank recipe name shows an error and nothing is saved"):
            at = self._add_data_app()
            self._fill_recipe_header(at, "   ")
            self._fill_ingr_row(at, 0, "Soy milk", 1.0, "c")
            self._click(at, "Save recipe")

            self.assertEqual(len(at.error), 1)
            loader.add_recipe_via_staging.assert_not_called()

        loader.add_recipe_via_staging.side_effect = ValueError("A recipe with these ingredients already exists")
        with self.subTest("An error from add_recipe_via_staging is shown and the entered data is kept"):
            at = self._add_data_app()
            self._fill_recipe_header(at, "Pancakes")
            self._fill_ingr_row(at, 0, "Soy milk", 1.0, "c")
            self._click(at, "Save recipe")

            self.assertEqual(len(at.exception), 0)
            self.assertTrue(any("already exists" in e.value for e in at.error))
            self.assertEqual(at.text_input(key="recipe_name").value, "Pancakes")
            self.assertEqual(at.selectbox(key="ingr_0").value, "Soy milk")
            self.assertEqual(at.selectbox(key="units_0").value, "c")
