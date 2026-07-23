"""
Class that connects to the database and manages interactions with it.

This is the database access layer; business logic should be elsewhere.

Copyright (c) 2026 Stephanie Johnson
"""

import logging

from dataclasses import fields
from datetime import date
from psycopg import errors as psql_errors
from typing import List

from dbcommons.db_conn import DBConn
from forkwise.fork_dataclasses import FoodProps, PantryItem, Ingredient, Recipe

class ForkDB(DBConn):
    def __init__(self, user: str, pw: str, db_name: str):
        # Use super() because I've now override base class init
        super().__init__(user=user, pw=pw, db_name=db_name)
        self._logger = logging.getLogger(__name__)

    def get_recipe_name(self, recipe_id: int) -> int | None:
        return self.execute_scalar("SELECT name FROM recipes WHERE id=%s;", (recipe_id,))
    
    def list_all_recipes(self) -> List[str]:
        name_tuples = self.execute_query("SELECT name FROM recipes;")
        return [a[0] for a in name_tuples]
        # print("\n".join([a for a, _ in name_tuples]))
    
    def add_conversions(self, path_to_conversions_csv: str) -> int:
        # Add new unit conversions from a csv (mostly used during db init)
        # In future versions of Forkwise this will be pulled from the internet
        # Returns number of rows added to conversions table.

        col_defs = [('unit','text'),('category','text'),('factor','real')]
        rows_staged = self.csv_to_staging(csv_path=path_to_conversions_csv, csv_columns=col_defs)

        if rows_staged == 0:
            msg=f"No unit conversions were staged from file {path_to_conversions_csv}; cannot load conversions"
            self._logger.error(msg)
            raise ValueError(msg)
        
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
        self._logger.info(f"Added {rows_added} to unit_conversions table")
        return len(rows_added)
    
    def add_ingredients_via_staging(self, path_to_ingr_csv: str) -> int:
        # Will skip any row for which (name, unitary_amt, units) are already in the db.
        # Returns number of rows added to pantry_items table.

        # TODO is there a way to avoid having to know PantryItem props needs to be special cased?
        ingr_col_defs = [(f.name, f.metadata['sql_type']) for f in fields(PantryItem) if f.name not in ["props"]] + [(f.name, f.metadata['sql_type']) for f in fields(FoodProps)]

        rows_staged = self.csv_to_staging(csv_path=path_to_ingr_csv, csv_columns=ingr_col_defs)

        if rows_staged == 0:
            self._logger.info("No ingredients loaded from source file to staging table; no ingredeints will be added to db")
            return 0
        
        col_names = ", ".join(f'{a}' for a, _ in ingr_col_defs)
        
        # This will throw a UniqueViolation if any rows in staging are already in the db pantry_items table
        # col_names_staging = ", ".join(f's.{a}' for a, _ in ingr_col_defs)
        # ingr_query = f"""
        #     INSERT INTO pantry_items ({col_names})
        #     SELECT {col_names_staging}
        #     FROM staging AS s
        #     RETURNING *;
        # """   
        
        join_statements = " AND ".join(f'p.{a} = s.{a}' for a, _ in ingr_col_defs[1:])
        ingr_query = f"""
            WITH joined AS (
                SELECT s.*
                FROM staging AS s
                LEFT JOIN pantry_items p ON
                    LOWER(p.name) = LOWER(s.name) AND
                    {join_statements}
                INNER JOIN unit_conversions u ON
                    LOWER(s.units) = LOWER(u.unit)
                WHERE p.id IS NULL
                )
            INSERT INTO pantry_items ({col_names})
            SELECT *
            FROM joined
            RETURNING *;
        """ 
        rows_added = self.execute_query(ingr_query)
        self._logger.info(f"Added {rows_added} to pantry_items table")

        if len(rows_added) != rows_staged:
            # This can be for two reasons: There were duplicates, which we ignore;
            # or units didn't match anything in unit_conversions.
            # Flag the latter:
            q = """
                SELECT s.name, s.units
                FROM staging AS s
                LEFT JOIN unit_conversions u ON
                    LOWER(s.units) = LOWER(u.unit)
                WHERE u.unit IS NULL;
            """
            unmatched_units = self.execute_query(q)
            if len(unmatched_units) > 0:
                msg = f"The following ingredients have units that aren't in the db and were skipped on load: {unmatched_units}"
                self._logger.warning(msg)

        return len(rows_added)
    
        # TODO drop staging? or let csv_to_staging handle that?

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
    
        ingr_col_defs = [(f.name, f.metadata['sql_type']) for f in fields(Ingredient)]

        rows_staged = self.csv_to_staging(csv_path=path_to_recipe_csv, csv_columns=ingr_col_defs)

        if rows_staged == 0:
            self._logger.info(f"No recipe loaded from source file {path_to_recipe_csv} to staging table, will not be added to db")
            return 0
        
        # A recipe can only be added if all ingredients are already in the db, with units in categories that match pantry_items.
        # Check first, error with a list of missing ingredients:
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
        ingr_missing = self.execute_query(check_ingr)
        if len(ingr_missing) > 0:
            msg = f"Cannot load recipe: {name}. Ingredients missing from db and/or units aren't in db and/or unit category mismatch: (name, recipe units, db units) {ingr_missing}"
            self._logger.error(msg)
            raise ValueError(msg)

        # We also don't allow duplicate recipes. A duplicate is same name, or same ingredients+amounts for a single recipe_id:
        # Check the latter condition first. Join pantry_items onto staging to get pantry_item id; then ask whether the ingredients table has
        # the same combo of (ingredient id, ingredient amt, ingredient units) associated with a single recipe id already as what's in staging.
        join_statements = " AND ".join(f'i.{a} = j.{a}' for a, _ in ingr_col_defs[1:])
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
        check_dups = self.execute_query(check_dup_ingredients)
        if len(check_dups) > 0:
            recipe_id, num_comps = zip(*check_dups)
            same_comps = sum([x==rows_staged for x in num_comps])
            if same_comps>0:
                recipe_name = self.get_recipe_name(recipe_id=recipe_id[0])
                msg = f"A recipe with ingredients in csv {path_to_recipe_csv} already exists (name: {recipe_name}); nothing will be added"
                self._logger.error(msg)
                raise ValueError(msg)
        
        # Insert recipe name and servings into recipe table, unless a recipe by this name already exists:
        try:
            recipe_id = self.execute_scalar(
                "INSERT INTO recipes (name, servings, servings_amt, servings_units) VALUES (%s,%s, %s, %s) RETURNING id;", 
                (name,servings, servings_amt, servings_units)
                )
        except psql_errors.UniqueViolation:
            self._logger.error(f"A recipe with name {name} already exists in db; nothing will be added")
            raise

        # then insert into ingreidents table
        ingredient_query = """
            INSERT INTO ingredients (recipe_id, ingredient_id, ingredient_amt, ingredient_units)
            SELECT %s, (SELECT id FROM pantry_items WHERE LOWER(name) = LOWER(s.ingr_name)), s.ingredient_amt, s.ingredient_units
            FROM staging AS s
            RETURNING *;
        """
        rows_added = self.execute_query(ingredient_query, (recipe_id,))
        self._logger.info(f"Added {rows_added} to ingredients table and recipe {name} to recipe table")
        
        # TODO drop staging? or let csv_to_staging handle that?
        return len(rows_added)
    
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
        
        meal_col_defs = [('date','date'), ('recipe_name','text'), ('servings','real')]
        rows_staged = self.csv_to_staging(csv_path=path_to_meals_csv, csv_columns=meal_col_defs)

        if rows_staged == 0:
            self._logger.info(f"No meals loaded from source file {path_to_meals_csv} to staging table, will not be added to db")
            return 0
        
        # Meals can only be added if all recipes are already in the db.
        # Check first, error with a list of missing recipes:
        check_rec = """
            SELECT s.recipe_name
            FROM staging AS s
            LEFT JOIN recipes r ON
                LOWER(r.name) = LOWER(s.recipe_name)
            WHERE r.id IS NULL;
        """
        recipe_missing = self.execute_query(check_rec)
        if len(recipe_missing) > 0:
            msg = f"Cannot load meals from {path_to_meals_csv}. Recipes missing from db: {list(zip(*recipe_missing))}"
            self._logger.error(msg)
            raise ValueError(msg)
        
        add_query = """
            INSERT INTO meals (date, recipe_id, recipe_servings)
            SELECT s.date, (SELECT id FROM recipes WHERE LOWER(name) = LOWER(s.recipe_name)), s.servings
            FROM staging AS s
            RETURNING *;
        """
        rows_added = self.execute_query(add_query)
        self._logger.info(f"Added {rows_added} to meals table")
        
        # TODO drop staging? or let csv_to_staging handle that?
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
        
        recipe_tuple = self.execute_query("SELECT id, servings, servings_amt, servings_units FROM recipes WHERE name=%s;", (recipe_name,))
        if len(recipe_tuple)==0:
            self._logger.error(f"Recipe {recipe_name} does not exist")
            raise ValueError(f"Recipe {recipe_name} does not exist")
        
        # I eventually abandoned this approach but saving the COALESE for future reference:
        # query=f"""
        #     WITH joined AS (
        #         SELECT *,
        #             COALESCE(u.factor, CASE WHEN p.units=i.ingredient_units THEN 1 ELSE NULL END) AS factor
        #         FROM pantry_items AS p
        #         LEFT JOIN ingredients i ON
        #             i.ingredient_id = p.id
        #         LEFT JOIN unit_conversions u ON
        #             u.unit_from = p.units  AND
        #             u.unit_to = i.ingredient_units
        #         WHERE i.recipe_id=%s
        #     ),
        #     SELECT joined.name, 
        #         {join_statements}
        #     FROM joined;
        #     """

        # For query building: The aliaising of the columns in the SELECT statement is just for display,
        # doesn't impact SQL execution:
        # SELECT p.*, 
        #        pu.unit AS p_unit, 
        #        pu.factor AS bottom_factor, 
        #        i.*, 
        #        iu.unit AS iu_unit, 
        #        iu.factor AS top_factor 
        # FROM pantry_items AS p 
        # INNER JOIN unit_conversions AS pu ON 
        #     pu.unit=p.units 
        # INNER JOIN ingredients AS i ON 
        #     i.ingredient_id=p.id 
        # INNER JOIN unit_conversions AS iu ON 
        #     iu.unit=i.ingredient_units 
        # WHERE i.recipe_id=1;

        ingr_cols = [f.name for f in fields(PantryItem) if f.name not in ["props"]] + [f.name for f in fields(FoodProps)]
        select_statements = ", ".join(f'SUM(i.ingredient_amt * (p.{c} / p.unitary_amt) * (iu.factor / pu.factor))  AS total_{c}' for c in ingr_cols if c not in {'name','unitary_amt','units','white_flour','animal'})

        query=f"""
            SELECT {select_statements},
                SUM(p.white_flour::int) AS white_flour,
                SUM(p.animal::int) AS animal,
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

        totals = self.execute_query(query,(recipe_tuple[0][0],))

        # Check that all units matched for conversions - otherwise the return from COUNT won't match
        # the number of ingredients in the recipe: (note this should be checked on recipe load regardless)
        check_query=f"""
            SELECT COUNT(*)
            FROM pantry_items AS p
            INNER JOIN ingredients i ON
                i.ingredient_id=p.id
            WHERE i.recipe_id=%s;
        """
        correct_rows = self.execute_scalar(check_query,(recipe_tuple[0][0],))

        if correct_rows != totals[0][-1]:
            msg = "Unit conversions failed in recipe totaling - some rows were dropped"
            self._logger.error(msg)
            raise ValueError(msg)

        ingr_props = FoodProps(cal=totals[0][0],
                      fat_grams=totals[0][1],
                      protein_grams=totals[0][2],
                      fiber_grams=totals[0][3],
                      sugar_grams= totals[0][4],
                      carb_grams= totals[0][5],
                      white_flour= bool(totals[0][6]),
                      animal= bool(totals[0][7])
                      )

        return Recipe(name=recipe_name, 
                      servings = recipe_tuple[0][1],
                      servings_amt=recipe_tuple[0][2],
                      servings_units=recipe_tuple[0][3],
                      props = ingr_props
                      )
    
    def get_recipes_in_dates(self, date_range: List[date]) -> List[Recipe]:
        # TODO do I want this to be totals or recipes? I think Recipes
        # REMEMBER: Recipe totals are per recipe, not per serving - if a recipe makes 2 servings,
        # get_recipe_totals will return totals for 2 servings. If a meal is 1 serving - need to do some math
        # (Calc meal or within date totals - need to normalize recipe totals per serving! (And then multiply servings in meals))
        pass