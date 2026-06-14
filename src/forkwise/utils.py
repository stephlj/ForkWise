"""
Constants and utilities used by multiple modules.

Copyright (c) 2026 Stephanie Johnson
"""

import os

DEFAULT_LOGGING_FORMAT = (
    "%(levelname)s %(asctime)-15s @ %(module)s.%(funcName)s.%(lineno)d - %(msg)s"
)

CONFIG_PATH = os.path.join(os.getcwd(),"src","forkwise","config.yml")