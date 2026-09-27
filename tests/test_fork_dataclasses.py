import unittest

from forkwise.fork_dataclasses import fix_units, flat_col_defs, FoodProps, PantryItem, Ingredient

class TestForkDataclasses(unittest.TestCase):

    def test_fix_units(self):
        self.assertEqual(fix_units('lb'), 'lbs')
        self.assertEqual(fix_units('lb '), 'lbs')
        self.assertEqual(fix_units('Lb '), 'lbs')
        self.assertEqual(fix_units('LB'), 'lbs')
        self.assertEqual(fix_units('cup'), 'c')
        self.assertEqual(fix_units(' cup'), 'c')
        self.assertEqual(fix_units('Cup'), 'c')
        self.assertEqual(fix_units('unit'), 'unit')
        self.assertEqual(fix_units(' unit '), 'unit')
        self.assertEqual(fix_units(' not a real unit but'), 'not a real unit but')

    def test_flat_col_defs_flattens_nested_dataclass(self):
        # PantryItem.props is a nested FoodProps: flat_col_defs should splice the
        # FoodProps columns into the parent, in order, with no 'props' column.
        # This also guards the is_dataclass(f.type) dependency: adding
        # `from __future__ import annotations` to fork_dataclasses would stringize
        # f.type, props would stop flattening, and this test would fail.
        defs = flat_col_defs(PantryItem)

        self.assertEqual(defs, [
            ('name', 'text'),
            ('unitary_amt', 'real'),
            ('units', 'text'),
            ('cal', 'real'),
            ('fiber_grams', 'real'),
            ('sugar_grams', 'real'),
            ('protein_grams', 'real'),
            ('fat_grams', 'real'),
            ('carb_grams', 'real'),
            ('animal', 'boolean'),
            ('white_flour', 'boolean'),
        ])
        self.assertNotIn('props', [name for name, _ in defs])

    def test_flat_col_defs_no_nesting(self):
        # A dataclass with no nested dataclass field is just its own (name, sql_type) pairs.
        self.assertEqual(flat_col_defs(Ingredient), [
            ('ingr_name', 'text'),
            ('ingredient_amt', 'real'),
            ('ingredient_units', 'text'),
        ])
        self.assertEqual(flat_col_defs(FoodProps), [
            ('cal', 'real'),
            ('fiber_grams', 'real'),
            ('sugar_grams', 'real'),
            ('protein_grams', 'real'),
            ('fat_grams', 'real'),
            ('carb_grams', 'real'),
            ('animal', 'boolean'),
            ('white_flour', 'boolean'),
        ])
