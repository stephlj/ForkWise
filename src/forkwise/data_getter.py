"""
Class that gets data from the db (for viz downstream).

Copyright (c) 2026 Stephanie Johnson
"""

import logging
import pandas as pd

from datetime import date
from typing import List

from forkwise.fork_db import ForkDB
from forkwise.fork_dataclasses import FoodProps, PantryItem, Ingredient, Recipe, Meal
from forkwise.fork_dataclasses import PANTRY_COL_DEFS, PANTRY_COL_NAMES, INGR_COL_DEFS, MEAL_COL_DEFS

class DataGetter:
    def __init__(self, user: str, pw: str, db_name: str):
        self.conn = ForkDB(user=user, pw=pw, db_name=db_name)

        self._logger = logging.getLogger(__name__)
    
    def close(self):
        # TODO there's some safety if's and try's I should add here
        self.conn.close()
    
    def __del__(self):
        # Fall back method to make sure connection is closed when garbage collected, again should
        # add some checking here TODO
        self.close()

    def __enter__(self):
        # Use DataLoader within a "with" clause
        return self
    
    def __exit__(self):
        self.close()    

    def get_recipe_totals(self, recipe_name: str) -> Recipe:
        """
        Calculate nutritional totals for a recipe. Note that the totals
        are for however many servings the recipe is for - NOT per serving!

        Parameters
        ----------
        recipe_name : str
            A recipe name in the db

        Returns:
        --------
        Recipe dataclass
        """

        
        recipe_tuple = self.conn.get_recipe_servings(recipe_name=recipe_name)
        if len(recipe_tuple)==0:
            msg = f"Recipe {recipe_name} does not exist"
            self._logger.error(msg)
            raise ValueError(msg)
        elif len(recipe_tuple) > 1:
            msg = f"Query to get recipe id from name returned multiple rows, something is wrong!"
            self._logger.error(msg)
            raise ValueError(msg)
        
        # TODO return this directly from schema
        recipe_dict_keys = ['id','name','servings','servings_amt', 'servings_units']
        recipe_dict = dict(zip(recipe_dict_keys,recipe_tuple[0]))

        totals_tuple = self.conn.calc_recipe_totals(recipe_id=recipe_dict['id'])
        if len(totals_tuple) != 1:
            msg = f"Query to get recipe totals from recipe {recipe_name} returned multiple rows, something is wrong!"
            self._logger.error(msg)
            raise ValueError(msg)
        # TODO get this from the db
        totals_dict_keys = [c for c in PANTRY_COL_NAMES if c not in {'name','unitary_amt','units'}]
        totals_dict_keys.append('count')
        totals_dict = dict(zip(totals_dict_keys,totals_tuple[0]))
        

        # Check that all units matched for conversions - otherwise the return from COUNT won't match
        # the number of ingredients in the recipe: (note this should be checked on recipe load regardless)
        correct_rows = self.conn.num_pantry_items_per_recipe(recipe_id=recipe_dict['id'])
        if correct_rows != totals_dict['count']:
            msg = "Unit conversions failed in recipe totaling - some rows were dropped"
            self._logger.error(msg)
            raise ValueError(msg)

        ingr_props = FoodProps(cal=totals_dict['cal'],
                      fat_grams=totals_dict['fat_grams'],
                      protein_grams=totals_dict['protein_grams'],
                      fiber_grams=totals_dict['fiber_grams'],
                      sugar_grams= totals_dict['sugar_grams'],
                      carb_grams= totals_dict['carb_grams'],
                      white_flour= bool(totals_dict['white_flour']),
                      animal= bool(totals_dict['animal'])
                      )

        return Recipe(name=recipe_name, 
                      servings = recipe_dict['servings'],
                      servings_amt=recipe_dict['servings_amt'],
                      servings_units=recipe_dict['servings_units'],
                      props = ingr_props
                      )
    
    def get_meals_in_dates(self, date_range: List[date]) -> List[Meal]:
        """
        Return a list of Meals in a date range. date_range is a list of length 2.
        """

        if len(date_range) != 2:
            log_msg = f"Date range must be list of length 2; got instead {date_range}"
            self._logger.error(log_msg)
            raise ValueError(log_msg)
        
        if (type(date_range[0]) != date) or (type(date_range[1]) != date):
            # date_range.sort() will do the wrong thing if this isn't date format
            log_msg = f"Date range must be in datetime.date format; got instead {date_range}"
            self._logger.error(log_msg)
            raise TypeError(log_msg)
        
        date_range.sort()

        recipes = self.conn.get_recipes_in_dates(date_range=(date_range[0],date_range[1]))

        # TODO refactor all of this
        meal_df = pd.DataFrame({"date_eaten":[r[0] for r in recipes],
                                "servings": [r[1] for r in recipes],
                                "name": [r[2] for r in recipes]
                                })
        grouped = meal_df.groupby("date_eaten")
        dates = list(grouped.groups.keys())
        meals = []
        for d in dates:
            recipe_list = []
            for r in grouped.get_group(d).name.to_list():
                recipe_list.append(self.get_recipe_totals(recipe_name=r)) # get_recipe_totals returns a Recipe
            meals.append(Meal(date_eaten=grouped.get_group(d).date_eaten.to_list()[0],
                              recipes=recipe_list,
                              servings_eaten=grouped.get_group(d).servings.to_list()
                              ))
        return meals