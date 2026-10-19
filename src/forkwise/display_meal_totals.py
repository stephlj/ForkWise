# Simple CLI to display information about a meals eaten in a date range.
# 
# Copyright (c) 2026 Stephanie Johnson

import sys
import logging
import yaml
import pandas as pd
import matplotlib.pyplot as plt

from datetime import date
from typing import List

from forkwise.utils import DEFAULT_LOGGING_FORMAT, CONFIG_PATH, PROPS_DISPLAY_NAMES
from forkwise.data_getter import DataGetter
from forkwise.fork_dataclasses import FOODPROPS_COL_NAMES

logger = logging.getLogger(__name__)
logging.basicConfig(level="INFO", format=DEFAULT_LOGGING_FORMAT)

def plot_pie(prop_totals: List[float], recipe_names: List[str]) -> None:
    # Before this function call, choose axies to plot into
    plt.pie(x=prop_totals,labels=recipe_names, autopct=lambda v: round(v*sum(prop_totals)/100,2))

def calc_daily_totals(meals_df: pd.DataFrame) -> pd.DataFrame:
    """
    Sum each nutrient over all recipes eaten on each date.
    meals_df is the output of get_meals. Returns a df indexed by date_eaten (sorted),
    one row per date, with nutrient columns (cal, fat_grams, etc).
    """
    # These columns don't make sense summed over a day. Dropped before the sum
    # rather than after, so pandas doesn't concatenate all the recipe names.
    return meals_df.drop(columns=["recipe_name", "animal", "white_flour"]).groupby("date_eaten").sum()

def display_meal_breakdown(meals_df: pd.DataFrame, test: bool=False) -> None:
    # Pie charts of nutritional breakdown by recipe for one day

    # Note the input df should have only one date, check first:
    if meals_df["date_eaten"].nunique() != 1:
        msg = "Meals data frame must contain meals for only one date"
        logger.error(msg)
        raise ValueError(msg)

    _ = plt.figure()
    # TODO iterate through FOODPROPS_COL_NAMES? Or othewise change this so I'm not re-copying "cal" etc in 2 lines
    ax00 = plt.subplot2grid((2,3),(0,0))
    plot_pie(prop_totals = meals_df["cal"].to_list(), recipe_names=meals_df["recipe_name"].to_list())
    ax00.set_title(PROPS_DISPLAY_NAMES["cal"])
    ax01 = plt.subplot2grid((2,3),(0,1))
    plot_pie(prop_totals = meals_df["protein_grams"].to_list(), recipe_names=meals_df["recipe_name"].to_list())
    ax01.set_title(PROPS_DISPLAY_NAMES["protein_grams"])
    ax02 = plt.subplot2grid((2,3),(0,2))
    plot_pie(prop_totals = meals_df["sugar_grams"].to_list(), recipe_names=meals_df["recipe_name"].to_list())
    ax02.set_title(PROPS_DISPLAY_NAMES["sugar_grams"])
    ax10 = plt.subplot2grid((2,3),(1,0))
    plot_pie(prop_totals = meals_df["fiber_grams"].to_list(), recipe_names=meals_df["recipe_name"].to_list())
    ax10.set_title(PROPS_DISPLAY_NAMES["fiber_grams"])
    ax11 = plt.subplot2grid((2,3),(1,1))
    plot_pie(prop_totals = meals_df["fat_grams"].to_list(), recipe_names=meals_df["recipe_name"].to_list())
    ax11.set_title(PROPS_DISPLAY_NAMES["fat_grams"])

    if not test:
        plt.show()

def display_meals_info(meals_df: pd.DataFrame, test: bool=False) -> None:
    """
    Plot a scatter of calories per date, and a bar chart of total fat, protein etc per date.
    TODO add: fraction total protein from animal sources, fraction carbs from white flour
    """

    daily_totals = calc_daily_totals(meals_df)

    _, axs = plt.subplots(2, 1)
    plt.subplots_adjust(hspace=0.5) # from claude

    # Plot cal per date
    axs[0].plot(daily_totals.index.to_list(),daily_totals["cal"].to_list(),'ob')
    axs[0].set_xlabel("Date")
    axs[0].set_ylabel(PROPS_DISPLAY_NAMES["cal"])
    axs[0].tick_params(axis='x', rotation=45) # from claude

    # plot grams of protein, sugar, fiber per day (cal is plotted above, and isn't in grams)
    pd_ax = daily_totals.drop(columns=["cal"]).plot.bar(ax=axs[1],rot=0)
    pd_ax.set_xlabel("Date")
    pd_ax.set_ylabel("Grams")
    pd_ax.legend()
    pd_ax.tick_params(axis='x', rotation=45)

    if not test:
        plt.show()

def get_meals(date_range: List[date], username: str, pw: str, path_to_config: str=CONFIG_PATH) -> pd.DataFrame:
    with open(path_to_config, "r") as config_file:
        config = yaml.safe_load(config_file)
        db_name = config["db"]["db_name"]

    with DataGetter(user=username, pw=pw, db_name=db_name) as dg:
        meals_df = dg.get_totals_in_dates(date_range=date_range)

    return meals_df

if __name__ == "__main__":

    if len(sys.argv) != 5:
        raise ValueError("fork_init takes 4 args: (1) user name to connect to the db, (2) user pw, (3) start date to plot, (4) end date")

    meals_df = get_meals(date_range=[date.fromisoformat(sys.argv[3]),date.fromisoformat(sys.argv[4])], username=sys.argv[1], pw=sys.argv[2])
    
    if date.fromisoformat(sys.argv[3])==date.fromisoformat(sys.argv[4]):
        display_meal_breakdown(meals_df=meals_df)
    else:
        display_meals_info(meals_df=meals_df)