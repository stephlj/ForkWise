import unittest

from dataclasses import fields

from forkwise.utils import (calc_totals_per_serving, calc_totals_eaten, parse_gram_nutrients,
                            DEFAULT_GRAM_NUTRIENTS, PROPS_DISPLAY_NAMES)
from forkwise.fork_dataclasses import FoodProps, Recipe

class TestUtils(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Both calc_totals_per_serving and calc_totals_eaten take a FoodProps item;
        # they shouldn't be the same but for the sake of testing, it's ok if they are:
        cls.test_props = FoodProps(
            cal=219,
            fat_grams=4,
            protein_grams=7,
            fiber_grams=27,
            sugar_grams=3.5,
            carb_grams=4.5,
            white_flour=True,
            animal=False
        )

        cls.r = Recipe(name="test_recipe",
                   servings=2.5,
                   servings_amt=0.25,
                   servings_units="c",
                   props=cls.test_props)
    
    def test_calc_totals_per_serving(self):
        
        totals = calc_totals_per_serving(recipe = self.r)

        self.assertEqual(totals.cal, 219/2.5)
        self.assertEqual(totals.carb_grams, 4.5/2.5)
        self.assertFalse(totals.animal)

    def test_calc_totals_eaten(self):
        
        totals_eaten = calc_totals_eaten(tots_per_serv=self.test_props, servings_eaten=1.5)

        self.assertEqual(totals_eaten.cal, 219*1.5)
        self.assertEqual(totals_eaten.carb_grams, 4.5*1.5)
        self.assertFalse(totals_eaten.animal)

    def test_parse_gram_nutrients(self):
        with self.subTest("Valid gram fields are kept, in the order given."):
            self.assertEqual(parse_gram_nutrients(["fat_grams", "carb_grams"]), ["fat_grams", "carb_grams"])

        with self.subTest("Unknown names, non-gram fields and duplicates are dropped with a warning each."):
            with self.assertLogs("forkwise.utils", level="WARNING") as logs:
                kept = parse_gram_nutrients(["fiber_grams", "salt_grams", "cal", "animal", "fiber_grams"])
            self.assertEqual(kept, ["fiber_grams"])
            self.assertEqual(len(logs.output), 4)
            self.assertIn("salt_grams", logs.output[0])

        with self.subTest("A missing list gives the defaults."):
            self.assertEqual(parse_gram_nutrients(None), DEFAULT_GRAM_NUTRIENTS)

        with self.subTest("A value that isn't a list gives the defaults with a warning."):
            # e.g. gram_nutrients: fiber_grams (a string, not a one-item list)
            with self.assertLogs("forkwise.utils", level="WARNING"):
                self.assertEqual(parse_gram_nutrients("fiber_grams"), DEFAULT_GRAM_NUTRIENTS)

        with self.subTest("An empty list stays empty."):
            self.assertEqual(parse_gram_nutrients([]), [])

    def test_props_display_names(self):
        # Charts look up labels here, so a field missing from it would crash the dashboard if configured
        self.assertEqual(set(PROPS_DISPLAY_NAMES), {f.name for f in fields(FoodProps)})
