# add_recipe.py
#
# CLI to add a recipe to db via csv.
#
# Copyright (c) 2026 Stephanie Johnson

import sys
import logging
import yaml

from forkwise.utils import DEFAULT_LOGGING_FORMAT, CONFIG_PATH
from forkwise.fork_db import ForkDB

if __name__ == "__main__":
    logger = logging.getLogger(__name__)

    if len(sys.argv) != 8:
        raise ValueError("add_recipe.py takes 5 args: (1) db username, (2) user db pw, (3) path to csv of ingredients, (4) recipe name, (5) number of servings (6) amount per serving (7) units of amount per serving")
    
    logging.basicConfig(level="INFO", format=DEFAULT_LOGGING_FORMAT)
    
    # TODO add csv format checking here, and input handling for things like servings should be int

    with open(CONFIG_PATH, 'r') as config_file:
        config = yaml.safe_load(config_file)
        db_name = config["db"]["db_name"]

    db_conn = ForkDB(user=sys.argv[1], pw=sys.argv[2], db_name=db_name)

    _ = db_conn.add_recipe_via_staging(path_to_recipe_csv=sys.argv[3], name=sys.argv[4], servings=sys.argv[5], servings_amt=sys.argv[6], servings_units=sys.argv[7])

    db_conn.close()
    