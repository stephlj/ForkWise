import unittest
import os

from dbcommons.dataclass_utils import csv_to_dataclass
from forkwise.fork_dataclasses import fix_units
from forkwise.fork_dataclasses import fix_units, PantryItem, Ingredient

from utils_for_tests import TEST_DATA_PATH

class TestForkDataclasses(unittest.TestCase):

    def test_fix_units(self):
        self.assertEqual(fix_units('lb'), 'lbs')
        self.assertEqual(fix_units('lb '), 'lbs')
        self.assertEqual(fix_units('Lb '), 'lbs')
        self.assertEqual(fix_units('LB'), 'lbs')
        self.assertEqual(fix_units('cup'), 'c')
        self.assertEqual(fix_units(' cup'), 'c')
        self.assertEqual(fix_units('Cup'), 'c')
        self.assertEqual(fix_units('unit'), 'unit')
        self.assertEqual(fix_units(' unit '), 'unit')
        self.assertEqual(fix_units(' not a real unit but'), 'not a real unit but')

    def test_csv_to_pantry_item(self):
        # Tests ForkWise's csv_parser metadata in fork_dataclasses on PantryItem: nested props, bools, fix_units on units.
        items = csv_to_dataclass(path_to_csv=os.path.join(TEST_DATA_PATH, 'test_ingrs_to_csv.csv'), cls=PantryItem)

        self.assertEqual([i.name for i in items], ['Cream cheese', 'Strawberries'])
        self.assertEqual(items[1].unitary_amt, 144)
        self.assertEqual(items[0].units, 'Tbsp')         # ' Tbsp' -> fix_units strips
        self.assertEqual(items[1].units, 'G')            # case preserved for non-aliased units
        self.assertEqual(items[0].props.cal, 80)         # nested FoodProps
        self.assertEqual(items[1].props.sugar_grams, 7)
        self.assertTrue(items[0].props.animal)           # '1' -> True
        self.assertFalse(items[1].props.animal)          # '0' -> False

    def test_csv_to_ingredient(self):
        ingrs = csv_to_dataclass(path_to_csv=os.path.join(TEST_DATA_PATH, "test_recipe.csv"), cls=Ingredient)
        self.assertEqual(ingrs[0].ingr_name, 'asparagus')

        ingrs_fixunit = csv_to_dataclass(path_to_csv=os.path.join(TEST_DATA_PATH, "test_recipe_fix_units.csv"), cls=Ingredient)
        self.assertEqual(ingrs_fixunit[0].ingredient_units, 'lbs')   # ' lb' -> 'lbs'
        self.assertEqual(ingrs_fixunit[1].ingredient_amt, 3.3)

        with self.assertRaises(ValueError):                           
            # 'one' (in the csv) isn't a float (expected by the dataclass)
            csv_to_dataclass(path_to_csv=os.path.join(TEST_DATA_PATH, "test_recipe_wrong_type.csv"), cls=Ingredient)
