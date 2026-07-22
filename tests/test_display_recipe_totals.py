import unittest

import forkwise.display_recipe_totals
from forkwise.fork_dataclasses import FoodProps, PantryItem, Ingredient, Recipe

class TestDisplayRecipeTotals(unittest.TestCase):

    def test_calc_totals_per_serving(self):
        test_props = FoodProps(
            cal=219,
            fat_grams=4,
            protein_grams=7,
            fiber_grams=27,
            sugar_grams=3.5,
            carb_grams=4.5,
            white_flour=True,
            animal=False
        )
        
        r = Recipe(name="test_recipe",
                   servings=2.5,
                   servings_amt=0.25,
                   servings_units="c",
                   props=test_props)