# Copyright (c) 2026 Stephanie Johnson

import unittest
import os

import dbcommons.testing_utils as utils
from forkwise.fork_db import ForkDB

# TODO might be better to locate these by where the file is? Does this work with CI?
TEST_CONFIG_PATH = os.path.join(os.getcwd(),"tests","fixtures","test_config.yml")
TEST_DATA_PATH = os.path.join(os.getcwd(),"tests","fixtures")
SCHEMA_PATH = os.path.join(os.getcwd(), "src", "forkwise", "schema.sql")

class TestDBConn(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.params = utils.config_params(config_path=TEST_CONFIG_PATH)
        utils.set_up_test_DB(params=cls.params, path_to_schema=SCHEMA_PATH)
        cls.conn = ForkDB(user=cls.params["user"], pw=cls.params["user_pw"], db_name=cls.params["test_db_name"])

    @classmethod
    def tearDownClass(cls):
        utils.tear_down_test_DB(db_conn=cls.conn, params=cls.params)
    
    def test_add_ingredients_via_staging(self):
        path_to_ingr_csv = os.path.join(TEST_DATA_PATH,"test_ingredients.csv")

        num_rows_added = self.conn.add_ingredients_from_csv(path_to_ingr_csv=path_to_ingr_csv)
        
        # TODO use pandas instead of hard-coding number of lines
        # Check for uploading partial duplicates by first uploading only part of the file
        self.assertEqual(num_rows_added, 11, "Incorrect number of rows added to ingredients table")

        # TODO test dups

    def test_add_recipe_via_staging(self):
        path_to_recipe_csv = os.path.join(TEST_DATA_PATH, "test_recipe2.csv")

        # Check that we can't add if not all ingredients are in db - 
        # Even if test_add_ingredients_via_staging is run first, so the db has that list of ingredients,
        # it'll be missing asparagus:
        with self.assertRaises(ValueError):
            self.conn.add_recipe_via_staging(path_to_recipe_csv=path_to_recipe_csv, name="grilled asparagus", servings=2)
        
        # Now add the missing ingredients (if test_add_ingredients_via_staging has run, olive oil will already be in there)
        # Note there's a deliberate case mismatch between ingredient names here vs test_recipe2.csv
        self.conn.add_ingredients_via_staging(path_to_ingr_csv=os.path.join(TEST_DATA_PATH, "test_ingredients2.csv"))

        self.assertEqual(self.conn.add_recipe_via_staging(path_to_recipe_csv=path_to_recipe_csv, name="grilled asparagus", servings=2), 1, "Failed to add recipe")