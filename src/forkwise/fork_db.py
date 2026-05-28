"""
Class that connects to the database and manages interactions with it.

This is the database access layer; business logic should be elsewhere.

Copyright (c) 2026 Stephanie Johnson
"""

import logging

from dbcommons.db_conn import DBConn

class ForkDB(DBConn):
    # TODO defining logger format needs to go in main app entry point ...
    def __init__(self, user: str, pw: str, db_name: str):
        # Use super() because I've now override base class init
        super().__init__(user=user, pw=pw, db_name=db_name)
        self._logger = logging.getLogger(__name__)
    
    def add_ingredients_from_csv(self, path_to_ingr_csv: str) -> None:
        # Don't need a staging table for this action
        # Will skip any row for which (name, unitary_amount, units) are already in the db.

        # Would be better to move this to the BLL with some input handling, but since this is just for
        # me and I have control over all the inputs, not bothering for now:
        # TODO get this from schema instead of hard-coding, or create a dataclass like in fintrackr
        ingr_col_defs = [("name", "text"),
                         ("unitary_amount", "real"),
                         ("units", "text"),
                         ("cal", "real"),
                         ("fat_grams", "real"),
                         ("protein_grams", "real"),
                         ("protein_grams", "real"),
                         ("fiber_grams", "real"),
                         ("sugar_grams", "real"),
                         ("carb_grams", "real"),
                         ("animal", "boolean")
                         ]
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