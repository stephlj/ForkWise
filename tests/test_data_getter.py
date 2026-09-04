# Copyright (c) 2026 Stephanie Johnson

import unittest
import os, subprocess

from psycopg import errors as psql_errors
from datetime import date

import dbcommons.testing_utils as utils
from forkwise.fork_init import fork_init
from forkwise.add_fork_user import add_fork_user
from forkwise.data_loader import DataLoader
from forkwise.data_getter import DataGetter

# TODO might be better to locate these by where the file is? Does this work with CI?
TEST_CONFIG_PATH = os.path.join(os.getcwd(),"tests","fixtures","test_config.yml")
TEST_DATA_PATH = os.path.join(os.getcwd(),"tests","fixtures")
SCHEMA_PATH = os.path.join(os.getcwd(), "src", "forkwise", "schema.sql")

class TestDataGetter(unittest.TestCase):
    # Implicit tests of fork_db
    @classmethod
    def setUpClass(cls):
        cls.params = utils.config_params(config_path=TEST_CONFIG_PATH)
        cls.params["user"] = "test_fork_user"

        fork_init(admin_pw=cls.params["owner_pw"], path_to_config=cls.params["config_path"])
        add_fork_user(new_user_name=cls.params["user"], new_user_pw=cls.params["user_pw"], admin_pw=cls.params["owner_pw"], path_to_config=cls.params["config_path"])

        # TODO open connetion here or use a with clause within test cases?
        cls.DataGetter = DataGetter(user=cls.params["user"], pw=cls.params["user_pw"], db_name=cls.params["test_db_name"])
        
    @classmethod
    def tearDownClass(cls):
        # utils.tear_down_test_DB(db_conn=cls.conn, params=cls.params)
        cls.DataGetter.close()

        # Delete testing db
        exit_code = subprocess.run(["dropdb", cls.params["test_db_name"]])
        exit_code2 = subprocess.run(["dropuser",cls.params["user"]])
        exit_code3 = subprocess.run(["dropuser",cls.params["test_owner"]])

        # We put these at the end to ensure teardown completes even if one of these fails.
        assert exit_code.returncode==0, "Failed to remove testing db, must now remove manually"
        assert exit_code2.returncode==0, "Failed to remove testing user, must now remove manually"
        assert exit_code3.returncode==0, "Failed to remove testing db owner, must now remove manually"
    
    def test_get_recipe_totals(self):
        # Add what we need in the db:
        with DataLoader(user=self.params["user"], pw=self.params["user_pw"], db_name=self.params["test_db_name"]) as dl:
            dl.add_ingredients_via_staging(path_to_ingr_csv=os.path.join(TEST_DATA_PATH, "test_totals_ingr.csv"))
            dl.add_recipe_via_staging(path_to_recipe_csv=os.path.join(TEST_DATA_PATH, "test_totals_recipe.csv"),
                                                name="hot cocoa", 
                                                servings=2,
                                                servings_amt=1,
                                                servings_units='c')

        totals = self.DataGetter.get_recipe_totals(recipe_name='hot cocoa')

        # Recipe totals are for however many servings the recipe makes, not per serving
        self.assertEqual(round(totals.props.cal,2), round(2*149 + (4/3)*12,2)) # 2 c milk * 149 cal/1 c + 4 tsp cocoa * 1 Tbsp/3 tsp * 12 cal/1 Tbsp
        self.assertEqual(round(totals.props.fat_grams,2), round(2*8 + (4/3)*1,2)) # 2 c milk * 8 fat g/1 c + 4 tsp cocoa * 1 Tbsp/3 tsp * 1 fat g/1 Tbsp
        self.assertTrue(totals.props.animal)
        self.assertEqual(totals.servings_amt, 1)

        # Test that unit conversion fails if units in ingredients vs pantry_items are mismatched types:
        # We now check for this on recipe load (so can't even add the recipe here)
        # self.conn.add_recipe_via_staging(path_to_recipe_csv=os.path.join(TEST_DATA_PATH, "test_totals_wrongunits.csv"),
        #                                  name="wrong cocoa",
        #                                  servings=2,
        #                                  servings_amt=1,
        #                                  servings_units="c")
        # with self.assertRaises(ValueError):
        #     self.conn.get_recipe_totals(recipe_name="wrong cocoa")

    def test_get_meals_in_dates(self):
        # Add meals, recipes, ingredients unique to this test
        path_to_ingr_csv = os.path.join(TEST_DATA_PATH, "test_meals2_ingr.csv")
        path_to_recipe_csv = os.path.join(TEST_DATA_PATH, "test_meals2_recipe.csv")
        path_to_recipe2_csv = os.path.join(TEST_DATA_PATH, "test_meals2_recipe2.csv")
        path_to_recipe3_csv = os.path.join(TEST_DATA_PATH, "test_meals2_recipe3.csv")
        path_to_meals_csv = os.path.join(TEST_DATA_PATH,"test_meals2.csv")

        with DataLoader(user=self.params["user"], pw=self.params["user_pw"], db_name=self.params["test_db_name"]) as dl:
            dl.add_ingredients_via_staging(path_to_ingr_csv=path_to_ingr_csv) #has an extraneous ingredient just for extra testing
            dl.add_recipe_via_staging(path_to_recipe_csv=path_to_recipe_csv,
                                                name="hummus", 
                                                servings=8,
                                                servings_amt=0.5,
                                                servings_units='c')
            dl.add_recipe_via_staging(path_to_recipe_csv=path_to_recipe2_csv, 
                                                name="toast", 
                                                servings=1,
                                                servings_amt=1, 
                                                servings_units='unit')
            dl.add_recipe_via_staging(path_to_recipe_csv=path_to_recipe3_csv, 
                                                name="soy cocoa", 
                                                servings=1,
                                                servings_amt=1, 
                                                servings_units='c')
            dl.add_meals_via_staging(path_to_meals_csv=path_to_meals_csv)
        
        # TODO These tests may fail because I need to sort by date in order to index the way I am ... and maybe recipes per date by name?
        # Test date selection:
        meals = self.DataGetter.get_meals_in_dates(date_range=[date(year=2026,month=5,day=20),date(year=2026,month=7,day=5)])
        self.assertTrue(meals[0].recipes[1].name=='soy cocoa')
        self.assertTrue(meals[1].recipes[0].name=='hummus')
        self.assertTrue(meals[1].servings_eaten[0]==1.5)

        # Test we can pull just one day:
        meals = self.DataGetter.get_meals_in_dates(date_range=[date(year=2026,month=5,day=12), date(year=2026,month=5,day=12)])
        self.assertTrue(len(meals)==1)
        self.assertTrue(meals[0].recipes[0].name=='hummus')
        self.assertTrue(meals[0].servings_eaten[0]==1)

        # Test grouping:
        meals = self.DataGetter.get_meals_in_dates(date_range=[date(year=2026,month=5,day=12),date(year=2026,month=7,day=5)])
        self.assertEqual(len(meals),3)
        self.assertTrue(len(meals[0].recipes)==1)