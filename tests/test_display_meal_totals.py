import unittest
import pandas as pd
import matplotlib.pyplot as plt

from forkwise.display_meal_totals import display_meal_breakdown, display_meals_info

class DisplayMealTotals(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # TODO fix these date formats and make real numbers for cal etc
        cls.meals_df  = pd.DataFrame({"date_eaten":['2026-06-02','2026-06-02','2026-07-05','2026-07-05'],
                                      "recipe_name":['toast','soy cocoa','toast','hummus'],
                                      "cal":[1,2,1,3],
                                      "fiber_grams" : [1,2,3,4],
                                      "sugar_grams" : [1,2,3,4],
                                      "protein_grams" : [1,2,3,4],
                                      "fat_grams" : [1,2,3,4],
                                      "carb_grams" : [1,2,3,4],
                                      "animal":[1,0,1,0],
                                      "white_flour": [0,1,0,1]
                                      })
    

    def test_display_meal_breakdown(self):
        # Implicit test of plot_pie
        # just a does-it-run test, doesn't check plotted output - do that manually!

        display_meal_breakdown(self.meals_df[self.meals_df["date_eaten"]=='2026-06-02'], test=True)
        plt.close('all')

    def test_display_meals_info(self):
        # just a does-it-run test, doesn't check plotted output - do that manually!

        display_meals_info(self.meals_df, test=True)

