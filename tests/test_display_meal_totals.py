import unittest
import pandas as pd
import matplotlib.pyplot as plt

from forkwise.display_meal_totals import calc_daily_totals, display_meal_breakdown, display_meals_info

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
    

    def test_calc_daily_totals(self):
        daily_totals = calc_daily_totals(self.meals_df)

        with self.subTest("There is one row per date, sorted by date."):
            self.assertEqual(daily_totals.index.to_list(), ['2026-06-02', '2026-07-05'])

        with self.subTest("Each nutrient is summed over all recipes eaten that day."):
            self.assertEqual(daily_totals["cal"].to_list(), [3, 4])
            self.assertEqual(daily_totals["fiber_grams"].to_list(), [3, 7])
            self.assertEqual(daily_totals["carb_grams"].to_list(), [3, 7])

        with self.subTest("Columns that don't make sense summed over a day are dropped."):
            self.assertEqual(set(daily_totals.columns),
                             {"cal", "fiber_grams", "sugar_grams", "protein_grams", "fat_grams", "carb_grams"})

    def test_display_meal_breakdown(self):
        # Implicit test of plot_pie
        # just a does-it-run test, doesn't check plotted output - do that manually!

        # TODO test empty df
        display_meal_breakdown(self.meals_df[self.meals_df["date_eaten"]=='2026-06-02'], test=True)
        plt.close('all')

    def test_display_meals_info(self):
        # just a does-it-run test, doesn't check plotted output - do that manually!

        # TODO test empty df
        display_meals_info(self.meals_df, test=True)

