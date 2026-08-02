import unittest

from datetime import date

from forkwise.display_meal_totals import PropsPerDay, calc_daily_totals, display_meals_info, display_meal_breakdown
from forkwise.fork_dataclasses import Meal, Recipe, FoodProps

class TestUtils(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.meal_list = [Meal(recipes=[Recipe(name='toast', 
                                            servings=1.0, 
                                            servings_amt=1.0, 
                                            servings_units='unit', 
                                            props=FoodProps(cal=225.0, 
                                                            fat_grams=1.0, 
                                                            protein_grams=1.0, 
                                                            fiber_grams=5.0, 
                                                            sugar_grams=9.25, 
                                                            carb_grams=28.0, 
                                                            white_flour=True, 
                                                            animal=True)
                                                ), 
                                        Recipe(name='soy cocoa', 
                                            servings=1.0, 
                                            servings_amt=1.0, 
                                            servings_units='c', 
                                            props=FoodProps(cal=170.0, 
                                                            fat_grams=10.5, 
                                                            protein_grams=1.25, 
                                                            fiber_grams=14.0, 
                                                            sugar_grams=8.375, 
                                                            carb_grams=16.25, 
                                                            white_flour=False, 
                                                            animal=False
                                                            )
                                                )
                                            ], 
                                servings_eaten=[2.0, 1.25], 
                                date_eaten=date(2026, 6, 2)
                                ), 
                        Meal(recipes=[Recipe(name='toast', 
                                            servings=1.0, 
                                            servings_amt=1.0, 
                                            servings_units='unit', 
                                            props=FoodProps(cal=225.0, 
                                                            fat_grams=1.0, 
                                                            protein_grams=1.0, 
                                                            fiber_grams=5.0, 
                                                            sugar_grams=9.25, 
                                                            carb_grams=28.0, 
                                                            white_flour=True, 
                                                            animal=True)
                                        )], 
                                servings_eaten=[1.5], 
                                date_eaten=date(2026, 7, 5)
                                )
                        ]
    
    def test_calc_daily_totals(self):
        # Represents an integration test with calc_totals_per_serving, calc_totals_eaten:
        dates, daily_props = calc_daily_totals(meals_list=self.meal_list)

        self.assertEqual(len(dates),2)
        self.assertEqual(dates[1],date(2026,7,5))

        self.assertEqual(len(daily_props),2)
        self.assertEqual(len(daily_props[0].recipe_names),2)
        self.assertEqual(daily_props[1].recipe_names[0],"toast")
        
        self.assertEqual(daily_props[0].sugar_list[1],(8.375/1)*1.25) # 8.375 g sugar for the whole recipe, divided by 1 serving per recipe, times 1.25 servings eaten
        self.assertEqual(daily_props[1].cal_list[0],(225.0/1)*1.5)

    def test_display_meals_info(self):
        # TODO need mocking - patch get_meals
        pass

    def test_display_meal_breakdown(self):
        # TODO need mocking - patch get_meals
        pass