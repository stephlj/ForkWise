# Simple CLI to display information about a meals eaten in a date range.
# 
# Copyright (c) 2026 Stephanie Johnson

import sys
import logging
import yaml
import pandas as pd
import matplotlib.pyplot as plt

from datetime import date
from collections import namedtuple
from typing import List
from forkwise.fork_dataclasses import Meal, Recipe

from forkwise.utils import DEFAULT_LOGGING_FORMAT, CONFIG_PATH, calc_totals_per_serving
from forkwise.fork_db import ForkDB

RecipesPerDate = namedtuple('RecipesPerDate',[('date_eaten',date),('recipe_list',List[Recipe])])

def get_meals(date_range: List[date], username: str, pw: str, path_to_config: str=CONFIG_PATH) -> List[RecipesPerDate]:
    with open(path_to_config, "r") as config_file:
        config = yaml.safe_load(config_file)
        db_name = config["db"]["db_name"]

    conn = ForkDB(user=username, pw=pw, db_name=db_name)
    meals_list = conn.get_meals_in_dates(date_range=date_range)

    meals=[]
    # TODO just change get_meals_in_dates to return this named tuple? This is goofy
    for m in meals:
        this_date = m.date_eaten
        todays_recipes = []
        for i in range(0,len(m.recipes)): # TODO I don't think this should scramble (servings_eaten, recipe_name)? triple check
            todays_recipes.append(conn.get_recipe_totals(recipe_name=m.recipes[i])) #get_recipe_totals returns a Recipe
        meals.append(RecipesPerDate(date_eaten=this_date, recipe_list=todays_recipes))

    conn.close()

    return meals

def display_meals_info(date_range: List[date], username: str, pw: str, path_to_config: str=CONFIG_PATH):
    """
    Retrieve info on meals eaten in date_range from the db, calculate info per day, print info to command line.
    """

    meals = get_meals(date_range=date_range, username=username, pw=pw, path_to_config=path_to_config)

    # Meals is a list of Meals. A Meal contains a list of Recipes (and servings of those Recipes) eaten on one date.
    # I want to plot total calories, total protein etc on y against dates on x.

    dates = []
    tot_cal = []
    tot_prot = []
    tot_sugar = []
    tot_fiber = []
    # to add: fraction total protein from animal sources, fraction carbs from white flour

    for m in meals:
        dates.append(m.date_eaten)
        daily_cal = []
        daily_prot = []
        daily_sugar = []
        daily_fiber = []
        for i in range(0,len(m.recipes)): # TODO I don't think this should scramble (servings_eaten, recipe_name)? triple check
            recipe = conn.get_recipe_totals(recipe_name=m.recipes[i])
            totals = calc_totals_per_serving(recipe=recipe)
            daily_cal.append(totals.cal*m.servings_eaten[i])
            daily_prot.append(totals.protein_grams*m.servings_eaten[i])
            daily_sugar.append(totals.sugar_grams*m.servings_eaten[i])
            daily_fiber.append(totals.fiber_grams*m.servings_eaten[i])
        tot_cal.append(sum(daily_cal))
        tot_prot.append(sum(daily_prot))
        tot_sugar.append(sum(daily_sugar))
        tot_fiber.append(sum(daily_fiber))

    # TODO print recipe names per day

    _, axs = plt.subplots(2, 1)
    plt.subplots_adjust(hspace=0.5) # from claude

    # Plot cal per date
    axs[0].plot(dates,tot_cal,'ob')
    axs[0].set_xlabel("Date")
    axs[0].set_ylabel("Calories")
    axs[0].tick_params(axis='x', rotation=45) # from claude

    # plot grams of protein, sugar, fiber per day
    grouped_totals = {"Protein": tot_prot, "Sugar": tot_sugar, "Fiber": tot_fiber}
    g_df = pd.DataFrame(grouped_totals,index=dates)
    pd_ax = g_df.plot.bar(ax=axs[1],rot=0)
    pd_ax.set_xlabel("Date")
    pd_ax.set_ylabel("Grams")
    pd_ax.legend()
    pd_ax.tick_params(axis='x', rotation=45)

    plt.show()

def display_meal_breakdown(date_eaten: date, username: str, pw: str, path_to_config: str=CONFIG_PATH):
    
    meals = get_meals(date_range=[date_eaten, date_eaten], username=username, pw=pw, path_to_config=path_to_config)


if __name__ == "__main__":
    logger = logging.getLogger(__name__)

    if len(sys.argv) != 5:
        raise ValueError("fork_init takes 4 args: (1) user name to connect to the db, (2) user pw, (3) start date to plot, (4) end date")
    
    logging.basicConfig(level="INFO", format=DEFAULT_LOGGING_FORMAT)
    
    if date.fromisoformat(sys.argv[3])==date.fromisoformat(sys.argv[4]):
        display_meal_breakdown(date_eaten=date.fromisoformat(sys.argv[3]), username=sys.argv[1], pw=sys.argv[2])
    else:
        display_meals_info(date_range=[date.fromisoformat(sys.argv[3]),date.fromisoformat(sys.argv[4])], username=sys.argv[1], pw=sys.argv[2])