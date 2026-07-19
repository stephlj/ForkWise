# Copyright (c) 2026 Stephanie Johnson

import unittest
import os

from psycopg import errors as psql_errors

import dbcommons.testing_utils as utils
from forkwise.fork_init import fork_init
from forkwise.add_fork_user import add_fork_user
from forkwise.fork_db import ForkDB

# TODO might be better to locate these by where the file is? Does this work with CI?
TEST_CONFIG_PATH = os.path.join(os.getcwd(),"tests","fixtures","test_config.yml")
TEST_DATA_PATH = os.path.join(os.getcwd(),"tests","fixtures")
SCHEMA_PATH = os.path.join(os.getcwd(), "src", "forkwise", "schema.sql")

class TestForkDB(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.params = utils.config_params(config_path=TEST_CONFIG_PATH)
        cls.params["user"] = "test_fork_user"

        # Can't use this anymore because forkwise now has its own init process:
        # utils.set_up_test_DB(params=cls.params, path_to_schema=SCHEMA_PATH)

        fork_init(admin_pw=cls.params["owner_pw"], path_to_config=cls.params["config_path"])
        add_fork_user(new_user_name=cls.params["user"], new_user_pw=cls.params["user_pw"], admin_pw=cls.params["owner_pw"], path_to_config=cls.params["config_path"])

        cls.conn = ForkDB(user=cls.params["user"], pw=cls.params["user_pw"], db_name=cls.params["test_db_name"])
        
        # TEMP HACK - goes with the line above I can't use anymore
        # cls.conn.add_conversions(path_to_conversions_csv=os.path.join(os.getcwd(), "src", "forkwise", "conversions.csv"))

    @classmethod
    def tearDownClass(cls):
        utils.tear_down_test_DB(db_conn=cls.conn, params=cls.params)
    
    def test_add_ingredients_via_staging(self):
        path_to_ingr_csv_some_dups = os.path.join(TEST_DATA_PATH,"test_ingredients.csv")
        path_to_ingr_csv = os.path.join(TEST_DATA_PATH,"test_ingredients_part.csv")

        num_rows_added = self.conn.add_ingredients_via_staging(path_to_ingr_csv=path_to_ingr_csv)
        
        # TODO use pandas instead of hard-coding number of lines?
        self.assertEqual(num_rows_added, 8, "Incorrect number of rows added to ingredients table")

        num_rows_added = self.conn.add_ingredients_via_staging(path_to_ingr_csv=path_to_ingr_csv_some_dups)
        self.assertEqual(num_rows_added, 2, "Failed to properly add only non-duplicate ingredients")

    def test_add_recipe_via_staging(self):
        path_to_recipe_csv = os.path.join(TEST_DATA_PATH, "test_recipe.csv")

        # Check that we can't add if not all ingredients are in db:
        with self.assertRaises(ValueError):
            self.conn.add_recipe_via_staging(
                path_to_recipe_csv=path_to_recipe_csv, 
                name="grilled asparagus", 
                servings=2,
                servings_amt=0.5,
                servings_units='lbs'
                )
        
        # Now add the missing ingredients:
        # Note there's a deliberate case mismatch between ingredient names here vs test_recipe.csv
        self.conn.add_ingredients_via_staging(path_to_ingr_csv=os.path.join(TEST_DATA_PATH, "test_recipe_ingr.csv"))

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
        # First add extra ingredient in test_recipe2:
        self.conn.add_ingredients_via_staging(path_to_ingr_csv=os.path.join(TEST_DATA_PATH, "test_recipe_ingr2.csv"))
        path_to_recipe_csv2 = os.path.join(TEST_DATA_PATH, "test_recipe2.csv")
        with self.assertRaises(psql_errors.UniqueViolation):
            self.conn.add_recipe_via_staging(path_to_recipe_csv=path_to_recipe_csv2, name="grilled asparagus", servings=2, servings_amt=0.5, servings_units='lbs')

        # Test that we can't add the same set of components under a different recipe name
        with self.assertRaises(ValueError):
            self.conn.add_recipe_via_staging(path_to_recipe_csv=path_to_recipe_csv, name="other asparagus", servings=2, servings_amt=0.5, servings_units='lbs')

        # Test that we can add a recipe with the additional ingredient (but not the same recipe name)
        # should add 3 rows, 2 of them duplicates except for recipe_id, because we allow that
        self.assertEqual(
            self.conn.add_recipe_via_staging(path_to_recipe_csv=path_to_recipe_csv2, 
                                             name="onion asparagus", 
                                             servings=1,
                                             servings_amt=0.5, 
                                             servings_units='lbs'), 
            3, 
            "Failed to add recipe with some duplicate components")
        
    def test_add_meals_via_staging(self):
        path_to_meals_csv = os.path.join(TEST_DATA_PATH,"test_meals.csv")

        # Add everything we need:
        self.conn.add_ingredients_via_staging(path_to_ingr_csv=os.path.join(TEST_DATA_PATH, "test_meals_ingr.csv"))
        self.conn.add_recipe_via_staging(path_to_recipe_csv=os.path.join(TEST_DATA_PATH, "test_meals_recipe.csv"),
                                            name="burger", 
                                            servings=4,
                                            servings_amt=0.4,
                                            servings_units='lbs')
        self.conn.add_recipe_via_staging(path_to_recipe_csv=os.path.join(TEST_DATA_PATH,"test_meals_recipe2.csv"), 
                                             name="steamed broccoli", 
                                             servings=2,
                                             servings_amt=0.5, 
                                             servings_units='lbs')
        # Test that we can't add meals if one recipe isn't in the db:
        with self.assertRaises(ValueError):
            self.conn.add_meals_via_staging(path_to_meals_csv=path_to_meals_csv)

        # Add missing recipe:
        self.conn.add_recipe_via_staging(path_to_recipe_csv=os.path.join(TEST_DATA_PATH, "test_meals_recipe3.csv"),
                                         name="lemonade",
                                         servings=6,
                                         servings_amt=1,
                                         servings_units='pint'
                                         )
        # Now adding meals should run:
        self.assertEqual(self.conn.add_meals_via_staging(path_to_meals_csv=path_to_meals_csv),3)
    
    def test_get_recipe_totals(self):
        # Add what we need in the db:
        self.conn.add_ingredients_via_staging(path_to_ingr_csv=os.path.join(TEST_DATA_PATH, "test_totals_ingr.csv"))
        self.conn.add_recipe_via_staging(path_to_recipe_csv=os.path.join(TEST_DATA_PATH, "test_totals_recipe.csv"),
                                            name="hot cocoa", 
                                            servings=2,
                                            servings_amt=1,
                                            servings_units='c')

        totals = self.conn.get_recipe_totals(recipe_name='hot cocoa')

        self.assertEqual(totals.cal, 314)
        self.assertTrue(totals.animal)
        self.assertEqual(totals.servings_amt, 1)

        # Test that unit conversion fails if units in Components vs Ingredients are mismatched types:
        self.conn.add_recipe_via_staging(path_to_recipe_csv=os.path.join(TEST_DATA_PATH, "test_totals_wrongunits.csv"),
                                         name="wrong cocoa",
                                         servings=2,
                                         servings_amt=1,
                                         servings_units="c")
        with self.assertRaises(ValueError):
            self.conn.get_recipe_totals(recipe_name="wrong cocoa")