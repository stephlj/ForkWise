"""
These dataclasses hold the structured data from the db in the python layer. 
They're objects that are roughly equivalent to how the information is stored in the db.

Note on accessing type information:
col_defs_python = [(f.name, f.type.__name__) for f in fields(Transaction)]
gives [('posted_date', 'date'), ('amount', 'Decimal'), ('description', 'str')]
col_defs_sql = [(f.name, f.metadata['sql_type']) for f in fields(Transaction)]
gives [('posted_date', 'date'), ('amount', 'numeric'), ('description', 'text')]

Copyright (c) 2026 Stephanie Johnson
"""

from dataclasses import dataclass, field
from typing import List
from datetime import date

@dataclass
class FoodProps:
    cal: float = field(metadata={'sql_type':'real'})
    fat_grams: float = field(metadata={'sql_type':'real'})
    protein_grams: float = field(metadata={'sql_type':'real'})
    fiber_grams: float = field(metadata={'sql_type':'real'})
    sugar_grams: float = field(metadata={'sql_type':'real'})
    carb_grams: float = field(metadata={'sql_type':'real'})
    white_flour: bool = field(metadata={'sql_type':'boolean'})
    animal: bool = field(metadata={'sql_type':'boolean'})

    def __iter__(self):
        yield self.cal
        yield self.fat_grams
        yield self.protein_grams
        yield self.fiber_grams
        yield self.sugar_grams
        yield self.carb_grams
        yield self.white_flour
        yield self.animal


@dataclass
class PantryItem:
    name: str = field(metadata={'sql_type':'text'})
    unitary_amt: float = field(metadata={'sql_type':'real'})
    units: str = field(metadata={'sql_type':'text'})
    props: FoodProps

    def __iter__(self):
        yield self.name
        yield self.unitary_amt
        yield self.units
        yield self.props

@dataclass
class Ingredient:
    ingr_name: str = field(metadata={'sql_type':'text'})
    ingredient_amt: float = field(metadata={'sql_type':'real'})
    ingredient_units: str = field(metadata={'sql_type':'text'})

    def __iter__(self):
        yield self.ingr_name
        yield self.ingredient_amt
        yield self.ingredient_units

@dataclass
class Recipe: 
    # In the db, a recipe is associated with a list of ingredients (pantry items in particular amounts)
    # But in the python layer, a Recipe is a set of FoodProps that those ingredients result in
    name: str = field(metadata={'sql_type':'text'})
    servings: float = field(metadata={'sql_type':'real'})
    servings_amt: float = field(metadata={'sql_type':'real'})
    servings_units: str = field(metadata={'sql_type':'text'})
    props: FoodProps

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

    