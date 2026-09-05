# app.py
#
# Streamlit dashboard: nutrient totals per day over a date range, with
# click-to-drill-down into a per-day recipe breakdown pie chart.
#
# Copyright (c) 2026 Stephanie Johnson

import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import streamlit as st
import yaml

from forkwise.display_meal_totals import get_meals, calc_daily_totals, plot_pie, PropsPerDay
from forkwise.utils import CONFIG_PATH
from forkwise.fork_db import ForkDB

st.set_page_config(page_title="ForkWise Dashboard", layout="wide")

CAL_PROP_KEY = "cal_list"
CAL_LABEL = "Calories"

# The remaining PropsPerDay fields all share units of grams, so they're
# plotted together as one grouped bar chart rather than one chart each.
GRAM_NUTRIENTS = [
    ("Protein (g)", "prot_list"),
    ("Sugar (g)", "sugar_list"),
    ("Fiber (g)", "fiber_list"),
    ("Fat (g)", "fat_list"),
]

PROP_LABELS = {CAL_PROP_KEY: CAL_LABEL, **{prop_key: label for label, prop_key in GRAM_NUTRIENTS}}
ALL_PROP_KEYS = [CAL_PROP_KEY] + [prop_key for _, prop_key in GRAM_NUTRIENTS]


def login() -> None:
    st.title("ForkWise Dashboard")
    with st.form("login"):
        username = st.text_input("Username")
        pw = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in")

    if submitted:
        with open(CONFIG_PATH, "r") as config_file:
            db_name = yaml.safe_load(config_file)["db"]["db_name"]
        try:
            # Open a connection just to validate the credentials, then close
            # it; get_meals() opens its own short-lived connection per call,
            # same as the existing CLI scripts, so there's no need to keep
            # one alive for the whole session.
            conn = ForkDB(user=username, pw=pw, db_name=db_name)
            conn.close()
            st.session_state.logged_in = True
            st.session_state.username = username
            st.session_state.pw = pw
            # Without this, the dashboard wouldn't render until some other
            # widget interaction triggered a second script run: setting
            # session_state here doesn't retroactively change which branch
            # this run took.
            st.rerun()
        except Exception as e:
            st.error(f"Could not connect: {e}")


def totals_per_day(daily_props: list[PropsPerDay]) -> dict[str, list[float]]:
    # Sum each nutrient's per-recipe breakdown into a single daily total.
    return {
        prop_key: [sum(getattr(p, prop_key)) for p in daily_props]
        for prop_key in ALL_PROP_KEYS
    }


def render_pie(daily_props: list[PropsPerDay], date_idx: int, prop_key: str, label: str) -> None:
    fig = plt.figure()
    ax = fig.add_subplot(111)
    plt.sca(ax)
    plot_pie(props_obj=daily_props[date_idx], prop=prop_key)
    ax.set_title(f"{label} breakdown")
    st.pyplot(fig)


def _render_drilldown(points: list[dict], dates: list, daily_props: list[PropsPerDay], prop_key: str, label: str, placeholder: str) -> None:
    # A chart's own selection is already "sticky" across reruns (Streamlit/
    # Plotly keep showing it as selected until the user clicks elsewhere on
    # that same chart), so there's no need to track history ourselves here:
    # whatever this chart currently reports as selected is exactly what its
    # own pie panel should show.
    if not points:
        st.info(placeholder)
        return

    clicked_date = pd.to_datetime(points[0]["x"]).date()
    try:
        date_idx = dates.index(clicked_date)
    except ValueError:
        st.warning("Selected date is no longer in range.")
        return

    st.subheader(f"{label} on {clicked_date.isoformat()}")
    render_pie(daily_props, date_idx, prop_key, label)


def dashboard() -> None:
    st.title("ForkWise Dashboard")

    col_start, col_end = st.columns(2)
    start_date = col_start.date_input("Start date")
    end_date = col_end.date_input("End date")

    if start_date > end_date:
        st.error("Start date must be before end date.")
        return

    meals = get_meals(
        date_range=[start_date, end_date],
        username=st.session_state.username,
        pw=st.session_state.pw,
    )

    if not meals:
        st.info("No meals logged in this date range.")
        return

    dates, daily_props = calc_daily_totals(meals)
    totals = totals_per_day(daily_props)

    # Widget keys include the date range so that changing it always starts
    # each chart with a fresh (empty) selection, rather than carrying over a
    # click made against a now-different set of dates.
    range_suffix = f"{start_date.isoformat()}_{end_date.isoformat()}"

    cal_chart_col, cal_pie_col = st.columns(2)
    with cal_chart_col:
        cal_df = pd.DataFrame({"date": dates, CAL_LABEL: totals[CAL_PROP_KEY]})
        cal_fig = px.scatter(cal_df, x="date", y=CAL_LABEL, title=CAL_LABEL)
        cal_event = st.plotly_chart(
            cal_fig, on_select="rerun", selection_mode="points", key=f"chart_cal_{range_suffix}"
        )
    with cal_pie_col:
        _render_drilldown(
            cal_event["selection"]["points"], dates, daily_props, CAL_PROP_KEY, CAL_LABEL,
            placeholder="Click a point on the calories chart to see that day's recipe breakdown.",
        )

    # One grouped bar chart for every gram-based nutrient, colored by
    # nutrient. custom_data carries the PropsPerDay field name for each bar
    # so a click can be traced back to the right nutrient regardless of
    # trace order.
    grams_chart_col, grams_pie_col = st.columns(2)
    with grams_chart_col:
        grams_df = pd.concat(
            [
                pd.DataFrame(
                    {"date": dates, "grams": totals[prop_key], "nutrient": label, "prop_key": prop_key}
                )
                for label, prop_key in GRAM_NUTRIENTS
            ],
            ignore_index=True,
        )
        grams_fig = px.bar(
            grams_df,
            x="date",
            y="grams",
            color="nutrient",
            barmode="group",
            custom_data=["prop_key"],
            category_orders={"nutrient": [label for label, _ in GRAM_NUTRIENTS]},
            title="Protein / Sugar / Fiber / Fat (g)",
        )
        grams_event = st.plotly_chart(
            grams_fig, on_select="rerun", selection_mode="points", key=f"chart_grams_{range_suffix}"
        )
    with grams_pie_col:
        grams_points = grams_event["selection"]["points"]
        grams_prop_key = grams_points[0]["customdata"][0] if grams_points else None
        _render_drilldown(
            grams_points, dates, daily_props, grams_prop_key, PROP_LABELS.get(grams_prop_key),
            placeholder="Click a bar to see that nutrient's recipe breakdown for that day.",
        )


if not st.session_state.get("logged_in"):
    login()
else:
    dashboard()
