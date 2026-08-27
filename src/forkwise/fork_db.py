"""
Class that connects to the database and manages interactions with it.

This is the database access layer; business logic should be elsewhere.

Copyright (c) 2026 Stephanie Johnson
"""

import logging
import pandas as pd

from datetime import date
from psycopg import errors as psql_errors
from typing import List

from dbcommons.db_conn import DBConn
from forkwise.fork_dataclasses import FoodProps, PantryItem, Ingredient, Recipe, Meal

class ForkDB(DBConn):
    def __init__(self, user: str, pw: str, db_name: str):
        # Use super() because I've now override base class init
        super().__init__(user=user, pw=pw, db_name=db_name)
        self._logger = logging.getLogger(__name__)
    
    def get_recipe_name(self, recipe_id: int) -> int | None:
        return self.execute_scalar("SELECT name FROM recipes WHERE id=%s;", (recipe_id,))
    
    def list_all_recipes(self) -> List[str]:
        name_tuples = self.execute_query("SELECT name FROM recipes ORDER BY name;")
        return [a[0] for a in name_tuples]
        # print("\n".join([a for a, _ in name_tuples]))

    def list_all_ingredients(self) -> List[str]:
        # Note what the user calls ingredients, the db calls pantry items
        name_tuples = self.execute_query("SELECT name FROM pantry_items ORDER BY name;")
        return [a[0] for a in name_tuples]
    
    #TODO
    def list_ingredients_per_recipe(self) -> List[str]:
        pass
    
    def check_units_exist(self)->List[tuple]:
        # Check that all rows in staging have units that match rows in unit_conversions
        # Return is a list of (staging.name, staging.units) where staging.units has 
        # no match in unit_conversions
        q = """
                SELECT s.name, s.units
                FROM staging AS s
                LEFT JOIN unit_conversions u ON
                    LOWER(s.units) = LOWER(u.unit)
                WHERE u.unit IS NULL;
            """
        return self.execute_query(q)
    
    def check_ingr_exist(self)->List[tuple]:
        # Check all ingredients in staging have rows in pantry_items and units in unit_conversions
        # Return is a list of tuples of any missing items (staging.ingr_name, staging.ingredient_units, pantry_items.units)

        check_ingr = """
            SELECT s.ingr_name, s.ingredient_units, p.units
            FROM staging AS s
            LEFT JOIN unit_conversions AS su ON
                LOWER(su.unit) = LOWER(s.ingredient_units)
            LEFT JOIN pantry_items p ON
                LOWER(p.name) = LOWER(s.ingr_name)
            LEFT JOIN unit_conversions AS pu ON
                LOWER(pu.unit) = LOWER(p.units) AND
                pu.category = su.category
            WHERE p.id IS NULL OR pu.id IS NULL;
        """
        return self.execute_query(check_ingr)
    
    def check_recipe_exist(self)->List[tuple]:
        # Return is a list of tuples of recipe names in staging that aren't in the recipes table in the db
        check_rec = """
            SELECT s.recipe_name
            FROM staging AS s
            LEFT JOIN recipes r ON
                LOWER(r.name) = LOWER(s.recipe_name)
            WHERE r.id IS NULL;
        """
        return self.execute_query(check_rec)
    
    def check_dup_ingr(self) -> List[tuple]:
        # Check if there are any rows in the staging table that are the same as an existing row
        # in pantry_items execept for the name (ie, these items exist under a different name)
        # Return is a list of tuples: (staging.name, pantry_items.name) for any duplicates
        join_statements = " AND ".join(f'p.{a} = s.{a}' for a, _ in self.pantry_col_defs[3:])
        check_dups = f"""
            SELECT s.name, p.name
            FROM staging AS s
            INNER JOIN pantry_items p ON
                p.unitary_amt = s.unitary_amt AND
                LOWER(p.units) = LOWER(s.units) AND
                {join_statements}
            WHERE LOWER(s.name) != LOWER(p.name);
        """
        return self.execute_query(check_dups)
    
    def check_dup_recipe(self)->List[tuple]:
        # Check whether staging contains a set of ingredients+amounts that matches an existing recipe under a different name
        # Join pantry_items onto staging to get pantry_item id; then ask whether the ingredients table already has
        # the same combo of (ingredient id, ingredient amt, ingredient units) associated with a single recipe id.
        # Return is a list of tuples of (recipe_id, count) for any matches

        join_statements = " AND ".join(f'i.{a} = j.{a}' for a, _ in self.ingr_col_defs[1:])
        # Equivalent to: LEFT JOIN pantry_items p ON ... WHERE p.id IS NOT NULL
        check_dup_ingredients = f"""
            WITH joined1 AS (
                SELECT s.*, p.id
                FROM staging AS s
                INNER JOIN pantry_items p ON
                    LOWER(p.name) = LOWER(s.ingr_name)
            ),
            joined2 AS (
                SELECT j.*, i.recipe_id
                FROM joined1 AS j
                INNER JOIN ingredients i ON
                    i.ingredient_id = j.id AND
                    {join_statements}
            )
            SELECT recipe_id, COUNT(*)
            FROM joined2
            GROUP BY recipe_id;
        """
        return self.execute_query(check_dup_ingredients)
        
    def staging_to_units(self)->int:
        # This will throw a UniqueViolation if any row is already in the conversions table:
        # conv_query = "INSERT INTO unit_conversions (unit_from, unit_to, factor) SELECT * FROM staging RETURNING *;"
        # Instead, just don't add duplicates:
        conv_query = f"""
            WITH joined AS (
                SELECT s.*
                FROM staging AS s
                LEFT JOIN unit_conversions u ON
                    u.unit = s.unit AND
                    u.category = s.category AND
                    u.factor = s.factor
                    WHERE u.id IS NULL
                )
            INSERT INTO unit_conversions (unit, category, factor)
            SELECT *
            FROM joined
            RETURNING *;
        """ 
        rows_added = self.execute_query(conv_query)
        return len(rows_added)
    
    def staging_to_pantry(self)->int:
        # Insert contents of staging into pantry_items
        # Skips any rows in staging with the same name as rows 
        # already in pantry_items; skips any rows in staging
        # that don't have units that match rows in unit_conversions.
        # Return is number of rows inserted into pantry_items.

        ingr_query = f"""
            INSERT INTO pantry_items ({self.pantry_col_names})
            SELECT s.*
                FROM staging AS s
                LEFT JOIN pantry_items p ON
                    LOWER(p.name) = LOWER(s.name)
                INNER JOIN unit_conversions u ON
                    LOWER(s.units) = LOWER(u.unit)
                WHERE p.id IS NULL
            RETURNING *;
        """ 
        rows_added = self.execute_query(ingr_query)
        return len(rows_added)

    def staging_to_recipe(self, name: str, servings: float, servings_amt: float, servings_units: str)->int:
        # Insert recipe name and servings into recipe table, unless a recipe by this name already exists:
        # Return is number of rows added to INGREDIENTS table
        try:
            recipe_id = self.execute_scalar(
                "INSERT INTO recipes (name, servings, servings_amt, servings_units) VALUES (%s,%s, %s, %s) RETURNING id;", 
                (name, servings, servings_amt, servings_units)
                )
        except psql_errors.UniqueViolation:
            self._logger.error(f"A recipe with name {name} already exists in db; nothing will be added")
            raise

        # then insert into ingredients table
        ingredient_query = """
            INSERT INTO ingredients (recipe_id, ingredient_id, ingredient_amt, ingredient_units)
            SELECT %s, (SELECT id FROM pantry_items WHERE LOWER(name) = LOWER(s.ingr_name)), s.ingredient_amt, s.ingredient_units
            FROM staging AS s
            RETURNING *;
        """
        rows_added = self.execute_query(ingredient_query, (recipe_id,))
        return len(rows_added)
    
    def staging_to_meals(self)->int:
        # Add meals from staging to meals table.
        # Return is number of rows added to meals table.
        q = """
            INSERT INTO meals (date, recipe_id, recipe_servings)
            SELECT s.date, (SELECT id FROM recipes WHERE LOWER(name) = LOWER(s.recipe_name)), s.servings
            FROM staging AS s
            RETURNING *;
        """
        rows_added = self.execute_query(q)

        return len(rows_added)
    
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

        # TODO have execute_query in dbcommons return column names - return a dict rather than the raw tuple.
        # column_names = [desc[0] for desc in cursor.description] # have not tested this
        recipe_dict_keys = ['id','servings','servings_amt', 'servings_units']
        recipe_cols = ", ".join(recipe_dict_keys)
        recipe_tuple = self.execute_query(f"SELECT {recipe_cols} FROM recipes WHERE name=%s;", (recipe_name,))
        if len(recipe_tuple)==0:
            msg = f"Recipe {recipe_name} does not exist"
            self._logger.error(msg)
            raise ValueError(msg)
        elif len(recipe_tuple) > 1:
            msg = f"Query to get recipe id from name returned multiple rows, something is wrong!"
            self._logger.error(msg)
            raise ValueError(msg)
        recipe_dict = dict(zip(recipe_dict_keys,recipe_tuple[0]))

        totals_dict_keys = [c for c in self.pantry_col_names if c not in {'name','unitary_amt','units'}]
        totals_dict_keys.append('count')
        select_statements = ", ".join(f'SUM(i.ingredient_amt * (p.{c} / p.unitary_amt) * (iu.factor / pu.factor))  AS total_{c}' for c in totals_dict_keys if c not in {'white_flour','animal', 'count'})

        query=f"""
            SELECT {select_statements},
                SUM(p.animal::int) AS animal,
                SUM(p.white_flour::int) AS white_flour,
                COUNT(*)
            FROM pantry_items AS p
            INNER JOIN unit_conversions AS pu ON 
                LOWER(pu.unit)=LOWER(p.units) 
            INNER JOIN ingredients AS i ON 
                i.ingredient_id=p.id 
            INNER JOIN unit_conversions AS iu ON 
                LOWER(iu.unit)=LOWER(i.ingredient_units) AND
                iu.category=pu.category
            WHERE i.recipe_id=%s;
            """

        totals_tuple = self.execute_query(query,(recipe_dict['id'],))
        if len(totals_tuple) != 1:
            msg = f"Query to get recipe totals from recipe {recipe_name} returned multiple rows, something is wrong!"
            self._logger.error(msg)
            raise ValueError(msg)
        totals_dict = dict(zip(totals_dict_keys,totals_tuple[0]))
        

        # Check that all units matched for conversions - otherwise the return from COUNT won't match
        # the number of ingredients in the recipe: (note this should be checked on recipe load regardless)
        check_query=f"""
            SELECT COUNT(*)
            FROM pantry_items AS p
            INNER JOIN ingredients i ON
                i.ingredient_id=p.id
            WHERE i.recipe_id=%s;
        """
        correct_rows = self.execute_scalar(check_query,(recipe_dict['id'],))

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

        query = """
            SELECT m.date, m.recipe_servings, r.name
            FROM meals AS m
            LEFT JOIN recipes AS r ON
                r.id = m.recipe_id
            WHERE date BETWEEN %s AND %s;
        """

        recipes = self.execute_query(query, (date_range[0],date_range[1]))

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
