# Copyright (c) 2026 Stephanie Johnson

import unittest
import os, subprocess

from psycopg import errors as psql_errors

import dbcommons.testing_utils as utils
from forkwise.fork_init import fork_init
from forkwise.add_fork_user import add_fork_user
from forkwise.data_loader import DataLoader
from forkwise.fork_db import ForkDB

# TODO might be better to locate these by where the file is? Does this work with CI?
TEST_CONFIG_PATH = os.path.join(os.getcwd(),"tests","fixtures","test_config.yml")
TEST_DATA_PATH = os.path.join(os.getcwd(),"tests","fixtures")
SCHEMA_PATH = os.path.join(os.getcwd(), "src", "forkwise", "schema.sql")

class TestDataLoader(unittest.TestCase):
    # Implicit tests of fork_db
    @classmethod
    def setUpClass(cls):
        cls.params = utils.config_params(config_path=TEST_CONFIG_PATH)
        cls.params["user"] = "test_fork_user"

        fork_init(admin_pw=cls.params["owner_pw"], path_to_config=cls.params["config_path"])
        add_fork_user(new_user_name=cls.params["user"], new_user_pw=cls.params["user_pw"], admin_pw=cls.params["owner_pw"], path_to_config=cls.params["config_path"])

        # TODO add connection here once? Or use in with clauses in test cases?
        cls.DataLoader = DataLoader(user=cls.params["user"], pw=cls.params["user_pw"], db_name=cls.params["test_db_name"])
    
    @classmethod
    def tearDownClass(cls):
        # utils.tear_down_test_DB(db_conn=cls.conn, params=cls.params)
        cls.DataLoader.close()

        # Delete testing db
        exit_code = subprocess.run(["dropdb", cls.params["test_db_name"]])
        exit_code2 = subprocess.run(["dropuser",cls.params["user"]])
        exit_code3 = subprocess.run(["dropuser",cls.params["test_owner"]])

        # We put these at the end to ensure teardown completes even if one of these fails.
        assert exit_code.returncode==0, "Failed to remove testing db, must now remove manually"
        assert exit_code2.returncode==0, "Failed to remove testing user, must now remove manually"
        assert exit_code3.returncode==0, "Failed to remove testing db owner, must now remove manually"
    
    def test_add_ingredients_via_staging(self):
        path_to_ingr_csv_dups = os.path.join(TEST_DATA_PATH,"test_ingredients_part_dups.csv")
        path_to_ingr_csv = os.path.join(TEST_DATA_PATH,"test_ingredients_part.csv")
        path_to_ingr_csv_wrong_units = os.path.join(TEST_DATA_PATH, "test_ingredients_wrong_units.csv")
        path_to_ingr_csv_some_dups = os.path.join(TEST_DATA_PATH,"test_ingredients.csv")

        with self.assertRaises(psql_errors.UniqueViolation):
            self.DataLoader.add_ingredients_via_staging(path_to_ingr_csv=path_to_ingr_csv_dups)

        num_rows_added = self.DataLoader.add_ingredients_via_staging(path_to_ingr_csv=path_to_ingr_csv)
        # TODO use pandas instead of hard-coding number of lines?
        self.assertEqual(num_rows_added, 8, "Incorrect number of rows added to ingredients table")

        num_rows_added = self.DataLoader.add_ingredients_via_staging(path_to_ingr_csv=path_to_ingr_csv_wrong_units)
        self.assertEqual(num_rows_added, 1, "Failed to properly add only non-duplicate ingredients with correct units")
        
        num_rows_added = self.DataLoader.add_ingredients_via_staging(path_to_ingr_csv=path_to_ingr_csv_some_dups)
        self.assertEqual(num_rows_added, 2, "Failed to properly add only non-duplicate ingredients")

        # Spot check correct load order of columns
        with ForkDB(user=self.params["user"], pw=self.params["user_pw"], db_name=self.params["test_db_name"]) as dbconn:
            carrot_fiber_grams_dict = dbconn.execute_query("SELECT fiber_grams FROM pantry_items WHERE name=%s",('Carrot',))
        carrot_fiber_grams = carrot_fiber_grams_dict[0]['fiber_grams']
        self.assertEqual(carrot_fiber_grams,2.2)

        with ForkDB(user=self.params["user"], pw=self.params["user_pw"], db_name=self.params["test_db_name"]) as dbconn:
            tamari_fat_grams_dict = dbconn.execute_query("SELECT fat_grams FROM pantry_items WHERE name=%s",('Tamari',))
        tamari_fat_grams = tamari_fat_grams_dict[0]['fat_grams']
        self.assertEqual(tamari_fat_grams,0)

    def test_add_recipe_via_staging(self):
        path_to_recipe_csv = os.path.join(TEST_DATA_PATH, "test_recipe.csv")

        # Check that we can't add if not all ingredients are in db:
        with self.assertRaises(ValueError):
            self.DataLoader.add_recipe_via_staging(
                path_to_recipe_csv=path_to_recipe_csv, 
                name="grilled asparagus", 
                servings=2,
                servings_amt=0.5,
                servings_units='lbs'
                )
        
        # Now add the missing ingredients:
        # Note there's a deliberate case mismatch between ingredient names here vs test_recipe.csv
        self.DataLoader.add_ingredients_via_staging(path_to_ingr_csv=os.path.join(TEST_DATA_PATH, "test_recipe_ingr.csv"))

        # Test that we still can't add the recipe if there's a unit category mismatch:
        path_to_recipe_csv_wrong_units = os.path.join(TEST_DATA_PATH, "test_recipe_wrong_units.csv")
        with self.assertRaises(ValueError):
            self.DataLoader.add_recipe_via_staging(
                path_to_recipe_csv=path_to_recipe_csv_wrong_units, 
                name="grilled asparagus", 
                servings=2,
                servings_amt=0.5,
                servings_units='lbs'
                )

        # Note that add_recipe_via_staging returns number of rows added to ingredients table
        self.assertEqual(
            self.DataLoader.add_recipe_via_staging(path_to_recipe_csv=path_to_recipe_csv, 
                                             name="grilled asparagus", 
                                             servings=2,
                                             servings_amt=0.5,
                                             servings_units='lbs'), 
            2, 
            "Failed to add recipe")
        
        # Test that we can't add a recipe of the same name
        # First add extra ingredient in test_recipe2:
        self.DataLoader.add_ingredients_via_staging(path_to_ingr_csv=os.path.join(TEST_DATA_PATH, "test_recipe_ingr2.csv"))
        path_to_recipe_csv2 = os.path.join(TEST_DATA_PATH, "test_recipe2.csv")
        with self.assertRaises(psql_errors.UniqueViolation):
            self.DataLoader.add_recipe_via_staging(path_to_recipe_csv=path_to_recipe_csv2, name="grilled asparagus", servings=2, servings_amt=0.5, servings_units='lbs')

        # Test that we can't add the same set of ingredients under a different recipe name
        with self.assertRaises(ValueError):
            self.DataLoader.add_recipe_via_staging(path_to_recipe_csv=path_to_recipe_csv, name="other asparagus", servings=2, servings_amt=0.5, servings_units='lbs')

        # Test that we can add a recipe with the additional ingredient (but not the same recipe name)
        # should add 3 rows, 2 of them duplicates except for recipe_id, because we allow that
        self.assertEqual(
            self.DataLoader.add_recipe_via_staging(path_to_recipe_csv=path_to_recipe_csv2, 
                                             name="onion asparagus", 
                                             servings=1,
                                             servings_amt=0.5, 
                                             servings_units='lbs'), 
            3, 
            "Failed to add recipe with some duplicate ingredients")
        
    def test_add_meals_via_staging(self):
        path_to_meals_csv = os.path.join(TEST_DATA_PATH,"test_meals.csv")

        # Add everything we need:
        self.DataLoader.add_ingredients_via_staging(path_to_ingr_csv=os.path.join(TEST_DATA_PATH, "test_meals_ingr.csv"))
        self.DataLoader.add_recipe_via_staging(path_to_recipe_csv=os.path.join(TEST_DATA_PATH, "test_meals_recipe.csv"),
                                            name="burger", 
                                            servings=4,
                                            servings_amt=0.4,
                                            servings_units='lbs')
        self.DataLoader.add_recipe_via_staging(path_to_recipe_csv=os.path.join(TEST_DATA_PATH,"test_meals_recipe2.csv"), 
                                             name="steamed broccoli", 
                                             servings=2,
                                             servings_amt=0.5, 
                                             servings_units='lbs')
        # Test that we can't add meals if one recipe isn't in the db:
        with self.assertRaises(ValueError):
            self.DataLoader.add_meals_via_staging(path_to_meals_csv=path_to_meals_csv)

        # Add missing recipe:
        self.DataLoader.add_recipe_via_staging(path_to_recipe_csv=os.path.join(TEST_DATA_PATH, "test_meals_recipe3.csv"),
                                         name="lemonade",
                                         servings=6,
                                         servings_amt=1,
                                         servings_units='pint'
                                         )
        # Now adding meals should run:
        self.assertEqual(self.DataLoader.add_meals_via_staging(path_to_meals_csv=path_to_meals_csv),3)
