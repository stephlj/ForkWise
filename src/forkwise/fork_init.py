# One-time initialization of ForkDB.
#
# Copyright (c) 2026 Stephanie Johnson

import sys, os
import logging
import yaml

from dbcommons.init_db import init_db

from forkwise.utils import DEFAULT_LOGGING_FORMAT, CONFIG_PATH, SCHEMA_PATH
from forkwise.fork_db import ForkDB

def fork_init(admin_pw: str, path_to_config: str=CONFIG_PATH)->None:
    init_db(pw=admin_pw,path_to_config=path_to_config, path_to_schema=SCHEMA_PATH)

    with open(path_to_config, "r") as config_file:
        config = yaml.safe_load(config_file)
        db_name = config["db"]["db_name"]
        admin = config["db"]["admin_name"]
    
    # Add conversions table as admin
    conn = ForkDB(user=admin, pw=admin_pw, db_name=db_name)
    conn.add_conversions(path_to_conversions_csv=os.path.join(os.getcwd(), "src", "forkwise", "conversions.csv"))

    conn.close()

if __name__ == "__main__":
    logger = logging.getLogger(__name__)

    if len(sys.argv) != 2:
        raise ValueError("fork_init takes only one arg: owner pw")
    
    logging.basicConfig(level="INFO", format=DEFAULT_LOGGING_FORMAT)
    
    fork_init(admin_pw=sys.argv[1])
    