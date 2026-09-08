import unittest
import os

from forkwise.add_recipe import fix_units, csv_to_recipe_ingr

TEST_DATA_PATH = os.path.join(os.getcwd(),"tests","fixtures")

class TestAddRecipe(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pass

    def test_fix_units(self):
        self.assertEqual(fix_units('lb'), 'lbs')
        self.assertEqual(fix_units('lb '), 'lbs')
        self.assertEqual(fix_units('cup'), 'c')
        self.assertEqual(fix_units(' cup'), 'c')
        self.assertEqual(fix_units('unit'), 'unit')
        self.assertEqual(fix_units(' unit '), 'unit')
        self.assertEqual(fix_units(' not a real unit but'),'not a real unit but')

    def test_csv_to_recipe_ingr(self):
        ingrs = csv_to_recipe_ingr(path_to_recipe_csv = os.path.join(TEST_DATA_PATH, "test_recipe.csv"))
        self.assertEqual(ingrs[0].ingr_name, 'asparagus')

        ingrs_fixunit = csv_to_recipe_ingr(path_to_recipe_csv = os.path.join(TEST_DATA_PATH, "test_recipe_fix_units.csv"))
        self.assertEqual(ingrs_fixunit[1].ingredient_amt, 3.3)
        self.assertEqual(ingrs_fixunit[0].ingredient_units, 'lbs')

        with self.assertRaises(ValueError):
            ingrs_unit_mismatch = csv_to_recipe_ingr(path_to_recipe_csv=os.path.join(TEST_DATA_PATH, "test_recipe_wrong_type.csv"))     

    def test_add_recipe_from_csv(self):
        # TODO use mocking? (integration test)
        pass