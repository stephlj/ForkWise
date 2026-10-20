# Tests for webapp/views/add_data.py using Streamlit's AppTest harness.
#
# ForkDB and DataLoader are mocked: add_recipe_via_staging's db writes are
# tested in test_data_loader.py, so these tests check that what's entered in
# the form reaches add_recipe_via_staging intact.
#
# Written by Claude Code

import unittest

from unittest.mock import patch

from forkwise.fork_dataclasses import Ingredient

from utils_for_tests import logged_in_app


class TestAddData(unittest.TestCase):

    def _add_data_app(self):
        at = logged_in_app()
        at.switch_page("views/add_data.py")
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


    @patch("forkwise.data_loader.DataLoader")
    @patch("forkwise.fork_db.ForkDB")
    def test_add_data(self, mock_forkdb, mock_dataloader):
        db = mock_forkdb.return_value.__enter__.return_value
        db.list_all_units.return_value = ["unit", "tsp", "Tbsp", "c", "g", "oz", "lbs"]
        # Not in alphabetical order, so the page has to sort it. Every unit list
        # is different (unlike real data) so an ingredient shown with another's units would be caught.
        compatible_units = {
            "Soy milk": ["tsp", "Tbsp", "c"],
            "Butter": ["g", "oz", "lbs"],
            "almond butter": ["tsp", "Tbsp"],
            "Carrot": ["unit"],
            "Flour": ["oz", "lbs"],
        }
        db.list_compatible_units.return_value = compatible_units
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
            self._fill_ingr_row(at, 3, "Flour", 7.0, "oz")
            # Remove a filled middle row: the rows after it must keep their own values
            at.button(key="remove_1").click().run()
            self._click(at, "Save recipe")

            self.assertEqual(len(at.exception), 0)
            # db_name set at login (by logged_in_app here) is the one written to
            self.assertEqual(mock_dataloader.call_args.kwargs["db_name"], "test_fork_db")
            loader.add_recipe_via_staging.assert_called_once_with(
                ingredients=[
                    Ingredient(ingr_name="Soy milk", ingredient_amt=1.5, ingredient_units="c"),
                    Ingredient(ingr_name="Carrot", ingredient_amt=3.0, ingredient_units="unit"),
                    Ingredient(ingr_name="Flour", ingredient_amt=7.0, ingredient_units="oz"),
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
            # Sorted alphabetically ignoring case
            self.assertEqual(at.selectbox(key="ingr_0").options,
                             ["almond butter", "Butter", "Carrot", "Flour", "Soy milk"])
            # Sorting the names must not pair any name with another ingredient's units
            for ingr, units in compatible_units.items():
                at.selectbox(key="ingr_0").set_value(ingr).run()
                self.assertEqual(at.selectbox(key="units_0").options, units, ingr)
            # Lists are fetched once, not on every rerun
            db.list_compatible_units.assert_called_once()

        with self.subTest("Changing a row's ingredient keeps its unit only if the new ingredient allows it"):
            at = self._add_data_app()
            self._fill_ingr_row(at, 0, "Soy milk", 1.0, "tsp")
            at.selectbox(key="ingr_0").set_value("almond butter").run()
            self.assertEqual(at.selectbox(key="units_0").value, "tsp")
            at.selectbox(key="ingr_0").set_value("Butter").run()
            self.assertIsNone(at.selectbox(key="units_0").value)  # tsp isn't a weight unit

        loader.reset_mock()
        with self.subTest("The +/- buttons step by 0.5 for servings and amount per serving, and 0.1 for ingredient amounts"):
            at = self._add_data_app()
            self.assertEqual(at.number_input(key="servings").step, 0.5)
            self.assertEqual(at.number_input(key="servings_amt").step, 0.5)
            self.assertEqual(at.number_input(key="amt_0").step, 0.1)

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
