"""
Class that loads data (from csvs or other sources) into the db.

Copyright (c) 2026 Stephanie Johnson
"""

import logging

from dataclasses import fields
from functools import wraps

from forkwise.fork_db import ForkDB
from forkwise.fork_dataclasses import FoodProps, PantryItem, Ingredient

class DataLoader:
    def __init__(self, user: str, pw: str, db_name: str):
        self.conn = ForkDB(user=user, pw=pw, db_name=db_name)

        self._logger = logging.getLogger(__name__)

        # TODO is there a way to avoid having to know PantryItem props needs to be special cased?
        self.pantry_col_defs = [(f.name, f.metadata['sql_type']) for f in fields(PantryItem) if f.name not in ["props"]] + [(f.name, f.metadata['sql_type']) for f in fields(FoodProps)]

        self.pantry_col_names = ", ".join(f'{a}' for a, _ in self.pantry_col_defs) 

        self.ingr_col_defs = [(f.name, f.metadata['sql_type']) for f in fields(Ingredient)]

        self.meal_col_defs = [('date','date'), ('recipe_name','text'), ('servings','real')]
    
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
        self._logger.info(f"Added {num_rows_added} to unit_conversions table")
        return num_rows_added
    
    @clean_up_staging
    def add_ingredients_via_staging(self, path_to_ingr_csv: str) -> int:
        # Will skip any row for which ingredient name is already in the db.
        # Returns number of rows added to pantry_items table.

        self.conn.create_staging(col_defs=self.pantry_col_defs)
        rows_staged = self.conn.csv_to_staging(csv_path=path_to_ingr_csv, csv_columns=self.pantry_col_defs)

        if rows_staged == 0:
            self._logger.info(f"No ingredients loaded from source file {path_to_ingr_csv} to staging table; no ingredeints will be added to db")
            return 0
        
        # WARN if an ingredient is added under a different name but every other value the same.
        dups = self.conn.check_dup_ingr()
        if len(dups)>0:
            msg=f"Source file {path_to_ingr_csv} contains rows identical to existing pantry items except for the name: (name in file, name in db) {dups}"
            self._logger.warning(msg)

        num_rows_added = self.conn.staging_to_pantry()
        self._logger.info(f"Added {num_rows_added} to pantry_items table")

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
                               path_to_recipe_csv: str, 
                               name: str, 
                               servings: float,
                               servings_amt: float,
                               servings_units: str) -> int:
        """
        Add recipe from csv via a staging table.

        Parameters
        ----------
        path_to_recipe_csv : str
           Path to a recipe: each row is an ingredient (name, amount, units).
           Name must already be an ingredient in the db in pantry_items table.
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
    
        self.conn.create_staging(col_defs=self.ingr_col_defs)
        rows_staged = self.conn.csv_to_staging(csv_path=path_to_recipe_csv, csv_columns=self.ingr_col_defs)

        if rows_staged == 0:
            self._logger.info(f"No recipe loaded from source file {path_to_recipe_csv} to staging table, will not be added to db")
            return 0
        
        # A recipe can only be added if all ingredients are already in the db, with units in categories that match pantry_items.
        # Check first, error with a list of missing ingredients:
        ingr_missing = self.conn.check_ingr_exist()
        if len(ingr_missing) > 0:
            msg = f"Cannot load recipe: {name}. Ingredients missing from db and/or units aren't in db and/or unit category mismatch: (name, recipe units, db units) {ingr_missing}"
            self._logger.error(msg)
            raise ValueError(msg)

        # We also don't allow duplicate recipes. A duplicate is same name, or same ingredients+amounts for a single recipe_id:
        # Check the latter condition first. 
        check_dups = self.conn.check_dup_recipe()
        if len(check_dups) > 0:
            recipe_id, num_comps = zip(*check_dups)
            same_comps = sum([x==rows_staged for x in num_comps])
            if same_comps>0:
                recipe_name = self.conn.get_recipe_name(recipe_id=recipe_id[0])
                msg = f"A recipe with ingredients in csv {path_to_recipe_csv} already exists (name: {recipe_name}); nothing will be added"
                self._logger.error(msg)
                raise ValueError(msg)
        
        # Insert recipe name and servings into recipe table, unless a recipe by this name already exists:
        num_rows_added = self.conn.staging_to_recipe(name=name, servings=servings, servings_amt=servings_amt, servings_units=servings_units)
        self._logger.info(f"Added {num_rows_added} to ingredients table and recipe {name} to recipe table")
        
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
        
        self.conn.create_staging(col_defs=self.meal_col_defs)
        rows_staged = self.conn.csv_to_staging(csv_path=path_to_meals_csv, csv_columns=self.meal_col_defs)

        if rows_staged == 0:
            self._logger.info(f"No meals loaded from source file {path_to_meals_csv} to staging table, will not be added to db")
            return 0
        
        # Meals can only be added if all recipes are already in the db.
        # Check first, error with a list of missing recipes:
        recipe_missing = self.conn.check_recipe_exist()
        if len(recipe_missing) > 0:
            msg = f"Cannot load meals from {path_to_meals_csv}. Recipes missing from db: {list(zip(*recipe_missing))}"
            self._logger.error(msg)
            raise ValueError(msg)

        num_rows_added = self.conn.staging_to_meals()
        self._logger.info(f"Added {num_rows_added} to meals table")

        return num_rows_added