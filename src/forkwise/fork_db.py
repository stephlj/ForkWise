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
        super().__init__(user=user, pw=pw, db_name=db_name)
        self._logger = logging.getLogger(__name__)