"""
Class that loads data (from csvs or other sources) into the db.

Copyright (c) 2026 Stephanie Johnson
"""

import os
import logging
import csv

from functools import wraps
from typing import List, Type, TypeVar
from dataclasses import fields, is_dataclass

from forkwise.fork_db import ForkDB
from forkwise.fork_dataclasses import PANTRY_COL_DEFS, INGR_COL_DEFS, MEAL_COL_DEFS, Ingredient, PantryItem, flat_col_defs

T = TypeVar("T")

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
            self._logger.warning(f"No pantry items were staged; nothing will be added to db")
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
    
    def csv_to_dataclass(self, path_to_csv: str, cls: Type[T]) -> List[T]:
        """
        Load a csv into a list of `cls` objects, one per row.

        Correspondence is by name: every csv column must match a field name of `cls`
        (or, for a nested dataclass field like PantryItem.props, a field name of that
        nested dataclass). Each field's metadata['csv_parser'] turns the string cell
        into the field's value, so there's no hand-written column->field mapping.

        Parameters
        ----------
        path_to_csv : str
            Path to a csv whose header holds every (flattened) field name of `cls`.
        cls : Type[T]
            A dataclass whose fields carry 'csv_parser' metadata.

        Returns
        -------
        List[T]
        """

        # Basic input checking
        if not os.path.isfile(path_to_csv):
            msg = f"{path_to_csv} not a path to a file that exists"
            self._logger.error(msg)
            raise ValueError(msg)

        if not os.path.splitext(path_to_csv)[1] == ".csv":
            msg = f"{path_to_csv} must be a csv file"
            self._logger.error(msg)
            raise ValueError(msg)

        # Expected columns are cls's (flattened) field names - the single source of
        # truth shared with the db staging col defs.
        expected_cols = [name for name, _ in flat_col_defs(cls)]

        with open(path_to_csv, mode='r') as f:
            reader = csv.DictReader(f)
            if set(reader.fieldnames or []) != set(expected_cols):
                msg = f"Wrong header in {path_to_csv}: needs to be {expected_cols} (instead of {reader.fieldnames})"
                self._logger.error(msg)
                raise ValueError(msg)

            objs = []
            for r in reader:
                kwargs = {}
                for field_ in fields(cls):
                    if is_dataclass(field_.type):
                        # Nested dataclass (e.g. props): build from its own fields in this row.
                        kwargs[field_.name] = field_.type(**{nf.name: nf.metadata['csv_parser'](r[nf.name])
                                                              for nf in fields(field_.type)})
                    else:
                        kwargs[field_.name] = field_.metadata['csv_parser'](r[field_.name])
                objs.append(cls(**kwargs))

        return objs

    def add_recipe_from_pantry(self, name: str, servings: float, servings_amt: float, servings_units: str) -> int:
        # Promote a pantry item to a recipe
        # Note that the servings_amt can be different for a recipe version than for the pantry item itself,
        # so these have to be passed in as args.
        # Return is number of rows added to ingredients table (as usual for adding a recipe)
        
        # Note all checking that this ingredient exists as a pantry item and that the unit types match is handled
        # in add_recipe_via_staging
        ingrs = [Ingredient(ingr_name=name, ingredient_amt=servings_amt, ingredient_units=servings_units)]

        num_ingr_rows_added = self.add_recipe_via_staging(ingredients=ingrs,
                                           name=name,
                                           servings=servings,
                                           servings_amt=servings_amt,
                                           servings_units=servings_units)
        
        if num_ingr_rows_added > 0:
            self._logger.info(f"Added {name} as a recipe")
        else:
            msg = f"Failed to add {name} as a recipe"
            self._logger.error(msg)
            raise ValueError(msg)
        
        return num_ingr_rows_added

    def add_recipe_to_pantry(self, recipe_name: str) -> None:
        # Convert a recipe to a pantry item.

        recipe_info = self.conn.get_recipe_servings(recipe_name=recipe_name)
        totals = self.conn.calc_recipe_totals_per_serving(recipe_id=recipe_info[0]["id"], recipe_servings = recipe_info[0]["servings"]) # Returns a FoodProps
        
        new_pantry_item =  PantryItem(name=recipe_name, 
                          unitary_amt=recipe_info[0]["servings_amt"], 
                          units=recipe_info[0]["servings_units"], 
                          props = totals)
    
        num_rows_pantry_added = self.add_ingredients_via_staging(pantry_items=[new_pantry_item])

        if num_rows_pantry_added == 1:
            self._logger.info(f"Added {recipe_name} as pantry item")
        else:
            msg = f"Failed to add {recipe_name} as a single pantry item"
            self._logger.error(msg)
            raise ValueError(msg)
    
    def add_ingredients_from_csv(self, path_to_ingr_csv: str)-> int:
        
        items = self.csv_to_dataclass(path_to_csv=path_to_ingr_csv, cls=PantryItem)

        return self.add_ingredients_via_staging(pantry_items=items)
    
    def add_recipe_from_csv(self, 
                            path_to_recipe_csv: str, 
                            recipe_name: str,
                            servings: float,
                            servings_amt: float,
                            servings_units: str,
                            )-> int:
        
        ingrs = self.csv_to_dataclass(path_to_csv=path_to_recipe_csv, cls=Ingredient)

        return self.add_recipe_via_staging(ingredients=ingrs, 
                                        name=recipe_name, 
                                        servings=servings, 
                                        servings_amt=servings_amt, 
                                        servings_units=servings_units
                                        )