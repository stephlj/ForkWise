"""
Constants and utilities used by multiple modules.

Copyright (c) 2026 Stephanie Johnson
"""

import os

DEFAULT_LOGGING_FORMAT = (
    "%(levelname)s %(asctime)-15s @ %(module)s.%(funcName)s.%(lineno)d - %(msg)s"
)

CONFIG_PATH = os.path.join(os.getcwd(),"src","forkwise","config.yml")
SCHEMA_PATH = os.path.join(os.getcwd(),"src","forkwise","schema.sql")

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