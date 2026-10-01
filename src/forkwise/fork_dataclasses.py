"""
These dataclasses hold the structured data from the db in the python layer. 
They're objects that are roughly equivalent to how the information is stored in the db.
They're meant to mesh with the utilities in dbcommons for loading data into the db.

Copyright (c) 2026 Stephanie Johnson
"""

from dbcommons.dataclass_utils import flat_col_defs

from dataclasses import dataclass, field
from typing import List
from datetime import date

def fix_units(raw_units: str) -> str:
    raw_units=raw_units.strip()
    if raw_units.lower()=='lb':
        return 'lbs'
    elif raw_units.lower()=='cup':
        return 'c'
    else:
        return raw_units

@dataclass
class FoodProps:
    cal: float = field(metadata={'sql_type':'real', 'csv_parser': lambda s: float(s)})
    fiber_grams: float = field(metadata={'sql_type':'real', 'csv_parser': lambda s: float(s)})
    sugar_grams: float = field(metadata={'sql_type':'real', 'csv_parser': lambda s: float(s)})
    protein_grams: float = field(metadata={'sql_type':'real', 'csv_parser': lambda s: float(s)})
    fat_grams: float = field(metadata={'sql_type':'real', 'csv_parser': lambda s: float(s)})
    carb_grams: float = field(metadata={'sql_type':'real', 'csv_parser': lambda s: float(s)})
    # int() first: bool('0') is truthy, so bool(raw_string) is always True
    animal: bool = field(metadata={'sql_type':'boolean', 'csv_parser': lambda s: bool(int(s))})
    white_flour: bool = field(metadata={'sql_type':'boolean', 'csv_parser': lambda s: bool(int(s))})


@dataclass
class PantryItem:
    name: str = field(metadata={'sql_type':'text', 'csv_parser': lambda s: s})
    unitary_amt: float = field(metadata={'sql_type':'real', 'csv_parser': lambda s: float(s)})
    units: str = field(metadata={'sql_type':'text', 'csv_parser': fix_units})
    props: FoodProps


@dataclass
class Ingredient:
    ingr_name: str = field(metadata={'sql_type':'text', 'csv_parser': lambda s: s})
    ingredient_amt: float = field(metadata={'sql_type':'real', 'csv_parser': lambda s: float(s)})
    ingredient_units: str = field(metadata={'sql_type':'text', 'csv_parser': fix_units})


@dataclass
class Recipe: 
    # In the db, a recipe is associated with a list of ingredients (pantry items in particular amounts)
    # But in the python layer, a Recipe is a set of FoodProps that those ingredients result in
    name: str = field(metadata={'sql_type':'text', 'csv_parser': lambda s: s})
    servings: float = field(metadata={'sql_type':'real', 'csv_parser': lambda s: float(s)})
    servings_amt: float = field(metadata={'sql_type':'real', 'csv_parser': lambda s: float(s)})
    servings_units: str = field(metadata={'sql_type':'text', 'csv_parser': fix_units})
    props: FoodProps


@dataclass
class Meal:
    recipes: List[Recipe]
    servings_eaten: List[float]
    date_eaten: date


# Col defs for interaction with the db layer - the data representation in the python and sql layers are not identical.
FOODPROPS_COL_DEFS = flat_col_defs(FoodProps)
FOODPROPS_COL_NAMES = [n for n, _ in FOODPROPS_COL_DEFS]
PANTRY_COL_DEFS = flat_col_defs(PantryItem)
PANTRY_COL_NAMES = [n for n, _ in PANTRY_COL_DEFS]
INGR_COL_DEFS = flat_col_defs(Ingredient)
MEAL_COL_DEFS = [('date','date'), ('recipe_name','text'), ('servings','real')]  # no dataclass maps to the meals csv
    