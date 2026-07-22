# Simple CLI to display information about a recipe logged in the db.
# 
# Copyright (c) 2026 Stephanie Johnson

import sys
import logging
import yaml

from dataclasses import fields

from forkwise.utils import DEFAULT_LOGGING_FORMAT, CONFIG_PATH
from forkwise.fork_db import ForkDB
from forkwise.fork_dataclasses import Recipe, FoodProps

def calc_totals_per_serving(recipe: Recipe)->FoodProps:
    """
    Given a Recipe, calculate totals per serving, returning as a FoodProps object.
    """

    return FoodProps(cal=recipe.props.cal/recipe.servings,
                     fat_grams=recipe.props.fat_grams/recipe.servings,
                     protein_grams=recipe.props.protein_grams/recipe.servings,
                     fiber_grams=recipe.props.fiber_grams/recipe.servings,
                     sugar_grams=recipe.props.sugar_grams/recipe.servings,
                     carb_grams=recipe.props.carb_grams/recipe.servings,
                     white_flour=recipe.props.white_flour,
                     animal=recipe.props.animal)

def display_recipe_info(recipe_name: str, username: str, pw: str, path_to_config: str=CONFIG_PATH):
    """
    Retrieve info on the recipe from the db, calculate info per serving, print info to command line.
    """

    with open(path_to_config, "r") as config_file:
        config = yaml.safe_load(config_file)
        db_name = config["db"]["db_name"]

    conn = ForkDB(user=username, pw=pw, db_name=db_name)
    recipe = conn.get_recipe_totals(recipe_name=recipe_name)
    conn.close()

    totals = calc_totals_per_serving(recipe=recipe)

    print(f"Nutritional values for recipe {recipe_name}, serving size {recipe.servings_amt} {recipe.servings_units}:")
    print(f"Calories per serving: {round(totals.cal,1)}")
    print(f"Grams of fat per serving: {round(totals.fat_grams,1)}")
    print(f"Grams of protein per serving: {round(totals.protein_grams,1)}")
    print(f"Grams of total carbs per serving: {round(totals.carb_grams,1)}, including {round(totals.fiber_grams,1)} of fiber and {round(totals.sugar_grams,1)} of sugar")

if __name__ == "__main__":
    logger = logging.getLogger(__name__)

    if len(sys.argv) != 4:
        raise ValueError("fork_init takes 3 args: (1) user name to connect to the db, (2) user pw, (3) recipe name to display")
    
    logging.basicConfig(level="INFO", format=DEFAULT_LOGGING_FORMAT)
    
    display_recipe_info(recipe_name=sys.argv[3], username=sys.argv[1], pw=sys.argv[2])