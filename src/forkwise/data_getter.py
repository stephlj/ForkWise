"""
Class that gets data from the db (for viz downstream).

Copyright (c) 2026 Stephanie Johnson
"""

import logging
import pandas as pd

from datetime import date
from typing import List

from forkwise.fork_db import ForkDB
from forkwise.fork_dataclasses import Recipe, Meal

class DataGetter:
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

    def get_recipe_totals(self, recipe_name: str) -> Recipe:
        """
        Calculate nutritional totals for a recipe, PER SERVING.
        (This is different from how Recipes are stored in the db!)

        Parameters
        ----------
        recipe_name : str
            A recipe name in the db

        Returns:
        --------
        Recipe dataclass
        """
        
        recipe_info = self.conn.get_recipe_servings(recipe_name=recipe_name)
        if len(recipe_info)!=1:
            msg = f"Recipe name {recipe_name} returned more than one row from the db, which shouldn't be possible! Something is wrong."
            self._logger.error(msg)
            raise ValueError(msg)
        props_per_serving = self.conn.calc_recipe_totals_per_serving(recipe_id=recipe_info[0]["id"], recipe_servings=recipe_info[0]["servings"])

        return Recipe(name=recipe_name, 
                      servings = 1, # Because this is now PER SERVING
                      servings_amt=recipe_info[0]['servings_amt'],
                      servings_units=recipe_info[0]['servings_units'],
                      props = props_per_serving
                      )
    
    def get_totals_in_dates(self, date_range: List[date]) -> pd.DataFrame:
        """
        Return a DataFrame of meals eaten in a date range. date_range is a list of length 2.
        DataFrame has columns date_eaten, recipe_name, cal, fat_grams, etc.
        Each row represents the nutritional totals from servings_eaten of a recipe on a date
        (multiple rows will likely have the same date_eaten).
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

        # totals_dict_list will be a list of dicts, each dict having keys "date_eaten", "recipe_name",
        # and the values of PANTRY_COL_NAMES
        totals_dict_list = self.conn.get_totals_per_date_range(date_range=(date_range[0],date_range[1]))

        # Return empty df if no rows matched query
        if len(totals_dict_list) == 0:
            return pd.DataFrame()

        # Rearrange into a df
        df_cols = totals_dict_list[0].keys()
        return pd.DataFrame({c:[t[c] for t in totals_dict_list] for c in df_cols})