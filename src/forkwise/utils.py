"""
Constants and utilities used by multiple modules.

Copyright (c) 2026 Stephanie Johnson
"""

import logging
import os

DEFAULT_LOGGING_FORMAT = (
    "%(levelname)s %(asctime)-15s @ %(module)s.%(funcName)s.%(lineno)d - %(msg)s"
)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yml")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")

DASHBOARD_TITLE = "ForkWise Dashboard"
PROPS_DISPLAY_NAMES = {"cal" : "Calories",
                       "fiber_grams": "Fiber (g)",
                       "sugar_grams" : "Sugar (g)",
                       "protein_grams" : "Protein (g)",
                        "fat_grams" : "Fat (g)",
                        "carb_grams" : "Carbs (g)",
                        "animal" : "Animal sources",
                        "white_flour" : "White flour"
                    }

from dataclasses import fields

from forkwise.fork_dataclasses import Recipe, FoodProps

# Used when config.yml has no display.gram_nutrients
DEFAULT_GRAM_NUTRIENTS = ["protein_grams", "sugar_grams", "fiber_grams", "fat_grams"]


def parse_gram_nutrients(requested: list[str] | None) -> list[str]:
    """
    Check the gram_nutrients list from config.yml, keeping only names that are
    FoodProps fields measured in grams (names ending in "_grams"), without duplicates.
    Anything else is dropped with a logged warning. Returns the defaults if requested is None.
    """
    logger = logging.getLogger(__name__)
    if requested is None:
        return DEFAULT_GRAM_NUTRIENTS
    if not isinstance(requested, list):
        logger.warning(f"gram_nutrients in config should be a list; got {requested!r}. Using defaults.")
        return DEFAULT_GRAM_NUTRIENTS

    # The "_grams" suffix is a naming convention, not enforced by FoodProps. Simple and
    # good enough for now; storing units in each field's metadata would be sturdier.
    gram_fields = {f.name for f in fields(FoodProps) if f.name.endswith("_grams")}
    kept = []
    for name in requested:
        if name not in gram_fields:
            logger.warning(f"Ignoring {name!r} in gram_nutrients: not a gram-based FoodProps field.")
        elif name in kept:
            logger.warning(f"Ignoring duplicate {name!r} in gram_nutrients.")
        else:
            kept.append(name)
    return kept


# Legacy functions, can probably delete soon
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

    return FoodProps(cal=tots_per_serv.cal*servings_eaten,
                     fat_grams=tots_per_serv.fat_grams*servings_eaten,
                     protein_grams=tots_per_serv.protein_grams*servings_eaten,
                     fiber_grams=tots_per_serv.fiber_grams*servings_eaten,
                     sugar_grams=tots_per_serv.sugar_grams*servings_eaten,
                     carb_grams=tots_per_serv.carb_grams*servings_eaten,
                     white_flour=tots_per_serv.white_flour,
                     animal=tots_per_serv.animal)