# Simple CLI to display information about a meals eaten in a date range.
# 
# Copyright (c) 2026 Stephanie Johnson

import sys
import logging
import yaml
import pandas as pd
import matplotlib.pyplot as plt

from datetime import date
# from collections import namedtuple
from typing import NamedTuple
from typing import List
from forkwise.fork_dataclasses import Meal, Recipe

from forkwise.utils import DEFAULT_LOGGING_FORMAT, CONFIG_PATH, calc_totals_per_serving, calc_totals_eaten
from forkwise.fork_db import ForkDB

PropsPerDay = NamedTuple('PropsPerDay',
                         [('recipe_names',List[str]),
                          ('cal_list',List[float]),
                          ('prot_list',List[float]),
                          ('sugar_list',List[float]),
                          ('fiber_list',List[float]),
                          ('fat_list',List[float])
                          ])

def get_meals(date_range: List[date], username: str, pw: str, path_to_config: str=CONFIG_PATH) -> List[Meal]:
    with open(path_to_config, "r") as config_file:
        config = yaml.safe_load(config_file)
        db_name = config["db"]["db_name"]

    conn = ForkDB(user=username, pw=pw, db_name=db_name)
    meals_list = conn.get_meals_in_dates(date_range=date_range)

    conn.close()

    return meals_list

def calc_daily_totals(meals_list: List[Meal]) -> tuple[List[date],List[PropsPerDay]]:
    """
    Given a list of Meals, return calorie, protein etc totals per recipe*servings per day.

    # TODO return a dict? This feels fragile.
    """
    dates = []
    daily_props = []
    
    for m in meals_list:
        dates.append(m.date_eaten)
        names = []
        daily_cal = []
        daily_prot = []
        daily_sugar = []
        daily_fiber = []
        daily_fat = []
        for i in range(0,len(m.recipes)): # TODO I don't think this should scramble (servings_eaten, recipe_name)? triple check
            names.append(m.recipes[i].name)
            totals = calc_totals_per_serving(recipe=m.recipes[i])
            totals_eaten = calc_totals_eaten(tots_per_serv=totals, servings_eaten=m.servings_eaten[i])
            daily_cal.append(totals_eaten.cal)
            daily_prot.append(totals_eaten.protein_grams)
            daily_sugar.append(totals_eaten.sugar_grams)
            daily_fiber.append(totals_eaten.fiber_grams)
            daily_fat.append(totals_eaten.fat_grams)
        daily_props.append(PropsPerDay(
                                recipe_names=names,
                                cal_list=daily_cal,
                                prot_list=daily_prot,
                                sugar_list=daily_sugar,
                                fiber_list=daily_fiber,
                                fat_list=daily_fat
                                ))
        
    return (dates,daily_props)

def display_meals_info(date_range: List[date], username: str, pw: str, path_to_config: str=CONFIG_PATH) -> None:
    """
    Retrieve info on meals eaten in date_range from the db, calculate info per day, print info to command line.
    """

    meals = get_meals(date_range=date_range, username=username, pw=pw, path_to_config=path_to_config)

    dates, daily_props = calc_daily_totals(meals_list=meals)

    tot_cal = []
    tot_prot = []
    tot_sugar = []
    tot_fiber = []
    tot_fat = []
    # to add: fraction total protein from animal sources, fraction carbs from white flour

    for p in daily_props:
        tot_cal.append(sum(p.cal_list))
        tot_prot.append(sum(p.prot_list))
        tot_sugar.append(sum(p.sugar_list))
        tot_fiber.append(sum(p.fiber_list))
        tot_fat.append(sum(p.fat_list))

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

def display_meal_breakdown(date_eaten: date, username: str, pw: str, path_to_config: str=CONFIG_PATH) -> None:
    
    meals = get_meals(date_range=[date_eaten, date_eaten], username=username, pw=pw, path_to_config=path_to_config)

    _, all_props = calc_daily_totals(meals_list=meals)

    daily_props = all_props[0]
    
    fig = plt.figure()
    ax00 = plt.subplot2grid((2,3),(0,0))
    plt.pie(x=daily_props.cal_list,labels=daily_props.recipe_names)
    ax00.set_title("Calories")
    ax01 = plt.subplot2grid((2,3),(0,1))
    plt.pie(x=daily_props.prot_list,labels=daily_props.recipe_names)
    ax01.set_title("Protein (g)")
    ax02 = plt.subplot2grid((2,3),(0,2))
    plt.pie(x=daily_props.sugar_list,labels=daily_props.recipe_names)
    ax02.set_title("Sugar (g)")
    ax10 = plt.subplot2grid((2,3),(1,0))
    plt.pie(x=daily_props.fiber_list,labels=daily_props.recipe_names)
    ax10.set_title("Fiber (g)")
    ax11 = plt.subplot2grid((2,3),(1,1))
    plt.pie(x=daily_props.fat_list,labels=daily_props.recipe_names)
    ax11.set_title("Fat (g)")

    plt.show()


if __name__ == "__main__":
    logger = logging.getLogger(__name__)

    if len(sys.argv) != 5:
        raise ValueError("fork_init takes 4 args: (1) user name to connect to the db, (2) user pw, (3) start date to plot, (4) end date")
    
    logging.basicConfig(level="INFO", format=DEFAULT_LOGGING_FORMAT)
    
    if date.fromisoformat(sys.argv[3])==date.fromisoformat(sys.argv[4]):
        display_meal_breakdown(date_eaten=date.fromisoformat(sys.argv[3]), username=sys.argv[1], pw=sys.argv[2])
    else:
        display_meals_info(date_range=[date.fromisoformat(sys.argv[3]),date.fromisoformat(sys.argv[4])], username=sys.argv[1], pw=sys.argv[2])