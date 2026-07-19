# Add a new user to the db.
#
# Copyright (c) 2026 Stephanie Johnson

import sys
import logging

from dbcommons.add_user import add_user

from forkwise.utils import DEFAULT_LOGGING_FORMAT, CONFIG_PATH

def add_fork_user(new_user_name: str, new_user_pw: str, admin_pw: str, path_to_config: str=CONFIG_PATH)->None:
    add_user(name=new_user_name, pw=new_user_pw, admin_pw=admin_pw, path_to_config=path_to_config)

if __name__ == "__main__":
    logger = logging.getLogger(__name__)

    if len(sys.argv) != 3:
        raise ValueError("add_fork_user takes 3 args: new user name, new user pw, admin pw")
    
    logging.basicConfig(level="INFO", format=DEFAULT_LOGGING_FORMAT)
    
    add_fork_user(new_user_name=sys.argv[1], new_user_pw=sys.argv[2], admin_pw=sys.argv[3])
    