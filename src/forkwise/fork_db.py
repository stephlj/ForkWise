"""
Class that connects to the database and manages interactions with it.

This is the database access layer; business logic should be elsewhere.

Copyright (c) 2026 Stephanie Johnson
"""

import logging

from dataclasses import fields
from psycopg import errors as psql_errors

from dbcommons.db_conn import DBConn
from forkwise.fork_dataclasses import Ingredient, Recipe, Component

class ForkDB(DBConn):
    def __init__(self, user: str, pw: str, db_name: str):
        # Use super() because I've now override base class init
        super().__init__(user=user, pw=pw, db_name=db_name)
        self._logger = logging.getLogger(__name__)

    def get_recipe_name(self, recipe_id: int) -> int | None:
        return self.execute_scalar("SELECT name FROM recipes WHERE id=%s;", (recipe_id,))
    
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

    def add_recipe_via_staging(self, path_to_recipe_csv: str, name: str, servings: int) -> int:
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
            if len(check_dups) > 1: # This should not be possible because of this here check!
                msg = f"Multiple recipe ids returned with these components; something has gone wrong with the db!"
                self._logger.error(msg)
                raise ValueError(msg)
            recipe_id, num_comps = zip(*check_dups)
            same_comps = sum([x==rows_staged for x in num_comps])
            if same_comps>0:
                recipe_name = self.get_recipe_name(recipe_id=recipe_id[0])
                msg = f"A recipe with components in csv {path_to_recipe_csv} already exists (name: {recipe_name}); nothing will be added"
                self._logger.error(msg)
                raise ValueError(msg)
        
        # Insert recipe name and servings into recipe table, unless a recipe by this name already exists:
        try:
            recipe_id = self.execute_scalar("INSERT INTO recipes (name, servings) VALUES (%s,%s) RETURNING id;", (name,servings))
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
