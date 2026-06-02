"""
Class that connects to the database and manages interactions with it.

This is the database access layer; business logic should be elsewhere.

Copyright (c) 2026 Stephanie Johnson
"""

import logging

from dataclasses import fields

from dbcommons.db_conn import DBConn
from forkwise.dataclasses import Ingredient, Recipe

class ForkDB(DBConn):
    # TODO defining logger format needs to go in main app entry point ...
    def __init__(self, user: str, pw: str, db_name: str):
        # Use super() because I've now override base class init
        super().__init__(user=user, pw=pw, db_name=db_name)
        self._logger = logging.getLogger(__name__)
    
    def add_ingredients_via_staging(self, path_to_ingr_csv: str) -> int:
        # Will skip any row for which (name, unitary_amount, units) are already in the db.
        # Returns number of rows added to Ingredients table.

        # TODO add some input handling for this csv in BLL
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
        
        join_statements = " AND ".join(f'LOWER(i.{a}) = LOWER(s.{a})' for a, _ in ingr_col_defs)
        ingr_query = f"""
            WITH joined AS (
                SELECT s.*
                FROM staging AS s
                LEFT JOIN ingredients i ON
                    {join_statements}
                    WHERE i.id IS NULL
                )
            INSERT INTO ingredients ({col_names})
            SELECT *
            FROM joined
            RETURNING *;
        """ 
        rows_added = self.execute_query(ingr_query)
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
           Units don't have to match ingredient table units (will be converted or error).
        name : str
            Recipe name.
        servings: int
            How many servings do the amounts in this recipe make in total.

        Returns
        -------
        1 for success, 0 for failure
        """
    
        # Servings and name are added separately! not in the csv. Don't include these in col def
        recipe_col_defs = [(f.name, f.metadata['sql_type']) for f in fields(Recipe) if f.name!='name' and f.name!='servings']

        rows_staged = self.csv_to_staging(csv_path=path_to_recipe_csv, csv_columns=recipe_col_defs)

        if rows_staged == 0:
            self._logger.info("No recipe loaded from source file to staging table, will not be added to db")
            return 0
        
        # A recipe can only be added if all ingredients are already in the db.
        # Check first, error with a list of missing ingredients: TODO or should I return this list?
        check_ingr = """
            SELECT * FROM (
                SELECT s.*
                FROM staging AS s
                LEFT JOIN ingredients i ON
                    LOWER(i.name) = LOWER(s.ingr_name)
                    WHERE i.id IS NULL
            );
        """
        ingr_missing = self.execute_query(check_ingr)

        if len(ingr_missing) > 0:
            missing_ingr_names = [a[0] for a in ingr_missing]
            msg = f"Cannot load recipe: {name}. Ingredients missing from db: {missing_ingr_names}"
            self._logger.error(msg)
            raise ValueError(msg)

        # Next: insert, including linking to ingredients table
        # TODO drop staging? or let csv_to_staging handle that?
        recipe_query = f"""..."""
        rows_added = self.execute_query(recipe_query)

        if len(rows_added) != 1:
            raise ValueError("something")
        return 1