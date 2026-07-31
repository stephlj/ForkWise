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

def calc_totals_eaten(tots_per_serv: FoodProps, servings_eaten: float)->FoodProps:
    """
    Given a FoodProps object (output of calc_totals_per_serving), and a number of servings_eaten,
    calculate totals eaten, returning as a FoodProps object.
    """

    return FoodProps(cal=tots_per_serv.cal/servings_eaten,
                     fat_grams=tots_per_serv.fat_grams/servings_eaten,
                     protein_grams=tots_per_serv.protein_grams/servings_eaten,
                     fiber_grams=tots_per_serv.fiber_grams/servings_eaten,
                     sugar_grams=tots_per_serv.sugar_grams/servings_eaten,
                     carb_grams=tots_per_serv.carb_grams/servings_eaten,
                     white_flour=tots_per_serv.white_flour,
                     animal=tots_per_serv.animal)