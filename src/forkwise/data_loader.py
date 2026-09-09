"""
Class that loads data (from csvs or other sources) into the db.

Copyright (c) 2026 Stephanie Johnson
"""

import os
import logging
import csv

from functools import wraps
from typing import List
from dataclasses import fields

from forkwise.utils import fix_units
from forkwise.fork_db import ForkDB
from forkwise.fork_dataclasses import PANTRY_COL_DEFS, PANTRY_COL_NAMES, INGR_COL_DEFS, MEAL_COL_DEFS, Ingredient, PantryItem, FoodProps

class DataLoader:
    def __init__(self, user: str, pw: str, db_name: str):
        self.conn = ForkDB(user=user, pw=pw, db_name=db_name)

        self._logger = logging.getLogger(__name__)

    def close(self):
        if getattr(self, "conn", None) is None:
            return
        try:
            self.conn.close()
        except Exception:
            self._logger.exception("DataLoader failed to close connection cleanly")
        finally:
            self.conn = None

    def __del__(self):
        # Fall back safety net to make sure connection is closed when garbage collected
        self.close()

    def __enter__(self):
        # Use DataLoader within a "with" clause
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
    
    def clean_up_staging(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            finally:
                self.conn.drop_staging()
        return wrapper
    
    @clean_up_staging
    def add_conversions(self, path_to_conversions_csv: str) -> int:
        # Add new unit conversions from a csv (mostly used during db init)
        # In future versions of Forkwise this will be pulled from the internet
        # Returns number of rows added to conversions table.

        col_defs = [('unit','text'),('category','text'),('factor','real')]
        self.conn.create_staging(col_defs=col_defs)
        rows_staged = self.conn.csv_to_staging(csv_path=path_to_conversions_csv, csv_columns=col_defs)

        if rows_staged == 0:
            msg=f"No unit conversions were staged from file {path_to_conversions_csv}; cannot load conversions"
            self._logger.error(msg)
            raise ValueError(msg)
        
        num_rows_added = self.conn.staging_to_units()
        self._logger.info(f"Added {num_rows_added} rows to unit_conversions table")
        return num_rows_added
    
    @clean_up_staging
    def add_ingredients_via_staging(self, pantry_items: List[PantryItem]) -> int:
        # Will skip any row for which panty_item name is already in the db.
        # Returns number of rows added to pantry_items table.

        self.conn.create_staging(col_defs=PANTRY_COL_DEFS)
        rows_staged = self.conn.class_to_staging(insert_cls=pantry_items)

        if rows_staged == 0:
            self._logger.info(f"No pantry items were staged; nothing will be added to db")
            return 0
        
        # WARN if an ingredient is added under a different name but every other value the same.
        dups = self.conn.check_dup_ingr()
        if len(dups)>0:
            msg=f"Input list with names {[p.name for p in pantry_items]} contains rows identical to existing pantry items except for the name: (name in input, name in db) {[tuple(d.values()) for d in dups]}"
            self._logger.warning(msg)

        num_rows_added = self.conn.staging_to_pantry()
        self._logger.info(f"Added {num_rows_added} rows to pantry_items table")

        if num_rows_added != rows_staged:
            # This can be for two reasons: There were duplicates, which we ignore;
            # or units didn't match anything in unit_conversions.
            # Warn for the latter:
            unmatched_units = self.conn.check_units_exist()
            if len(unmatched_units) > 0:
                msg = f"The following ingredients have units that aren't in the db and were skipped on load: {unmatched_units}"
                self._logger.warning(msg)

        return num_rows_added

    @clean_up_staging
    def add_recipe_via_staging(self, 
                               ingredients: List[Ingredient], 
                               name: str, 
                               servings: float,
                               servings_amt: float,
                               servings_units: str) -> int:
        """
        Add recipe via a staging table, so that we can perform some checks before inserting into db.

        Parameters
        ----------
        ingredients : List[Ingredient]
           List of Ingredients: name, amount, units.
           Names must already be in the db in pantry_items table.
           Units don't have to match pantry_items table units (can be converted later)-
           but must match unit type (weight, vol etc).
        name : str
            Recipe name.
        servings: float
            How many servings do the amounts in this recipe make in total.
        servings_amt : float
            Amount corresponding to one serving (e.g. 1, if 1 c is a serving)
        servings_units : str
            Units per serving amount, eg c if a serving is 1 c

        Returns
        -------
        int, number of rows added to ingredients table (NOT recipes table!)
        """
    
        self.conn.create_staging(col_defs=INGR_COL_DEFS)
        num_rows_staged = self.conn.class_to_staging(insert_cls=ingredients)

        if num_rows_staged == 0:
            self._logger.error(f"Failed to stage recipe, nothing will be added to db!")
            raise ValueError(f"Failed to stage recipe, nothing will be added to db!")
        
        # A recipe can only be added if all ingredients are already in the db, with units in categories that match pantry_items.
        # Check first, error with a list of missing ingredients:
        ingr_missing = self.conn.check_ingr_exist()
        if len(ingr_missing) > 0:
            msg = f"Cannot load recipe: {name}. Ingredients missing from db and/or units aren't in db and/or unit category mismatch: {ingr_missing}"
            self._logger.error(msg)
            raise ValueError(msg)

        # We also don't allow duplicate recipes. A duplicate is same name, or same ingredients+amounts for a single recipe_id:
        # Check the latter condition first. 
        check_dups = self.conn.check_dup_recipe()
        if len(check_dups) > 0:
            # check_dup_recipe doesn't compare number of ingredients that were a match to the length of the staging table;
            # do that here. Some recipe_id's might have been partial matches.
            for d in check_dups:
                if d['count'] == num_rows_staged:
                    recipe_name = self.conn.get_recipe_name(recipe_id=d['recipe_id'])
                    msg = f"A recipe with these ingredients already exists (name: {recipe_name}); nothing will be added for {name}"
                    self._logger.error(msg)
                    raise ValueError(msg)
        
        # Insert recipe name and servings into recipe table, unless a recipe by this name already exists:
        num_rows_added = self.conn.staging_to_recipe(name=name, servings=servings, servings_amt=servings_amt, servings_units=servings_units)
        self._logger.info(f"Added {num_rows_added} rows to ingredients table and recipe {name} to recipe table")
        
        return num_rows_added
    
    @clean_up_staging
    def add_meals_via_staging(self, path_to_meals_csv: str)->int:
        """
        Add meals from csv via a staging table.

        Parameters
        ----------
        path_to_meals_csv : str
           Path to a list of meals csvs. Each row is one recipe eaten on a date.
           Columns (no header) are: date, recipe name, servings.

        Returns
        -------
        int, number of rows added to meals table
        """
        
        self.conn.create_staging(col_defs=MEAL_COL_DEFS)
        rows_staged = self.conn.csv_to_staging(csv_path=path_to_meals_csv, csv_columns=MEAL_COL_DEFS)

        if rows_staged == 0:
            self._logger.info(f"No meals loaded from source file {path_to_meals_csv} to staging table, will not be added to db")
            return 0
        
        # Meals can only be added if all recipes are already in the db.
        # Check first, error with a list of missing recipes:
        recipe_missing = self.conn.check_recipe_exist()
        if len(recipe_missing) > 0:
            msg = f"Cannot load meals from {path_to_meals_csv}. Recipes missing from db: {[r['recipe_name'] for r in recipe_missing]}"
            self._logger.error(msg)
            raise ValueError(msg)

        num_rows_added = self.conn.staging_to_meals()
        self._logger.info(f"Added {num_rows_added} rows to meals table")

        return num_rows_added
    
    def csv_to_pantry(self, path_to_ingr_csv: str)->List[PantryItem]:
        """
        Load a csv of PantryItems into a list of PantryItems.

        Parameters
        ----------
        path_to_recipe_csv : str
            Path to a csv with header containing columns called the elements of PANTRY_COL_NAMES

        Returns
        -------
        List[PantryItems]
        """

        # Basic input checking
        if not os.path.isfile(path_to_ingr_csv):
            msg = f"{path_to_ingr_csv} not a path to a file that exists"
            self._logger.error(msg)
            raise ValueError(msg)
            
        if not os.path.splitext(path_to_ingr_csv)[1] == ".csv":
            msg = f"{path_to_ingr_csv} must be a csv file"
            self._logger.error(msg)
            raise ValueError(msg)

        with open(path_to_ingr_csv, mode='r') as f:
            reader = csv.DictReader(f)
            if set(reader.fieldnames) != set(PANTRY_COL_NAMES):
                msg = f"Wrong header in {path_to_ingr_csv}: needs to be {PANTRY_COL_NAMES} (instead of {reader.fieldnames})"
                self._logger.error(msg)
                raise ValueError(msg)
            # TODO can I generalize this / not hard code field names?
            items = [PantryItem(
                        name=r["name"], 
                        unitary_amt=float(r["unitary_amt"]), 
                        units=fix_units(r["units"]),
                        props=FoodProps(cal=float(r["cal"]),
                                        fiber_grams=float(r["fiber_grams"]),
                                        sugar_grams=float(r["sugar_grams"]),
                                        protein_grams=float(r["protein_grams"]),
                                        fat_grams=float(r["fat_grams"]),
                                        carb_grams=float(r["carb_grams"]),
                                        animal=bool(r["animal"]),
                                        white_flour=bool(r["animal"])
                                        )
                        ) 
                    for r in reader]

        return items

    def csv_to_recipe_ingr(self, path_to_recipe_csv: str)->List[Ingredient]:
        """
        In the db, a recipe is loaded as a list of Ingredients,
        plus servings amt, servings size, servings units, and
        a name for the recipe.

        When loaded from a csv, the csv contains only columns for
        ingredient name, amount, units.

        This function loads a recipe csv and returns a list of Ingredients.

        Parameters
        ----------
        path_to_recipe_csv : str
            Path to a csv with 3 columns: ingredient name, ingredient amount, ingredient units.

        Returns
        -------
        List[Ingredient]
        """

        # Basic input checking
        if not os.path.isfile(path_to_recipe_csv):
            msg = f"{path_to_recipe_csv} not a path to a file that exists"
            self._logger.error(msg)
            raise ValueError(msg)
            
        if not os.path.splitext(path_to_recipe_csv)[1] == ".csv":
            msg = f"{path_to_recipe_csv} must be a csv file"
            self._logger.error(msg)
            raise ValueError(msg)

        # TODO overhaul recipe input? Or not bother if I'm moving away from csvs?

        with open(path_to_recipe_csv, mode='r') as f:
            reader = csv.DictReader(f)
            if set(reader.fieldnames) != set([f.name for f in fields(Ingredient)]):
                msg = f"Wrong header in {path_to_recipe_csv}: needs to be {[f.name for f in fields(Ingredient)]} (instead of {reader.fieldnames})"
                self._logger.error(msg)
                raise ValueError(msg)
            # TODO can I generalize this / not hard code Ingredient field names?
            ingrs = [Ingredient(ingr_name=r["ingr_name"], ingredient_amt=float(r["ingredient_amt"]), ingredient_units=fix_units(r["ingredient_units"])) for r in reader]

        return ingrs
    
    def add_recipe_from_pantry(self, name: str, servings: float, servings_amt: float, servings_units: str) -> int:
        # Promote a pantry item to a recipe
        # Note that the servings_amt can be different for a recipe version than for the pantry item itself,
        # so these have to be passed in as args.
        # Return is number of rows added to ingredients table (as usual for adding a recipe)
        
        # Note all checking that this ingredient exists as a pantry item and that the unit types match is handled
        # in add_recipe_via_staging
        ingrs = [Ingredient(ingr_name=name, ingredient_amt=servings_amt, ingredient_units=servings_units)]

        return self.add_recipe_via_staging(ingredients=ingrs,
                                           name=name,
                                           servings=servings,
                                           servings_amt=servings_amt,
                                           servings_units=servings_units)

    def add_recipe_to_pantry(self):
        # Convert a recipe to a pantry item
        pass
    
    def add_ingredients_from_csv(self, path_to_ingr_csv: str)-> int:
        
        items = self.csv_to_pantry(path_to_ingr_csv=path_to_ingr_csv)

        return self.add_ingredients_via_staging(pantry_items=items)
    
    def add_recipe_from_csv(self, 
                            path_to_recipe_csv: str, 
                            recipe_name: str,
                            servings: float,
                            servings_amt: float,
                            servings_units: str,
                            )-> int:
        
        ingrs = self.csv_to_recipe_ingr(path_to_recipe_csv=path_to_recipe_csv)

        return self.add_recipe_via_staging(ingredients=ingrs, 
                                        name=recipe_name, 
                                        servings=servings, 
                                        servings_amt=servings_amt, 
                                        servings_units=servings_units
                                        )