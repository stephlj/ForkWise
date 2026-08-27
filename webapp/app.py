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

# (display label, PropsPerDay field name, plotly chart type)
NUTRIENTS = [
    ("Calories", "cal_list", px.scatter),
    ("Protein (g)", "prot_list", px.bar),
    ("Sugar (g)", "sugar_list", px.bar),
    ("Fiber (g)", "fiber_list", px.bar),
    ("Fat (g)", "fat_list", px.bar),
]


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
        field: [sum(getattr(p, field)) for p in daily_props]
        for _, field, _ in NUTRIENTS
    }


def render_pie(daily_props: list[PropsPerDay], date_idx: int, prop_key: str, label: str) -> None:
    fig = plt.figure()
    ax = fig.add_subplot(111)
    plt.sca(ax)
    plot_pie(props_obj=daily_props[date_idx], prop=prop_key)
    ax.set_title(f"{label} breakdown")
    st.pyplot(fig)


def dashboard() -> None:
    st.title("ForkWise Dashboard")

    col_start, col_end = st.columns(2)
    start_date = col_start.date_input("Start date")
    end_date = col_end.date_input("End date")

    if start_date > end_date:
        st.error("Start date must be before end date.")
        return

    # Clear any drill-down selection if the date range has changed, since
    # the previously selected date may no longer be in range.
    date_range_key = (start_date, end_date)
    if st.session_state.get("last_range") != date_range_key:
        st.session_state.last_range = date_range_key
        st.session_state.selected = None

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

    chart_col, pie_col = st.columns(2)

    with chart_col:
        for label, prop_key, plot_fn in NUTRIENTS:
            df = pd.DataFrame({"date": dates, label: totals[prop_key]})
            fig = plot_fn(df, x="date", y=label, title=label)
            event = st.plotly_chart(
                fig, on_select="rerun", selection_mode="points", key=f"chart_{prop_key}"
            )
            points = event["selection"]["points"]
            if points:
                clicked_date = pd.to_datetime(points[0]["x"]).date()
                st.session_state.selected = {
                    "date": clicked_date,
                    "prop_key": prop_key,
                    "label": label,
                }

    with pie_col:
        selected = st.session_state.get("selected")
        if selected is None:
            st.info("Click a point on a chart to see which recipes contributed that day.")
        else:
            try:
                date_idx = dates.index(selected["date"])
            except ValueError:
                st.warning("Selected date is no longer in range.")
            else:
                st.subheader(f"{selected['label']} on {selected['date'].isoformat()}")
                render_pie(daily_props, date_idx, selected["prop_key"], selected["label"])


if not st.session_state.get("logged_in"):
    login()
else:
    dashboard()
