# Copyright (c) 2026 Stephanie Johnson

import unittest
import os, subprocess

import pandas as pd

from datetime import date

import dbcommons.testing_utils as utils
from forkwise.fork_init import fork_init
from forkwise.add_fork_user import add_fork_user
from forkwise.data_loader import DataLoader
from forkwise.data_getter import DataGetter

from utils_for_tests import TEST_CONFIG_PATH, TEST_DATA_PATH

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
        # Implicit test of fork_db.calc_recipe_totals_per_serving, which is the key logic piece here
        # Add what we need in the db:
        with DataLoader(user=self.params["user"], pw=self.params["user_pw"], db_name=self.params["test_db_name"]) as dl:
            dl.add_ingredients_from_csv(path_to_ingr_csv=os.path.join(TEST_DATA_PATH, "test_totals_ingr.csv"))
            dl.add_recipe_from_csv(path_to_recipe_csv=os.path.join(TEST_DATA_PATH, "test_totals_recipe.csv"),
                                                recipe_name="hot cocoa", 
                                                servings=2,
                                                servings_amt=1,
                                                servings_units='c')

        totals = self.DataGetter.get_recipe_totals(recipe_name='hot cocoa')

        # Recipe totals are now per serving
        self.assertEqual(round(totals.props.cal,2), round((2*149 + (4/3)*12)/2,2)) # 2 c milk * 149 cal/1 c + 4 tsp cocoa * 1 Tbsp/3 tsp * 12 cal/1 Tbsp, divided by 2 servings
        self.assertEqual(round(totals.props.fat_grams,2), round((2*8 + (4/3)*1)/2,2)) # 2 c milk * 8 fat g/1 c + 4 tsp cocoa * 1 Tbsp/3 tsp * 1 fat g/1 Tbsp, divided by 2 servings
        self.assertTrue(totals.props.animal)
        self.assertEqual(totals.servings, 1)
        self.assertEqual(totals.servings_amt, 1)

        # Test that unit conversion fails if units in ingredients vs pantry_items are mismatched types:
        # We now check for this on recipe load (so can't even add the recipe here)
        # self.conn.add_recipe_from_csv(path_to_recipe_csv=os.path.join(TEST_DATA_PATH, "test_totals_wrongunits.csv"),
        #                                  recipe_name="wrong cocoa",
        #                                  servings=2,
        #                                  servings_amt=1,
        #                                  servings_units="c")
        # with self.assertRaises(ValueError):
        #     self.conn.get_recipe_totals(recipe_name="wrong cocoa")

    def test_get_totals_in_dates(self):
        # Implicit test of fork_db.get_totals_per_date_range()

        # Add meals, recipes, ingredients unique to this test
        path_to_ingr_csv = os.path.join(TEST_DATA_PATH, "test_meals2_ingr.csv")
        path_to_recipe_csv = os.path.join(TEST_DATA_PATH, "test_meals2_recipe.csv")
        path_to_recipe2_csv = os.path.join(TEST_DATA_PATH, "test_meals2_recipe2.csv")
        path_to_recipe3_csv = os.path.join(TEST_DATA_PATH, "test_meals2_recipe3.csv")
        path_to_meals_csv = os.path.join(TEST_DATA_PATH,"test_meals2.csv")

        with DataLoader(user=self.params["user"], pw=self.params["user_pw"], db_name=self.params["test_db_name"]) as dl:
            dl.add_ingredients_from_csv(path_to_ingr_csv=path_to_ingr_csv) #has an extraneous ingredient just for extra testing
            dl.add_recipe_from_csv(path_to_recipe_csv=path_to_recipe_csv,
                                                recipe_name="hummus", 
                                                servings=8,
                                                servings_amt=0.5,
                                                servings_units='c')
            dl.add_recipe_from_csv(path_to_recipe_csv=path_to_recipe2_csv, 
                                                recipe_name="toast", 
                                                servings=1,
                                                servings_amt=1, 
                                                servings_units='unit')
            dl.add_recipe_from_csv(path_to_recipe_csv=path_to_recipe3_csv, 
                                                recipe_name="soy cocoa", 
                                                servings=1,
                                                servings_amt=1, 
                                                servings_units='c')
            dl.add_meals_from_csv(path_to_meals_csv=path_to_meals_csv)
        
        # Test date selection:
        meals = self.DataGetter.get_totals_in_dates(date_range=[date(year=2026,month=5,day=20),date(year=2026,month=7,day=5)])
        self.assertEqual(len(meals),4) # 4 recipes eaten over 2 dates in range
        # ensure no data were scrambled, and calculations are right
        # Soy cocoa cal = 1.25 c soy milk * (80 cal/1 c) + 0.25 c cocoa * (17.5 cal / 1 Tbsp * 16 Tbsp / c) / 1 serving per recipe * 1.25 servings eaten on 6/2/26
        self.assertEqual(round(meals[(meals['date_eaten']==date(year=2026,month=6,day=2)) & (meals['recipe_name']=='soy cocoa')].cal.item(),2), round((1.25*80 + 0.25*17.5*16)*1.25,2))
        # hummus fiber_grams = (30 oz garbonzo * 21 fiber/15.5 oz + 0.67 c oil * 0 fiber/Tbsp + 2 Tbsp lemon * 0.06 fiber / Tbsp + 1 unit garlic * 0.06 fiber/unit) / 8 servings per recipe * 1.5 servings eaten on 7/5/26
        self.assertEqual(round(meals[(meals['date_eaten']==date(year=2026,month=7,day=5)) & (meals['recipe_name']=='hummus')].fiber_grams.item(),2), round((30*(21/15.5) + 2*0.06 + 1*0.06)/8 * 1.5,2)) 
        self.assertTrue(meals[(meals['date_eaten']==date(year=2026,month=7,day=5)) & (meals['recipe_name']=='toast')].animal.item()) # Check boolean handling

        # Test we can pull just one day:
        meals = self.DataGetter.get_totals_in_dates(date_range=[date(year=2026,month=5,day=12), date(year=2026,month=5,day=12)])
        self.assertTrue(len(meals)==1)
        self.assertEqual(meals[meals["date_eaten"]==date(year=2026,month=5,day=12)].recipe_name.to_list(), ['hummus'])

        # Test we get an empty df for no meals in range
        meals = self.DataGetter.get_totals_in_dates(date_range=[date(year=2027,month=10,day=5),date(year=2027,month=10,day=10)])
        pd.testing.assert_frame_equal(meals, pd.DataFrame())