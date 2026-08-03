# add_ingredients.py
#
# CLI to add ingredients to db via csv.
#
# Copyright (c) 2026 Stephanie Johnson

import sys
import logging
import yaml

from forkwise.utils import DEFAULT_LOGGING_FORMAT, CONFIG_PATH
from forkwise.fork_db import ForkDB

if __name__ == "__main__":
    logger = logging.getLogger(__name__)

    # TODO add csv format checking here

    if len(sys.argv) != 4:
        raise ValueError("add_ingredients.py takes 3 args: (1) db username, (2) user db pw, (3) path to csv of ingredients")
    
    logging.basicConfig(level="INFO", format=DEFAULT_LOGGING_FORMAT)

    with open(CONFIG_PATH, 'r') as config_file:
        config = yaml.safe_load(config_file)
        db_name = config["db"]["db_name"]

    db_conn = ForkDB(user=sys.argv[1], pw=sys.argv[2], db_name=db_name)

    num_rows_added = db_conn.add_ingredients_via_staging(path_to_ingr_csv=sys.argv[3])

    db_conn.close()

    logger.info(f"Added {num_rows_added} rows to pantry items table")
    