"""
Class that connects to the database and manages interactions with it.

This is the database access layer; business logic should be elsewhere.

Copyright (c) 2026 Stephanie Johnson
"""

import logging

from dbcommons.db_conn import DBConn
from forkwise.dataclasses import Ingredient

class ForkDB(DBConn):
    # TODO defining logger format needs to go in main app entry point ...
    def __init__(self, user: str, pw: str, db_name: str):
        # Use super() because I've now override base class init
        super().__init__(user=user, pw=pw, db_name=db_name)
        self._logger = logging.getLogger(__name__)
    
    def add_ingredients_from_csv(self, path_to_ingr_csv: str) -> None:
        # Don't need a staging table for this action
        # Will skip any row for which (name, unitary_amount, units) are already in the db.

        # TODO add some input handling for this csv in BLL
        ingr_col_defs = [(f.name, f.metadata['sql_type']) for f in fields(Ingredient)]

        # TODO how does import_file handle dups that aren't allowed in the db? Does this throw an error?
        # Should probably wrap in a try-except
        r = self._import_file(csv_columns=ingr_col_defs, dest_table="ingredients", csv_path=path_to_ingr_csv)

        if r==0:
            self._logger.info("Failed to import ingredients csv")
        
        # TODO without loading first into a staging table, can't get num rows added ... 
        # rows_added = self.execute_query(balances_query, (accnt_name,))
        # return len(rows_added)

    def add_recipe_from_staging(self) -> None:
        # This does go through a staging table first.
        pass