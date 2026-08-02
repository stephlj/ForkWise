import unittest

from forkwise.utils import calc_totals_per_serving, calc_totals_eaten
from forkwise.fork_dataclasses import FoodProps, PantryItem, Ingredient, Recipe

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