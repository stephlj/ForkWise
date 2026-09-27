# Copyright (c) 2026 Stephanie Johnson

import unittest
import os, subprocess, tempfile

from dataclasses import dataclass, field

from psycopg import errors as psql_errors

import dbcommons.testing_utils as utils
from forkwise.fork_init import fork_init
from forkwise.add_fork_user import add_fork_user
from forkwise.data_loader import DataLoader
from forkwise.fork_db import ForkDB
from forkwise.fork_dataclasses import PantryItem, FoodProps, Ingredient, fix_units

TEST_CONFIG_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "test_config.yml")
TEST_DATA_PATH = os.path.join(os.path.dirname(__file__), "fixtures")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "forkwise", "schema.sql")

@dataclass
class _Gizmo:
    # A throwaway dataclass unrelated to anything in fork_dataclasses, used to prove
    # csv_to_dataclass is generic. Carries the same metadata contract (sql_type +
    # csv_parser) that fork_dataclasses fields do.
    label: str = field(metadata={'sql_type': 'text', 'csv_parser': lambda s: s})
    weight: float = field(metadata={'sql_type': 'real', 'csv_parser': lambda s: float(s)})
    shiny: bool = field(metadata={'sql_type': 'boolean', 'csv_parser': lambda s: bool(int(s))})
    size_units: str = field(metadata={'sql_type': 'text', 'csv_parser': fix_units})

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
    
    def _write_tmp_csv(self, text: str) -> str:
        # Write `text` to a throwaway .csv and return its path (cleaned up after the test).

        f = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False)
        f.write(text)
        f.close()

        self.addCleanup(os.remove, f.name)
        
        return f.name
    
    def test_add_ingredients_from_csv(self):
        # Implicit test of add_ingredients_via_staging
        path_to_ingr_csv_dups = os.path.join(TEST_DATA_PATH,"test_ingredients_part_dups.csv")
        path_to_ingr_csv = os.path.join(TEST_DATA_PATH,"test_ingredients_part.csv")
        path_to_ingr_csv_fix_units = os.path.join(TEST_DATA_PATH, "test_ingredients_fix_units.csv")
        path_to_ingr_csv_wrong_units = os.path.join(TEST_DATA_PATH, "test_ingredients_wrong_units.csv")
        path_to_ingr_csv_some_dups = os.path.join(TEST_DATA_PATH,"test_ingredients.csv")

        with self.assertRaises(psql_errors.UniqueViolation):
            self.DataLoader.add_ingredients_from_csv(path_to_ingr_csv=path_to_ingr_csv_dups)

        num_rows_added = self.DataLoader.add_ingredients_from_csv(path_to_ingr_csv=path_to_ingr_csv)
        # TODO use pandas instead of hard-coding number of lines?
        self.assertEqual(num_rows_added, 8, "Incorrect number of rows added to ingredients table")

        num_rows_added = self.DataLoader.add_ingredients_from_csv(path_to_ingr_csv=path_to_ingr_csv_fix_units)
        self.assertEqual(num_rows_added, 2, "Failed to properly add only non-duplicate ingredients with units that need fixing (cup->c)")

        num_rows_added = self.DataLoader.add_ingredients_from_csv(path_to_ingr_csv=path_to_ingr_csv_wrong_units)
        self.assertEqual(num_rows_added, 1, "Failed to properly add only non-duplicate ingredients with wrong units")
        
        num_rows_added = self.DataLoader.add_ingredients_from_csv(path_to_ingr_csv=path_to_ingr_csv_some_dups)
        # One of these will be black beans (vs black beans can) which WILL load but with a warning
        self.assertEqual(num_rows_added, 2, "Failed to properly add only non-duplicate ingredients")

        # Spot check correct load order of columns, and handling of boolean inputs
        with ForkDB(user=self.params["user"], pw=self.params["user_pw"], db_name=self.params["test_db_name"]) as dbconn:
            carrot_dict = dbconn.execute_query("SELECT fiber_grams, animal FROM pantry_items WHERE name=%s;",('Carrot',))
        self.assertEqual(carrot_dict[0]['fiber_grams'],2.2)
        self.assertFalse(carrot_dict[0]["animal"])

        with ForkDB(user=self.params["user"], pw=self.params["user_pw"], db_name=self.params["test_db_name"]) as dbconn:
            tamari_dict = dbconn.execute_query("SELECT fat_grams, white_flour FROM pantry_items WHERE name=%s;",('Tamari',))
        self.assertEqual(tamari_dict[0]['fat_grams'],0)
        self.assertFalse(tamari_dict[0]["white_flour"])

    def test_add_recipe_from_csv(self):
        # Implicit test of add_recipe_via_staging
        path_to_recipe_csv = os.path.join(TEST_DATA_PATH, "test_recipe.csv")

        # Check that we can't add if not all ingredients are in db:
        with self.assertRaises(ValueError):
            self.DataLoader.add_recipe_from_csv(
                path_to_recipe_csv=path_to_recipe_csv, 
                recipe_name="grilled asparagus", 
                servings=2,
                servings_amt=0.5,
                servings_units='lbs'
                )
        
        # Now add the missing ingredients:
        # Note there's a deliberate case mismatch between ingredient names here vs test_recipe.csv
        self.DataLoader.add_ingredients_from_csv(path_to_ingr_csv=os.path.join(TEST_DATA_PATH, "test_recipe_ingr.csv"))

        # Test that we still can't add the recipe if there's a unit category mismatch:
        path_to_recipe_csv_wrong_units = os.path.join(TEST_DATA_PATH, "test_recipe_wrong_units.csv")
        with self.assertRaises(ValueError):
            self.DataLoader.add_recipe_from_csv(
                path_to_recipe_csv=path_to_recipe_csv_wrong_units, 
                recipe_name="grilled asparagus", 
                servings=2,
                servings_amt=0.5,
                servings_units='lbs'
                )

        # Note that add_recipe_from_csv returns number of rows added to ingredients table
        self.assertEqual(
            self.DataLoader.add_recipe_from_csv(path_to_recipe_csv=path_to_recipe_csv, 
                                             recipe_name="grilled asparagus", 
                                             servings=2,
                                             servings_amt=0.5,
                                             servings_units='lbs'), 
            2, 
            "Failed to add recipe")
        
        # Test that we can't add a recipe of the same name
        # First add extra ingredient in test_recipe2:
        self.DataLoader.add_ingredients_from_csv(path_to_ingr_csv=os.path.join(TEST_DATA_PATH, "test_recipe_ingr2.csv"))
        path_to_recipe_csv2 = os.path.join(TEST_DATA_PATH, "test_recipe2.csv")
        with self.assertRaises(psql_errors.UniqueViolation):
            self.DataLoader.add_recipe_from_csv(path_to_recipe_csv=path_to_recipe_csv2, recipe_name="grilled asparagus", servings=2, servings_amt=0.5, servings_units='lbs')

        # Test that we can't add the same set of ingredients under a different recipe name
        with self.assertRaises(ValueError):
            self.DataLoader.add_recipe_from_csv(path_to_recipe_csv=path_to_recipe_csv, recipe_name="other asparagus", servings=2, servings_amt=0.5, servings_units='lbs')

        # Test that we can add a recipe with the additional ingredient (but not the same recipe name)
        # should add 3 rows, 2 of them duplicates except for recipe_id, because we allow that
        self.assertEqual(
            self.DataLoader.add_recipe_from_csv(path_to_recipe_csv=path_to_recipe_csv2, 
                                             recipe_name="onion asparagus", 
                                             servings=1,
                                             servings_amt=0.5, 
                                             servings_units='lbs'), 
            3, 
            "Failed to add recipe with some duplicate ingredients")
        
    def test_add_meals_via_staging(self):
        path_to_meals_csv = os.path.join(TEST_DATA_PATH,"test_meals.csv")

        # Add everything we need:
        self.DataLoader.add_ingredients_from_csv(path_to_ingr_csv=os.path.join(TEST_DATA_PATH, "test_meals_ingr.csv"))
        self.DataLoader.add_recipe_from_csv(path_to_recipe_csv=os.path.join(TEST_DATA_PATH, "test_meals_recipe.csv"),
                                            recipe_name="burger", 
                                            servings=4,
                                            servings_amt=0.4,
                                            servings_units='lbs')
        self.DataLoader.add_recipe_from_csv(path_to_recipe_csv=os.path.join(TEST_DATA_PATH,"test_meals_recipe2.csv"), 
                                             recipe_name="steamed broccoli", 
                                             servings=2,
                                             servings_amt=0.5, 
                                             servings_units='lbs')
        # Test that we can't add meals if one recipe isn't in the db:
        with self.assertRaises(ValueError):
            self.DataLoader.add_meals_via_staging(path_to_meals_csv=path_to_meals_csv)

        # Add missing recipe:
        self.DataLoader.add_recipe_from_csv(path_to_recipe_csv=os.path.join(TEST_DATA_PATH, "test_meals_recipe3.csv"),
                                         recipe_name="lemonade",
                                         servings=6,
                                         servings_amt=1,
                                         servings_units='pint'
                                         )
        # Now adding meals should run:
        self.assertEqual(self.DataLoader.add_meals_via_staging(path_to_meals_csv=path_to_meals_csv),3)

    def test_csv_to_dataclass(self):
        # First: test generic behavior on a dataclass that looks nothing like fork_dataclasses.
        # Note the csv columns are in a different order than _Gizmo's fields: correspondence
        # is by name, so order shouldn't matter.
        gizmos = self.DataLoader.csv_to_dataclass(
            path_to_csv=os.path.join(TEST_DATA_PATH, "test_arbitrary_dataclass.csv"), cls=_Gizmo)

        self.assertEqual(gizmos[0].label, "Sprocket")     # str passthrough
        self.assertEqual(gizmos[0].weight, 2.5)           # float parser
        self.assertTrue(gizmos[0].shiny)                  # '1' -> bool(int) -> True
        self.assertFalse(gizmos[1].shiny)                 # '0' -> False (not the truthy-string bug)
        self.assertEqual(gizmos[0].size_units, "c")       # ' cup' -> fix_units -> 'c'
        self.assertEqual(gizmos[1].size_units, "lbs")     # 'lb'   -> fix_units -> 'lbs'

        # Wrong value type in a row: non-numeric where float is expected -> ValueError.
        with self.subTest("wrong value type"):
            path = self._write_tmp_csv("shiny,size_units,label,weight\n1,cup,Sprocket,heavy\n")
            with self.assertRaises(ValueError):
                self.DataLoader.csv_to_dataclass(path_to_csv=path, cls=_Gizmo)

        # No header: DictReader treats the first (data) row as the header, so the column
        # names won't match the expected fields -> ValueError.
        with self.subTest("no header"):
            path = self._write_tmp_csv("1,cup,Sprocket,2.5\n0,lb,Widget,10\n")
            with self.assertRaises(ValueError):
                self.DataLoader.csv_to_dataclass(path_to_csv=path, cls=_Gizmo)

        # Wrong header - easy-to-miss trailing whitespace in a column name.
        with self.subTest("whitespace in header name"):
            path = self._write_tmp_csv("shiny,size_units,label,weight \n1,cup,Sprocket,2.5\n")
            with self.assertRaises(ValueError):
                self.DataLoader.csv_to_dataclass(path_to_csv=path, cls=_Gizmo)

        # Empty file: reader.fieldnames is None -> guarded by `or []` -> ValueError, not TypeError.
        with self.subTest("empty file"):
            path = self._write_tmp_csv("")
            with self.assertRaises(ValueError):
                self.DataLoader.csv_to_dataclass(path_to_csv=path, cls=_Gizmo)

        # Now test cases that match actual Forkwise loads
        # Check loading pantry items from csv
        items = self.DataLoader.csv_to_dataclass(
            path_to_csv=os.path.join(TEST_DATA_PATH, 'test_ingrs_to_csv.csv'), cls=PantryItem)

        self.assertEqual(items[0].name, 'Cream cheese')
        self.assertEqual(items[1].name, 'Strawberries')

        self.assertEqual(items[0].unitary_amt, 2)
        self.assertEqual(items[1].unitary_amt, 144)

        # Check units were fixed - remove spaces
        self.assertEqual(items[0].units, 'Tbsp')
        self.assertEqual(items[1].units, 'G')

        # spot check some (nested) columns
        self.assertEqual(items[0].props.cal, 80)
        self.assertEqual(items[1].props.sugar_grams, 7)

        # check bool types
        self.assertTrue(items[0].props.animal)
        self.assertFalse(items[1].props.animal)

        # Check loading ingredients from csv
        ingrs = self.DataLoader.csv_to_dataclass(
            path_to_csv=os.path.join(TEST_DATA_PATH, "test_recipe.csv"), cls=Ingredient)
        self.assertEqual(ingrs[0].ingr_name, 'asparagus')

        ingrs_fixunit = self.DataLoader.csv_to_dataclass(
            path_to_csv=os.path.join(TEST_DATA_PATH, "test_recipe_fix_units.csv"), cls=Ingredient)
        self.assertEqual(ingrs_fixunit[1].ingredient_amt, 3.3)
        self.assertEqual(ingrs_fixunit[0].ingredient_units, 'lbs')

        with self.assertRaises(ValueError):
            self.DataLoader.csv_to_dataclass(
                path_to_csv=os.path.join(TEST_DATA_PATH, "test_recipe_wrong_type.csv"), cls=Ingredient)

    def test_add_recipe_to_pantry(self):
        # Add some ingredients - will be skipped if other tests have already run
        self.DataLoader.add_ingredients_from_csv(path_to_ingr_csv=os.path.join(TEST_DATA_PATH, "test_recipe_to_pantry_ingrs.csv"))
        # Add a recipe we'll then convert to a pantry item
        recipe_name = "Carrot Salad"
        self.DataLoader.add_recipe_from_csv(path_to_recipe_csv=os.path.join(TEST_DATA_PATH, "test_recipe_to_pantry_recipe.csv"),
                                            recipe_name=recipe_name,
                                            servings=2,
                                            servings_amt=0.5,
                                            servings_units="c")

        self.DataLoader.add_recipe_to_pantry(recipe_name=recipe_name)

        # This recipe is 5 carrots, 1 lemon, and 0.3 c olive oil, and makes 2 servings.
        # Carrot is 31 cal, 0.7 g protein, and 7.3 g carbs; lemon is 17 cal, 0.6 g protein, and 5.4 g carbs.
        # Those are both per unit so no unit conversion.
        # Olive oil is 120 cal per Tbsp, 0 protein, 0 carb; will need unit conversion here.
        per_serv_cal = (5*31+1*17+(0.3*48/3)*120)/2
        per_serv_prot = (5*0.7+1*0.6+(0.3*48/3)*0)/2
        per_serv_carb = (5*7.3+1*5.4+(0.3*48/3)*0)/2

        with ForkDB(user=self.params["user"], pw=self.params["user_pw"], db_name=self.params["test_db_name"]) as dbconn:
            vals_dict_list = dbconn.execute_query("SELECT unitary_amt, cal, protein_grams, carb_grams, animal FROM pantry_items WHERE name=%s;",(recipe_name,))
        self.assertEqual(per_serv_cal, vals_dict_list[0]["cal"])
        self.assertEqual(per_serv_prot, vals_dict_list[0]["protein_grams"])
        self.assertEqual(per_serv_carb, vals_dict_list[0]["carb_grams"])
        # self.assertFalse(vals_dict_list[0]["animal"])
        self.assertEqual(0.5, vals_dict_list[0]["unitary_amt"])
    
    def test_add_recipe_from_pantry(self):
        # Add a pantry item that we will then promote to a recipe

        # First test we get an error if the item to promote isn't in the db already
        with self.assertRaises(ValueError):
            _ = self.DataLoader.add_recipe_from_pantry(name='apple', servings=1, servings_amt=1, servings_units='unit')

        # Now add the item
        apple_props = FoodProps(cal=95, fiber_grams=4, sugar_grams=19, protein_grams=0, fat_grams=0, carb_grams=25, animal=False, white_flour=False)
        new_pantry_item = PantryItem(name='apple', unitary_amt=1, units='unit', props=apple_props)
        _ = self.DataLoader.add_ingredients_via_staging(pantry_items=[new_pantry_item])

        num_rows_added = self.DataLoader.add_recipe_from_pantry(name='apple', servings=1, servings_amt=1, servings_units='unit')

        self.assertEqual(num_rows_added, 1)

        with ForkDB(user=self.params["user"], pw=self.params["user_pw"], db_name=self.params["test_db_name"]) as dbconn:
            new_ingr = dbconn.list_ingredients_per_recipe(recipe_name='apple')
        self.assertEqual(len(new_ingr),1)