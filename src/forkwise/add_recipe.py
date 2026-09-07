# add_recipe.py
#
# CLI to add a recipe to db via csv.
#
# Copyright (c) 2026 Stephanie Johnson

import sys, os
import logging
import yaml
import csv

from typing import List

from forkwise.utils import DEFAULT_LOGGING_FORMAT, CONFIG_PATH
from forkwise.fork_dataclasses import Ingredient
from forkwise.data_loader import DataLoader

def fix_units(raw_units: str) -> str:
    # TODO see README for unit checking I need to do here
    pass

def csv_to_recipe_ingr(path_to_recipe_csv: str)->List[Ingredient]:
    """
    In the db, a recipe is loaded as a list of Ingredients,
    plus servings amt, servings size, servings units, and
    a name for the recipe.

    When loaded from a csv, the csv contains only columns for
    ingredient name, amount, units.

    This function loads a recipe csv and returns a list of Ingredients.

    Parameters
    ----------
    path_to_recipe_csv : str
        Path to a csv with 3 columns: ingredient name, ingredient amount, ingredient units.

    Returns
    -------
    List[Ingredient]
    """

    # Basic input checking
    if not os.path.isfile(path_to_recipe_csv):
        msg = f"{path_to_recipe_csv} not a path to a file that exists"
        logger.error(msg)
        raise ValueError(msg)
        
    if not os.path.splitext(path_to_recipe_csv)[1] == ".csv":
        msg = f"{path_to_recipe_csv} must be a csv file"
        logger.error(msg)
        raise ValueError(msg)

    # TODO overhaul recipe input? Or not bother if I'm moving away from csvs?
    # The way I've actually been logging recipes is as one big csv, not one per recipe

    with open(path_to_recipe_csv, mode='r') as f:
        reader = csv.DictReader(f)
        # TODO check how it handles type mismatchces
        ingrs = [Ingredient(ingr_name=r["ingr_name"], ingredient_amt=int(r["ingredient_amt"]), ingredient_units=fix_units(r["ingredient_units"])) for r in reader]

    return ingrs


if __name__ == "__main__":
    logger = logging.getLogger(__name__)

    if len(sys.argv) != 8:
        raise ValueError("add_recipe.py takes 7 args: (1) db username, (2) user db pw, (3) path to csv of ingredients, (4) recipe name, (5) number of servings (6) amount per serving (7) units of amount per serving")
    
    logging.basicConfig(level="INFO", format=DEFAULT_LOGGING_FORMAT)
    
    # TODO add csv format checking here, and input handling for things like servings should be int

    with open(CONFIG_PATH, 'r') as config_file:
        config = yaml.safe_load(config_file)
        db_name = config["db"]["db_name"]

    ingrs = csv_to_recipe_ingr(path_to_recipe_csv=sys.argv[3])

    with DataLoader(user=sys.argv[1], pw=sys.argv[2], db_name=db_name) as dl:
        _ = dl.add_recipe_via_staging(ingredients=ingrs, name=sys.argv[4], servings=sys.argv[5], servings_amt=sys.argv[6], servings_units=sys.argv[7])
    