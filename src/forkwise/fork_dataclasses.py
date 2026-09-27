"""
These dataclasses hold the structured data from the db in the python layer. 
They're objects that are roughly equivalent to how the information is stored in the db.

Note on accessing type information:

col_defs_python = [(f.name, f.type.__name__) for f in fields(Transaction)]
gives [('posted_date', 'date'), ('amount', 'Decimal'), ('description', 'str')]

col_defs_sql = [(f.name, f.metadata['sql_type']) for f in fields(Transaction)]
gives [('posted_date', 'date'), ('amount', 'numeric'), ('description', 'text')]

Each field that can be loaded from a csv carries a 'csv_parser' in its metadata:
a callable turning one csv string cell into the field's value. DataLoader's
csv_to_dataclass function uses this to build objects generically, driving the
column<->field correspondence off the field names so it can't be mistyped.

WARNING: do NOT add `from __future__ import annotations` to this module. It would
turn f.type into a string, breaking the is_dataclass(f.type) check that
csv_to_dataclass relies on to recurse into nested dataclass fields (e.g. props).

Copyright (c) 2026 Stephanie Johnson
"""

from dataclasses import dataclass, field, fields, is_dataclass
from typing import List, Tuple
from datetime import date

def fix_units(raw_units: str) -> str:
    raw_units=raw_units.strip()
    if raw_units.lower()=='lb':
        return 'lbs'
    elif raw_units.lower()=='cup':
        return 'c'
    else:
        return raw_units
    
def flat_col_defs(cls: type) -> List[Tuple[str, str]]:
    """
    (name, sql_type) for each column `cls` maps to in the db, flattening a nested
    dataclass field (e.g. PantryItem.props -> the FoodProps columns) into the
    parent. This is what lets us avoid special-casing props by hand.
    """
    defs = []
    for f in fields(cls):
        if is_dataclass(f.type):
            defs += [(nf.name, nf.metadata['sql_type']) for nf in fields(f.type)]
        else:
            defs.append((f.name, f.metadata['sql_type']))
    return defs

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

    def __iter__(self):
        yield self.cal
        yield self.fiber_grams
        yield self.sugar_grams
        yield self.protein_grams
        yield self.fat_grams
        yield self.carb_grams
        yield self.animal
        yield self.white_flour


@dataclass
class PantryItem:
    name: str = field(metadata={'sql_type':'text', 'csv_parser': lambda s: s})
    unitary_amt: float = field(metadata={'sql_type':'real', 'csv_parser': lambda s: float(s)})
    units: str = field(metadata={'sql_type':'text', 'csv_parser': fix_units})
    props: FoodProps  # special-cased in csv_to_dataclass (nested dataclass, no csv_parser)

    def __iter__(self):
        yield self.name
        yield self.unitary_amt
        yield self.units
        yield self.props

@dataclass
class Ingredient:
    ingr_name: str = field(metadata={'sql_type':'text', 'csv_parser': lambda s: s})
    ingredient_amt: float = field(metadata={'sql_type':'real', 'csv_parser': lambda s: float(s)})
    ingredient_units: str = field(metadata={'sql_type':'text', 'csv_parser': fix_units})

    def __iter__(self):
        yield self.ingr_name
        yield self.ingredient_amt
        yield self.ingredient_units

@dataclass
class Recipe: 
    # In the db, a recipe is associated with a list of ingredients (pantry items in particular amounts)
    # But in the python layer, a Recipe is a set of FoodProps that those ingredients result in
    name: str = field(metadata={'sql_type':'text', 'csv_parser': lambda s: s})
    servings: float = field(metadata={'sql_type':'real', 'csv_parser': lambda s: float(s)})
    servings_amt: float = field(metadata={'sql_type':'real', 'csv_parser': lambda s: float(s)})
    servings_units: str = field(metadata={'sql_type':'text', 'csv_parser': fix_units})
    props: FoodProps  # special-cased in csv_to_dataclass (nested dataclass, no csv_parser)

    def __iter__(self):
        yield self.name
        yield self.servings
        yield self.servings_amt
        yield self.servings_units
        yield self.props

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
    