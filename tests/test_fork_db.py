# Copyright (c) 2026 Stephanie Johnson

import unittest
import os

from psycopg import errors as psql_errors

import dbcommons.testing_utils as utils
from forkwise.fork_db import ForkDB

# TODO might be better to locate these by where the file is? Does this work with CI?
TEST_CONFIG_PATH = os.path.join(os.getcwd(),"tests","fixtures","test_config.yml")
TEST_DATA_PATH = os.path.join(os.getcwd(),"tests","fixtures")
SCHEMA_PATH = os.path.join(os.getcwd(), "src", "forkwise", "schema.sql")

# To connect to the testing db (if not running this automatically):
# psql -U test_user -d test_fork_db

class TestForkDB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.params = utils.config_params(config_path=TEST_CONFIG_PATH)
        utils.set_up_test_DB(params=cls.params, path_to_schema=SCHEMA_PATH)
        cls.conn = ForkDB(user=cls.params["user"], pw=cls.params["user_pw"], db_name=cls.params["test_db_name"])

        #TODO in next PR: put this in db init. Temporary hack!
        cls.conn.add_conversions(path_to_conversions_csv=os.path.join(os.getcwd(), "src", "forkwise", "conversions.csv"))

    # @classmethod
    # def tearDownClass(cls):
    #     utils.tear_down_test_DB(db_conn=cls.conn, params=cls.params)
    
    def test_add_ingredients_via_staging(self):
        path_to_ingr_csv_some_dups = os.path.join(TEST_DATA_PATH,"test_ingredients.csv")
        path_to_ingr_csv = os.path.join(TEST_DATA_PATH,"test_ingredients_part.csv")

        num_rows_added = self.conn.add_ingredients_via_staging(path_to_ingr_csv=path_to_ingr_csv)
        
        # TODO use pandas instead of hard-coding number of lines?
        self.assertEqual(num_rows_added, 8, "Incorrect number of rows added to ingredients table")

        num_rows_added = self.conn.add_ingredients_via_staging(path_to_ingr_csv=path_to_ingr_csv_some_dups)
        self.assertEqual(num_rows_added, 2, "Failed to properly add only non-duplicate ingredients")

    def test_add_recipe_via_staging(self):
        path_to_recipe_csv = os.path.join(TEST_DATA_PATH, "test_recipe2.csv")

        # Check that we can't add if not all ingredients are in db - 
        # Even if test_add_ingredients_via_staging is run first, so the db has that list of ingredients,
        # it'll be missing asparagus:
        with self.assertRaises(ValueError):
            self.conn.add_recipe_via_staging(
                path_to_recipe_csv=path_to_recipe_csv, 
                name="grilled asparagus", 
                servings=2,
                servings_amt=0.5,
                servings_units='lbs'
                )
        
        # Now add the missing ingredients (if test_add_ingredients_via_staging has run, olive oil will already be in there)
        # Note there's a deliberate case mismatch between ingredient names here vs test_recipe2.csv
        self.conn.add_ingredients_via_staging(path_to_ingr_csv=os.path.join(TEST_DATA_PATH, "test_ingredients2.csv"))

        # Note that add_recipe_via_staging returns number of rows added to components
        self.assertEqual(
            self.conn.add_recipe_via_staging(path_to_recipe_csv=path_to_recipe_csv, 
                                             name="grilled asparagus", 
                                             servings=2,
                                             servings_amt=0.5,
                                             servings_units='lbs'), 
            2, 
            "Failed to add recipe")
        
        # Test that we can't add a recipe of the same name
        path_to_recipe_csv2 = os.path.join(TEST_DATA_PATH, "test_recipe3.csv")
        with self.assertRaises(psql_errors.UniqueViolation):
            self.conn.add_recipe_via_staging(path_to_recipe_csv=path_to_recipe_csv2, name="grilled asparagus", servings=2, servings_amt=0.5, servings_units='lbs')

        # Test that we can't add the same set of components under a different recipe name
        with self.assertRaises(ValueError):
            self.conn.add_recipe_via_staging(path_to_recipe_csv=path_to_recipe_csv, name="other asparagus", servings=2, servings_amt=0.5, servings_units='lbs')

        # Test that we can add a recipe with an additional ingredient (but not the same name)
        # should add 3 rows, 2 of them duplicates except for recipe_id, because we allow that
        # Make sure ingredients from test_ingredients is in the db:
        self.conn.add_ingredients_via_staging(path_to_ingr_csv=os.path.join(TEST_DATA_PATH, "test_ingredients.csv"))
        self.assertEqual(
            self.conn.add_recipe_via_staging(path_to_recipe_csv=path_to_recipe_csv2, 
                                             name="onion asparagus", 
                                             servings=1,
                                             servings_amt=0.5, 
                                             servings_units='lbs'), 
            3, 
            "Failed to add recipe with some duplicate components")
        
    def test_get_recipe_totals(self):
        # Make sure we have what we need in the db already:
        self.conn.add_ingredients_via_staging(path_to_ingr_csv=os.path.join(TEST_DATA_PATH, "test_ingredients2.csv"))
        try: 
            self.conn.add_recipe_via_staging(path_to_recipe_csv=os.path.join(TEST_DATA_PATH, "test_recipe2.csv"),
                                            name="grilled asparagus", 
                                            servings=2,
                                            servings_amt=0.5,
                                            servings_units='lbs')
        except ValueError:
            pass

        totals = self.conn.get_recipe_totals(recipe_name='grilled asparagus')

        self.assertEqual(totals.cal, 416)
        self.assertFalse(totals.animal)
        self.assertEqual(totals.servings_amt, 0.5)

        # Test that unit conversion fails if units in Components vs Ingredients are mismatched types:
        self.conn.add_recipe_via_staging(path_to_recipe_csv=os.path.join(TEST_DATA_PATH, "test_recipe_wrongunits.csv"),
                                         name="wrong asparagus",
                                         servings=2,
                                         servings_amt=0.5,
                                         servings_units="lbs")
        with self.assertRaises(ValueError):
            self.conn.get_recipe_totals(recipe_name="wrong asparagus")

    def test_add_meals_via_staging(self):
        path_to_meals_csv = os.path.join(TEST_DATA_PATH,"test_meals.csv")

        # Test that we can't add meals if some recipes aren't in the db:
        with self.assertRaises(ValueError):
            self.conn.add_meals_via_staging(path_to_meals_csv=path_to_meals_csv)

        # Add missing recipe:
        self.conn.add_recipe_via_staging(path_to_recipe_csv=os.path.join(TEST_DATA_PATH, "test_recipe.csv"),
                                         name="Veggie Burger",
                                         servings=6,
                                         servings_amt=1,
                                         servings_units='unit'
                                         )
        
        self.assertEqual(self.conn.add_meals_via_staging(path_to_meals_csv=path_to_meals_csv),3)