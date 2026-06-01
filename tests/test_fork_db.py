# Copyright (c) 2026 Stephanie Johnson

import unittest
import os

import dbcommons.testing_utils as utils
from forkwise.fork_db import ForkDB

# TODO might be better to locate these by where the file is? Does this work with CI?
TEST_CONFIG_PATH = os.path.join(os.getcwd(),"tests","fixtures","test_config.yml")
TEST_DATA_PATH = os.path.join(os.getcwd(),"tests","fixtures")
SCHEMA_PATH = os.path.join(os.getcwd(), "src", "forkwise", "schema.sql")

class TestDBConn(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.params = utils.config_params(config_path=TEST_CONFIG_PATH)
        utils.set_up_test_DB(params=cls.params, path_to_schema=SCHEMA_PATH)
        cls.conn = ForkDB(user=cls.params["user"], pw=cls.params["user_pw"], db_name=cls.params["test_db_name"])

    @classmethod
    def tearDownClass(cls):
        utils.tear_down_test_DB(db_conn=cls.conn, params=cls.params)
    
    def test_add_ingredients_from_csv(self):
        path_to_ingr_csv = os.path.join(TEST_DATA_PATH,"test_ingredients.csv")

        num_rows_added = self.conn.add_ingredients_from_csv(path_to_ingr_csv=path_to_ingr_csv)
        
        # TODO use pandas instead of hard-coding number of lines
        # Check for uploading partial duplicates
        self.assertEqual(num_rows_added, 11, "Incorrect number of rows added to ingredients table")