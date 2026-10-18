# app.py
#
# Streamlit dashboard: nutrient totals per day over a date range, with
# click-to-drill-down into a per-day recipe breakdown pie chart.
#
# Written by Claude Code

import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import streamlit as st
import yaml

from forkwise.data_getter import DataGetter
from forkwise.display_meal_totals import calc_daily_totals, plot_pie
from forkwise.utils import CONFIG_PATH, DASHBOARD_TITLE, PROPS_DISPLAY_NAMES

st.set_page_config(page_title=DASHBOARD_TITLE, layout="wide")

# These all have units of grams, so they're plotted together as one grouped
# bar chart rather than one chart each.
GRAM_NUTRIENTS = ["protein_grams", "sugar_grams", "fiber_grams", "fat_grams"]


def login() -> None:
    # Sets st.session_state.logged_in, username, pw, db_name and targets, which dashboard reads.
    st.title(DASHBOARD_TITLE)
    with st.form("login"):
        username = st.text_input("Username")
        pw = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in")
    if not submitted:
        return

    with open(CONFIG_PATH, "r") as config_file:
        config = yaml.safe_load(config_file)
    try:
        # Open a connection just to check the credentials. dashboard opens its own
        # short-lived connection on each run rather than keeping one open all session.
        with DataGetter(user=username, pw=pw, db_name=config["db"]["db_name"]):
            pass
    except Exception as e:
        st.error(f"Could not connect: {e}")
        return

    st.session_state.logged_in = True
    st.session_state.username = username
    st.session_state.pw = pw
    # Config is read once here, rather than on every rerun of the dashboard
    st.session_state.db_name = config["db"]["db_name"]
    st.session_state.targets = config.get("targets", {})
    # Without this, the dashboard wouldn't render until some other widget
    # interaction triggered a second run: setting session_state here doesn't
    # retroactively change which branch this run took.
    st.rerun()


def dashboard() -> None:
    # Reads st.session_state.username, pw and db_name, set by login.
    # Streamlit draws widgets in the order they're called, so the calls below
    # are also the page layout, top to bottom.
    st.title(DASHBOARD_TITLE)

    start_col, end_col = st.columns(2)
    start_date = start_col.date_input("Start date", format="YYYY-MM-DD")
    end_date = end_col.date_input("End date", format="YYYY-MM-DD")
    if start_date > end_date:
        st.error("Start date must be before end date.")
        return

    with DataGetter(user=st.session_state.username, pw=st.session_state.pw, db_name=st.session_state.db_name) as dg:
        meals_df = dg.get_totals_in_dates(date_range=[start_date, end_date])
    if meals_df.empty:
        st.info("No meals logged in this date range.")
        return
    daily_totals = calc_daily_totals(meals_df)

    # Widget keys include the date range so that changing it always starts
    # each chart with a fresh (empty) selection, rather than carrying over a
    # click made against a now-different set of dates.
    range_suffix = f"{start_date.isoformat()}_{end_date.isoformat()}"

    cal_chart_col, cal_pie_col = st.columns(2)
    with cal_chart_col:
        cal_points = calories_chart(daily_totals, key=f"chart_cal_{range_suffix}")
    with cal_pie_col:
        breakdown_pie(meals_df, cal_points, "cal",
                      placeholder="Click a point on the calories chart to see that day's recipe breakdown.")

    grams_chart_col, grams_pie_col = st.columns(2)
    with grams_chart_col:
        grams_points = grams_chart(daily_totals, key=f"chart_grams_{range_suffix}")
    with grams_pie_col:
        # Each bar carries its nutrient's column name in customdata (see grams_chart)
        nutrient = grams_points[0]["customdata"][0] if grams_points else None
        breakdown_pie(meals_df, grams_points, nutrient,
                      placeholder="Click a bar to see that nutrient's recipe breakdown for that day.")


def calories_chart(daily_totals: pd.DataFrame, key: str) -> list[dict]:
    # Scatter of total calories per day, with a dashed line at the calorie target if there is one.
    # Reads st.session_state.targets, set by login. Returns the selected points (empty if none).
    label = PROPS_DISPLAY_NAMES["cal"]
    fig = px.scatter(x=daily_totals.index, y=daily_totals["cal"], labels={"x": "Date", "y": label}, title=label)
    target = st.session_state.targets.get("cal")
    if target is not None:
        fig.add_hline(y=target, line_dash="dash", line_color=fig.data[0].marker.color)
    event = st.plotly_chart(fig, on_select="rerun", selection_mode="points", key=key)
    return event["selection"]["points"]


def grams_chart(daily_totals: pd.DataFrame, key: str) -> list[dict]:
    # Grouped bar chart of each gram-based nutrient per day, with a dashed line in the
    # matching color at each nutrient's target, if it has one.
    # Reads st.session_state.targets, set by login. Returns the selected points (empty if none).

    # px.bar groups and colors by a column, so reshape to one row per (date, nutrient)
    grams_df = daily_totals[GRAM_NUTRIENTS].reset_index().melt(
        id_vars="date_eaten", var_name="nutrient", value_name="grams")
    grams_df["label"] = grams_df["nutrient"].map(PROPS_DISPLAY_NAMES)
    # custom_data carries each bar's column name, so a click can be traced back
    # to the right nutrient regardless of trace order
    fig = px.bar(grams_df, x="date_eaten", y="grams", color="label", barmode="group", custom_data=["nutrient"],
                 labels={"date_eaten": "Date", "label": "Nutrient"}, title="Nutrients")

    colors = {trace.name: trace.marker.color for trace in fig.data}
    for nutrient in GRAM_NUTRIENTS:
        target = st.session_state.targets.get(nutrient)
        if target is not None:
            fig.add_hline(y=target, line_dash="dash", line_color=colors[PROPS_DISPLAY_NAMES[nutrient]])

    # Plotly auto-detects a date-like x column as a continuous date axis.
    # For a grouped bar chart, the bars for a given day then get positioned
    # using real calendar spacing between days; if some day in the range has
    # no logged meals, that spacing shifts, and a clicked bar can report the
    # neighboring day. A categorical axis gives every day an equal-width slot
    # regardless of gaps, so a bar always reports its own date.
    fig.update_xaxes(type="category")
    event = st.plotly_chart(fig, on_select="rerun", selection_mode="points", key=key)
    return event["selection"]["points"]


def breakdown_pie(meals_df: pd.DataFrame, points: list[dict], nutrient: str | None, placeholder: str) -> None:
    # Pie chart of how much each recipe contributed to one nutrient on the selected day,
    # or the placeholder message if nothing is selected.
    # A chart's selection persists across reruns (Streamlit keeps showing it as
    # selected until the user clicks elsewhere on that chart), so whatever is
    # selected now is what the pie should show; no need to track it ourselves.
    if not points:
        st.info(placeholder)
        return

    clicked_date = pd.to_datetime(points[0]["x"]).date()
    day_df = meals_df[meals_df["date_eaten"] == clicked_date]
    if day_df.empty:
        st.warning("Selected date is no longer in range.")
        return

    st.subheader(f"{PROPS_DISPLAY_NAMES[nutrient]} on {clicked_date.isoformat()}")
    fig = plt.figure()
    plot_pie(prop_totals=day_df[nutrient].to_list(), recipe_names=day_df["recipe_name"].to_list())
    st.pyplot(fig)
    # pyplot keeps every figure in memory until it's closed
    plt.close(fig)


if not st.session_state.get("logged_in"):
    login()
else:
    dashboard()
