"""
Class that connects to the database and manages interactions with it.

This is the database access layer; business logic should be elsewhere.

Copyright (c) 2026 Stephanie Johnson
"""

import logging

from dataclasses import fields
from psycopg import errors as psql_errors
from typing import List

from dbcommons.db_conn import DBConn
from forkwise.fork_dataclasses import Ingredient, Recipe, Component

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
        # Will skip any row for which (name, unitary_amount, units) are already in the db.
        # Returns number of rows added to Ingredients table.

        ingr_col_defs = [(f.name, f.metadata['sql_type']) for f in fields(Ingredient)]

        rows_staged = self.csv_to_staging(csv_path=path_to_ingr_csv, csv_columns=ingr_col_defs)

        if rows_staged == 0:
            self._logger.info("No ingredients loaded from source file to staging table; no ingredeints will be added to db")
            return 0
        
        col_names = ", ".join(f'{a}' for a, _ in ingr_col_defs)
        
        # This will throw a UniqueViolation if any rows in staging are already in the db ingredients table
        # col_names_staging = ", ".join(f's.{a}' for a, _ in ingr_col_defs)
        # ingr_query = f"""
        #     INSERT INTO ingredients ({col_names})
        #     SELECT {col_names_staging}
        #     FROM staging AS s
        #     RETURNING *;
        # """   
        
        join_statements = " AND ".join(f'i.{a} = s.{a}' for a, _ in ingr_col_defs[1:])
        ingr_query = f"""
            WITH joined AS (
                SELECT s.*
                FROM staging AS s
                LEFT JOIN ingredients i ON
                    LOWER(i.name) = LOWER(s.name) AND
                    {join_statements}
                    WHERE i.id IS NULL
                )
            INSERT INTO ingredients ({col_names})
            SELECT *
            FROM joined
            RETURNING *;
        """ 
        rows_added = self.execute_query(ingr_query)
        self._logger.info(f"Added {rows_added} to ingredients table")
        return len(rows_added)
    
        # TODO drop staging? or let csv_to_staging handle that?

    def add_recipe_via_staging(self, 
                               path_to_recipe_csv: str, 
                               name: str, 
                               servings: int,
                               servings_amt: float,
                               servings_units: str) -> int:
        """
        Add recipe from csv via a staging table.

        Parameters
        ----------
        path_to_recipe_csv : str
           Path to a recipe: each row is an ingredient (name, amount, units).
           Name must already be an ingredient in the db.
           Units don't have to match ingredient table units (can be converted later).
        name : str
            Recipe name.
        servings: int
            How many servings do the amounts in this recipe make in total.
        servings_amt : float
            Amount corresponding to one serving (e.g. 1, if 1 c is a serving)
        servings_units : str
            Units per serving amount, eg c if a serving is 1 c

        Returns
        -------
        int, number of rows added to compontents table
        """
    
        component_col_defs = [(f.name, f.metadata['sql_type']) for f in fields(Component)]

        rows_staged = self.csv_to_staging(csv_path=path_to_recipe_csv, csv_columns=component_col_defs)

        if rows_staged == 0:
            self._logger.info("No recipe loaded from source file to staging table, will not be added to db")
            return 0
        
        # A recipe can only be added if all ingredients are already in the db.
        # Check first, error with a list of missing ingredients: TODO or should I return this list?
        check_ingr = """
            WITH joined AS (
                SELECT s.*
                FROM staging AS s
                LEFT JOIN ingredients i ON
                    LOWER(i.name) = LOWER(s.ingr_name)
                    WHERE i.id IS NULL
            )
            SELECT ingr_name FROM joined;
        """
        ingr_missing = self.execute_query(check_ingr)
        if len(ingr_missing) > 0:
            msg = f"Cannot load recipe: {name}. Ingredients missing from db: {list(zip(*ingr_missing))}"
            self._logger.error(msg)
            raise ValueError(msg)

        # We also don't allow duplicate recipes. A duplicate is same name, or same ingredients+amounts for a single recipe_id:
        # Check the latter condition first. Join ingredients onto staging to get ingredient id; then ask whether the components table has
        # the same combo of (ingredient id, ingredient amt, ingredient units) associated with a single recipe id already as what's in staging.
        join_statements = " AND ".join(f'c.{a} = j.{a}' for a, _ in component_col_defs[1:])
        # Equivalent to: LEFT JOIN ingredients i ON ... WHERE i.id IS NOT NULL
        check_dup_components = f"""
            WITH joined1 AS (
                SELECT s.*, i.id
                FROM staging AS s
                INNER JOIN ingredients i ON
                    LOWER(i.name) = LOWER(s.ingr_name)
            ),
            joined2 AS (
                SELECT j.*, c.recipe_id
                FROM joined1 AS j
                INNER JOIN components c ON
                    c.ingredient_id = j.id AND
                    {join_statements}
            )
            SELECT recipe_id, COUNT(*)
            FROM joined2
            GROUP BY recipe_id;
        """
        check_dups = self.execute_query(check_dup_components)
        if len(check_dups) > 0:
            recipe_id, num_comps = zip(*check_dups)
            same_comps = sum([x==rows_staged for x in num_comps])
            if same_comps>0:
                recipe_name = self.get_recipe_name(recipe_id=recipe_id[0])
                msg = f"A recipe with components in csv {path_to_recipe_csv} already exists (name: {recipe_name}); nothing will be added"
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

        # then insert into components table
        component_query = """
            INSERT INTO components (recipe_id, ingredient_id, ingredient_amt, ingredient_units)
            SELECT %s, (SELECT id FROM ingredients WHERE LOWER(name) = LOWER(s.ingr_name)), s.ingredient_amt, s.ingredient_units
            FROM staging AS s
            RETURNING *;
        """
        rows_added = self.execute_query(component_query, (recipe_id,))
        self._logger.info(f"Added {rows_added} to components table and recipe {name} to recipe table")
        
        # TODO drop staging? or let csv_to_staging handle that?
        return len(rows_added)
    
    def get_recipe_totals(self, recipe_name: str) -> Recipe:
        """
        Calculate nutritional totals for a recipe.

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
        #             COALESCE(u.factor, CASE WHEN i.units=c.ingredient_units THEN 1 ELSE NULL END) AS factor
        #         FROM ingredients AS i
        #         LEFT JOIN components c ON
        #             c.ingredient_id = i.id
        #         LEFT JOIN unit_conversions u ON
        #             u.unit_from = i.units  AND
        #             u.unit_to = c.ingredient_units
        #         WHERE c.recipe_id=%s
        #     ),
        #     SELECT joined.name, 
        #         {join_statements}
        #     FROM joined;
        #     """

        # For query building: The aliaising of the columns in the SELECT statement is just for display,
        # doesn't impact SQL execution:
        # SELECT i.*, 
        #        iu.unit AS i_unit, 
        #        iu.factor AS bottom_factor, 
        #        c.*, 
        #        cu.unit AS cu_unit, 
        #        cu.factor AS top_factor 
        # FROM ingredients AS i 
        # INNER JOIN unit_conversions AS iu ON 
        #     iu.unit=i.units 
        # INNER JOIN components AS c ON 
        #     c.ingredient_id=i.id 
        # INNER JOIN unit_conversions AS cu ON 
        #     cu.unit=c.ingredient_units 
        # WHERE c.recipe_id=1;

        ingr_cols = [f.name for f in fields(Ingredient)]
        select_statements = ", ".join(f'SUM(c.ingredient_amt * (i.{i} / i.unitary_amount) * (cu.factor / iu.factor))  AS total_{i}' for i in ingr_cols[3:-1])

        query=f"""
            SELECT {select_statements},
                SUM(i.animal::int) AS animal,
                COUNT(*)
            FROM ingredients AS i
            INNER JOIN unit_conversions AS iu ON 
                LOWER(iu.unit)=LOWER(i.units) 
            INNER JOIN components AS c ON 
                c.ingredient_id=i.id 
            INNER JOIN unit_conversions AS cu ON 
                LOWER(cu.unit)=LOWER(c.ingredient_units) AND
                cu.category=iu.category
            WHERE c.recipe_id=%s;
            """

        totals = self.execute_query(query,(recipe_tuple[0][0],))

        # Check that all units matched for conversions - otherwise the return from COUNT won't match
        # the number of ingredients in the recipe:
        check_query=f"""
            SELECT COUNT(*)
            FROM ingredients AS i
            INNER JOIN components c ON
                c.ingredient_id=i.id
            WHERE c.recipe_id=%s;
        """
        correct_rows = self.execute_scalar(check_query,(recipe_tuple[0][0],))

        if correct_rows != totals[0][7]:
            msg = "Unit conversions failed in recipe totaling - some rows were dropped"
            self._logger.error(msg)
            raise ValueError(msg)

        return Recipe(name=recipe_name, 
                      cal=totals[0][0],
                      fat_grams=totals[0][1],
                      protein_grams=totals[0][2],
                      fiber_grams=totals[0][3],
                      sugar_grams= totals[0][4],
                      carb_grams= totals[0][5],
                      animal= bool(totals[0][6]),
                      servings = recipe_tuple[0][1],
                      servings_amt=recipe_tuple[0][2],
                      servings_units=recipe_tuple[0][3]
                      )