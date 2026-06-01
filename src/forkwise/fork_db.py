"""
Class that connects to the database and manages interactions with it.

This is the database access layer; business logic should be elsewhere.

Copyright (c) 2026 Stephanie Johnson
"""

import logging

from dataclasses import fields

from dbcommons.db_conn import DBConn
from forkwise.dataclasses import Ingredient

class ForkDB(DBConn):
    # TODO defining logger format needs to go in main app entry point ...
    def __init__(self, user: str, pw: str, db_name: str):
        # Use super() because I've now override base class init
        super().__init__(user=user, pw=pw, db_name=db_name)
        self._logger = logging.getLogger(__name__)
    
    def add_ingredients_from_csv(self, path_to_ingr_csv: str) -> int:
        # Will skip any row for which (name, unitary_amount, units) are already in the db.
        # Returns number of rows added to Ingredients table.

        # TODO add some input handling for this csv in BLL
        ingr_col_defs = [(f.name, f.metadata['sql_type']) for f in fields(Ingredient)]

        rows_staged = self.csv_to_staging(csv_path=path_to_ingr_csv, csv_columns=ingr_col_defs)

        if rows_staged == 0:
            self._logger.info("No ingredients loaded from source file to staging table; no ingredeints will be added to db")
            return 0
        
        col_names = ", ".join(f'{a}' for a, _ in ingr_col_defs)
        col_names_staging = ", ".join(f's.{a}' for a, _ in ingr_col_defs)
        
        # CHECK not sure this works
        # CHECk that this skips anything already in db (violation of unique constraint)
        ingr_query = "INSERT INTO ingredients (%s) " \
            "SELECT %s" \
            "FROM staging AS s " \
            "RETURNING *;"
        rows_added = self.execute_query(ingr_query, (col_names,col_names_staging))
        return len(rows_added)

    def add_recipe_from_staging(self) -> None:
        # This does go through a staging table first.
        pass