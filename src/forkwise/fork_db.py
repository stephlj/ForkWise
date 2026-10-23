"""
Class that connects to the database and manages interactions with it.

This is the database access layer; business logic should be elsewhere.

Copyright (c) 2026 Stephanie Johnson
"""

import logging

from psycopg import errors as psql_errors
from typing import List, Any
from datetime import date

from dbcommons.db_conn import DBConn
from forkwise.fork_dataclasses import (
    PANTRY_COL_NAMES, 
    INGR_COL_DEFS, 
    FOODPROPS_COL_DEFS, 
    FOODPROPS_COL_NAMES, 
    FoodProps,
    Meal
)

class ForkDB(DBConn):
    def __init__(self, user: str, pw: str, db_name: str):
        # Use super() because I've now override base class init
        super().__init__(user=user, pw=pw, db_name=db_name)
        self._logger = logging.getLogger(__name__)
    
    def get_recipe_name(self, recipe_id: int) -> str | None:
        return self.execute_scalar("SELECT name FROM recipes WHERE id=%s;", (recipe_id,))
    
    def get_recipe_servings(self, recipe_name: str)->List[dict]:
        # For a recipe, returns a (length-one) list of dicts with keys: id, servings, servings_amt, and servings_units
        return self.execute_query(f"SELECT id, servings, servings_amt, servings_units FROM recipes WHERE name=%s;", (recipe_name,))
    
    def get_totals_per_date_range(self, date_range: tuple[date])->List[dict]:
        # Returns a list of dicts, with keys 'date_eaten', 'servings_eaten', and PANTRY_COL_NAMES
        # Each element of the list is a row from the db query.
        # Values for each PANTRY_COL_NAMES is, e.g, cal from servings eaten of a recipe on that day (per recipe per day)

        # TODO extract this summation logic into a view (shared with calc_recipe_totals_per_serving)
        totals_statements = [f'SUM(i.ingredient_amt * (p.{c} / p.unitary_amt) * (iu.factor / pu.factor)) AS {c}' for c in FOODPROPS_COL_NAMES if c not in {'white_flour','animal'}]
        totals_statements.append('SUM(p.animal::int) AS animal')
        totals_statements.append('SUM(p.white_flour::int) AS white_flour')
        
        sum_statements = ", ".join(totals_statements)

        select_statements_list = [f't.{c} / r.servings * m.servings_eaten AS {c}' for c in FOODPROPS_COL_NAMES if c not in {'white_flour','animal'}]
        select_statements_list.append('t.animal')
        select_statements_list.append('t.white_flour')
        select_statements = ", ".join(select_statements_list)
        
        query=f"""
            WITH totals AS (
                SELECT i.recipe_id,
                {sum_statements}
                FROM pantry_items AS p
                INNER JOIN unit_conversions AS pu ON 
                    LOWER(pu.unit)=LOWER(p.units) 
                INNER JOIN ingredients AS i ON 
                    i.pantry_id=p.id 
                INNER JOIN unit_conversions AS iu ON 
                    LOWER(iu.unit)=LOWER(i.ingredient_units) AND
                    iu.category=pu.category
                GROUP BY i.recipe_id
            )
            SELECT m.date_eaten, 
                r.name AS recipe_name,
                {select_statements}
            FROM meals AS m
            INNER JOIN recipes AS r ON
                r.id = m.recipe_id
            INNER JOIN totals AS t ON
                t.recipe_id = r.id
            WHERE m.date_eaten BETWEEN %s AND %s
            ;
            """

        # Nested return classes are currently not supported by dbcommons; so we can't use execute_query_w_class
        # return self.execute_query_w_class(query, return_class=Totals, vals=(date_range[0],date_range[1]))

        return self.execute_query(query, vals=(date_range[0],date_range[1]))
    
    def calc_recipe_totals_per_serving(self, recipe_id: int, recipe_servings: float)->FoodProps:
        
        totals_per_recipe_statements = [f'SUM(i.ingredient_amt * (p.{c} / p.unitary_amt) * (iu.factor / pu.factor))  AS total_{c}' for c in FOODPROPS_COL_NAMES if c not in {'white_flour','animal'}]
        totals_per_recipe_statements.append('SUM(p.animal::int) AS animal')
        totals_per_recipe_statements.append('SUM(p.white_flour::int) AS white_flour')
        
        select_statements = ", ".join(totals_per_recipe_statements)

        query=f"""
            SELECT {select_statements},
                COUNT(*)
            FROM pantry_items AS p
            INNER JOIN unit_conversions AS pu ON 
                LOWER(pu.unit)=LOWER(p.units) 
            INNER JOIN ingredients AS i ON 
                i.pantry_id=p.id 
            INNER JOIN unit_conversions AS iu ON 
                LOWER(iu.unit)=LOWER(i.ingredient_units) AND
                iu.category=pu.category
            WHERE i.recipe_id=%s;
            """

        # Note: Can't use execute_query_w_class and return a class because
        # we're returning count and not returning things like name
        totals_dict_list = self.execute_query(query,(recipe_id,))
        if len(totals_dict_list)!=1:
            msg = f"Recipe with id {recipe_id} returned more than one row from the db, which shouldn't be possible! Something is wrong."
            self._logger.error(msg)
            raise ValueError(msg)
        totals_dict = totals_dict_list[0]

        # Check that all units matched for conversions - otherwise the return from COUNT won't match
        # the number of ingredients in the recipe: (note this should be checked on recipe load regardless)
        correct_rows = self.num_pantry_items_per_recipe(recipe_id=recipe_id)
        if correct_rows != totals_dict['count']:
            msg = "Unit conversions failed in recipe totaling - some rows were dropped"
            self._logger.error(msg)
            raise ValueError(msg)

        return FoodProps(cal=totals_dict['total_cal']/recipe_servings,
                      fat_grams=totals_dict['total_fat_grams']/recipe_servings,
                      protein_grams=totals_dict['total_protein_grams']/recipe_servings,
                      fiber_grams=totals_dict['total_fiber_grams']/recipe_servings,
                      sugar_grams= totals_dict['total_sugar_grams']/recipe_servings,
                      carb_grams= totals_dict['total_carb_grams']/recipe_servings,
                      white_flour= bool(totals_dict['white_flour']),
                      animal= bool(totals_dict['animal'])
                      )
    
    def list_all_recipes(self) -> List[str]:
        name_list = self.execute_query("SELECT name FROM recipes ORDER BY name;")
        return [a['name'] for a in name_list]
        # print("\n".join([a for a, _ in name_tuples]))

    def list_all_ingredients(self) -> List[str]:
        # Note what the user calls ingredients, the db calls pantry items
        name_list = self.execute_query("SELECT name FROM pantry_items ORDER BY name;")
        return [a['name'] for a in name_list]
    
    def list_ingredients_per_recipe(self, recipe_name: str) -> List[str]:
        query = f"""
            SELECT p.name
            FROM pantry_items AS p
            INNER JOIN ingredients i ON
                i.pantry_id = p.id
            INNER JOIN recipes r ON
                r.id = i.recipe_id
            WHERE r.name = %s;
        """
        ingr_list = self.execute_query(query, (recipe_name,))
        return [i['name'] for i in ingr_list]
    
    def list_all_units(self) -> List[str]:
        unit_list = self.execute_query("SELECT unit FROM unit_conversions ORDER BY category, factor;")
        return [a['unit'] for a in unit_list]

    def list_compatible_units(self) -> dict[str, List[str]]:
        # For all pantry items, list compatible units by category. E.g. if the pantry item is units of oz, 
        # list all weight units in the unit_conversions table. Dict key in return is pantry item name.
        q = """
            WITH joined AS (
                SELECT u.unit, u.category, p.name
                FROM unit_conversions AS u
                INNER JOIN pantry_items p ON
                    LOWER(u.unit) = LOWER(p.units)
            )
            SELECT ARRAY_AGG(uu.unit ORDER BY uu.factor) AS units_list, j.name 
            FROM joined AS j
            INNER JOIN unit_conversions AS uu ON
                uu.category = j.category
            GROUP BY j.name;
        """
        compatible_units = self.execute_query(q) 
        # compatible_units is a List[dict], one dict per row, key is column names (units_list, name)
        # Convert to a dict with keys: name
        return {d['name']: d['units_list'] for d in compatible_units}

    
    def check_units_exist(self)->List[dict]:
        # Check that all rows in staging have units that match rows in unit_conversions
        # Return is a list of dicts representing (staging.name, staging.units) where staging.units has 
        # no match in unit_conversions
        q = """
                SELECT s.name, s.units
                FROM staging AS s
                LEFT JOIN unit_conversions u ON
                    LOWER(s.units) = LOWER(u.unit)
                WHERE u.unit IS NULL;
            """
        return self.execute_query(q)
    
    def check_ingr_exist(self)->List[dict]:
        # Check all ingredients in staging have rows in pantry_items and units in unit_conversions
        # Return is a list of dicts of any missing items; 
        # each dict represents (staging.ingr_name, staging.ingredient_units, pantry_items.units)
        # (keys 'staging_ingredient_name', 'staging_ingredient_units', 'pantry_units')

        check_ingr = """
            SELECT s.ingr_name AS staging_ingredient_name, s.ingredient_units AS staging_ingredient_units, p.units AS pantry_units
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
    
    def check_recipe_exist(self)->List[dict]:
        # Return is a list of dicts of recipe names in staging that aren't in the recipes table in the db.
        # Dict keys are 'recipe_name'
        check_rec = """
            SELECT s.recipe_name
            FROM staging AS s
            LEFT JOIN recipes r ON
                LOWER(r.name) = LOWER(s.recipe_name)
            WHERE r.id IS NULL;
        """
        return self.execute_query(check_rec)
    
    def check_dup_ingr(self) -> List[dict]:
        # Check if there are any rows in the staging table that are the same as an existing row
        # in pantry_items execept for the name (ie, these items exist under a different name)
        # Return is a list of dicts representing (staging.name, pantry_items.name) for any duplicates
        join_statements = " AND ".join(f'p.{a} = s.{a}' for a, _ in FOODPROPS_COL_DEFS)
        check_dups = f"""
            SELECT s.name AS staging_name, p.name AS pantry_name
            FROM staging AS s
            INNER JOIN pantry_items p ON
                p.unitary_amt = s.unitary_amt AND
                LOWER(p.units) = LOWER(s.units) AND
                {join_statements}
            WHERE LOWER(s.name) != LOWER(p.name);
        """
        return self.execute_query(check_dups)
    
    def check_dup_recipe(self)->List[dict]:
        # Check whether staging contains a set of ingredients+amounts that matches an existing recipe under a different name
        # Join pantry_items onto staging to get pantry_item id; then ask whether the ingredients table already has
        # the same combo of (ingredient id, ingredient amt, ingredient units) associated with a single recipe id.
        # Return is a list of dicts with keys 'recipe_id', 'count' for any matches

        join_statements = " AND ".join(f'i.{a} = j.{a}' for a, _ in INGR_COL_DEFS if a != 'ingr_name')
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
                    i.pantry_id = j.id AND
                    {join_statements}
            )
            SELECT recipe_id, COUNT(*)
            FROM joined2
            GROUP BY recipe_id;
        """
        return self.execute_query(check_dup_ingredients)
        
    def check_dup_meals_in_staging(self)->List[dict]:
        # Check whether staging has more than one row with the same (date_eaten, recipe_name)
        # Note that staging for meals will have recipe_name, where the meals table has recipe_id
        
        q = f"""
            SELECT recipe_name, date_eaten, COUNT(*)
            FROM staging
            GROUP BY recipe_name, date_eaten
            HAVING COUNT(*) > 1;
        """

        return self.execute_query(query=q)

    def check_dup_meals(self)->List[dict]:
        # Check whether meals in staging already exist in the db (ignoring servings, just matching on date_eaten, recipe_name)
        # Note that staging for meals will have recipe_name, where the meals table has recipe_id, so we can't use execute_query_w_class
        
        q = f"""
            SELECT s.recipe_name, s.date_eaten
            FROM staging AS s
            INNER JOIN meals m ON
                (SELECT name FROM recipes r WHERE r.id = m.recipe_id) = s.recipe_name AND
                m.date_eaten = s.date_eaten
            ;
        """

        return self.execute_query(query=q)
    
    def num_pantry_items_per_recipe(self, recipe_id: int)->int:
        q=f"""
                SELECT COUNT(*)
                FROM pantry_items AS p
                INNER JOIN ingredients i ON
                    i.pantry_id=p.id
                WHERE i.recipe_id=%s;
            """
        return self.execute_scalar(q,(recipe_id,))
    
    def staging_to_units(self)->int:
        # We don't allow units with the same name (case insensitive)
        # so any rows in staging with the same unit name as a row 
        # existing in the db are skipped on insert.
        # This WILL error if the staged table contains multiple rows
        # with the same unit name, case insensitive (e.g. `c` and `C`) -
        # which you shouldn't be trying to load!
        conv_query = f"""
            WITH joined AS (
                SELECT s.*
                FROM staging AS s
                LEFT JOIN unit_conversions u ON
                    LOWER(u.unit) = LOWER(s.unit)
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

        col_names_str = ", ".join(PANTRY_COL_NAMES)
        staging_cols_str = ", ".join(f"s.{c}" for c in PANTRY_COL_NAMES)
        ingr_query = f"""
            INSERT INTO pantry_items ({col_names_str})
            SELECT {staging_cols_str}
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
            INSERT INTO ingredients (recipe_id, pantry_id, ingredient_amt, ingredient_units)
            SELECT %s, (SELECT id FROM pantry_items WHERE LOWER(name) = LOWER(s.ingr_name)), s.ingredient_amt, s.ingredient_units
            FROM staging AS s
            RETURNING *;
        """
        rows_added = self.execute_query(ingredient_query, (recipe_id,))
        return len(rows_added)
    
    def staging_to_meals(self)->int:
        # Add meals from staging to meals table.
        # Return is number of rows added to meals table.
        # Assumes input handling is done elsewhere - will incur a UniqueViolation if duplicates are attempted to be added, for example.

        q = """
            INSERT INTO meals (date_eaten, recipe_id, servings_eaten)
            SELECT s.date_eaten, (SELECT id FROM recipes WHERE LOWER(name) = LOWER(s.recipe_name)), s.servings_eaten
            FROM staging AS s
            RETURNING *;
        """
        rows_added = self.execute_query(q)

        return len(rows_added)
