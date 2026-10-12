# app.py
#
# Streamlit app. Dashboard page: nutrient totals per day over a date range, with
# click-to-drill-down into a per-day recipe breakdown pie chart.
# Add data page: form for adding a recipe from existing pantry items.
#
# Written by Claude Code

import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import streamlit as st
import yaml

from forkwise.data_loader import DataLoader
from forkwise.display_meal_totals import get_meals, calc_daily_totals, plot_pie, PropsPerDay
from forkwise.fork_dataclasses import Ingredient
from forkwise.utils import CONFIG_PATH, DASHBOARD_TITLE
from forkwise.fork_db import ForkDB

st.set_page_config(page_title=DASHBOARD_TITLE, layout="wide")

# TODO hopefully none of this will be necessary after refactoring my dataclasses...
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

# config.yml's "targets" section keys are named after FoodProps fields, which
# don't match the PropsPerDay prop_keys above, so map one to the other here.
TARGET_TO_PROP_KEY = {
    "cal": CAL_PROP_KEY,
    "protein_grams": "prot_list",
    "sugar_grams": "sugar_list",
    "fiber_grams": "fiber_list",
    "fat_grams": "fat_list",
}


def login() -> None:
    st.title(DASHBOARD_TITLE)
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
    # TODO This rearranges the output of calc_daily_totals; may not be needed
    # after calc_daily_totals is refactored (or may replace it).
    # Should be moved to display_meal_totals.py and leave app.py just for plotting.
    return {
        prop_key: [sum(getattr(p, prop_key)) for p in daily_props]
        for prop_key in ALL_PROP_KEYS
    }


def render_pie(daily_props: list[PropsPerDay], date_idx: int, prop_key: str, label: str) -> None:
    fig = plt.figure()
    ax = fig.add_subplot(111)
    plt.sca(ax)
    plot_pie(props_obj=daily_props[date_idx], prop=prop_key)
    #ax.set_title(f"{label} breakdown")
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
    st.title(DASHBOARD_TITLE)

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

    with open(CONFIG_PATH, "r") as config_file:
        targets = yaml.safe_load(config_file).get("targets", {})
    targets_by_prop_key = {
        TARGET_TO_PROP_KEY[key]: value
        for key, value in targets.items()
        if key in TARGET_TO_PROP_KEY
    }

    # Widget keys include the date range so that changing it always starts
    # each chart with a fresh (empty) selection, rather than carrying over a
    # click made against a now-different set of dates.
    range_suffix = f"{start_date.isoformat()}_{end_date.isoformat()}"

    cal_chart_col, cal_pie_col = st.columns(2)
    with cal_chart_col:
        cal_df = pd.DataFrame({"date": dates, CAL_LABEL: totals[CAL_PROP_KEY]})
        cal_fig = px.scatter(cal_df, x="date", y=CAL_LABEL, title=CAL_LABEL)
        cal_target = targets_by_prop_key.get(CAL_PROP_KEY)
        if cal_target is not None:
            cal_fig.add_hline(y=cal_target, line_dash="dash", line_color=cal_fig.data[0].marker.color)
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
            title="Nutrients",
        )
        grams_colors = {trace.name: trace.marker.color for trace in grams_fig.data}
        for label, prop_key in GRAM_NUTRIENTS:
            grams_target = targets_by_prop_key.get(prop_key)
            if grams_target is not None:
                grams_fig.add_hline(y=grams_target, line_dash="dash", line_color=grams_colors[label])

        # Plotly auto-detects a date-like x column as a continuous date axis.
        # For a grouped bar chart, the 4 bars for a given day then get
        # positioned using real calendar spacing between days; if some day in
        # the range has no logged meals (no bar at all), that spacing math
        # shifts, and a bar can end up reporting the neighboring day when
        # clicked. Forcing a categorical axis gives every day an equal-width
        # slot regardless of calendar gaps, so a bar always reports the exact
        # date it belongs to. (Confirmed via fig.layout.xaxis.type: without
        # this, it's left as auto/None; this pins it to "category".)
        grams_fig.update_xaxes(type="category")
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


def add_data() -> None:
    # Form for adding a recipe built from existing pantry items, one ingredient per row.
    # Not an st.form: forms hold back reruns until submit, so a row's unit list
    # couldn't update when its ingredient changes.
    st.title("Add a recipe")

    with open(CONFIG_PATH, "r") as config_file:
        db_name = yaml.safe_load(config_file)["db"]["db_name"]

    # Fetched once per session rather than on every rerun (each widget change reruns the page).
    if "compatible_units" not in st.session_state:
        with ForkDB(user=st.session_state.username, pw=st.session_state.pw, db_name=db_name) as db:
            st.session_state.all_units = db.list_all_units()
            st.session_state.compatible_units = db.list_compatible_units()
    all_units = st.session_state.all_units
    compatible_units = st.session_state.compatible_units
    pantry_names = sorted(compatible_units, key=str.lower)

    # Set by a successful save on the previous run, which then cleared the form and reran.
    saved_name = st.session_state.pop("saved_recipe_name", None)
    if saved_name is not None:
        st.success(f"Added recipe {saved_name}.")

    if "ingr_row_ids" not in st.session_state:
        st.session_state.ingr_row_ids = [0]
        st.session_state.next_row_id = 1

    name = st.text_input("Recipe name", key="recipe_name")
    servings_col, amt_col, units_col = st.columns(3)
    # value=None leaves the box empty until filled in; 0 is caught on save
    servings = servings_col.number_input("Servings", min_value=0.0, value=None, key="servings")
    servings_amt = amt_col.number_input("Amount per serving", min_value=0.0, value=None, key="servings_amt")
    servings_units = units_col.selectbox("Serving units", options=all_units, index=None, key="servings_units")

    st.subheader("Ingredients")
    # Widget keys use a row id rather than the row's position, so removing a
    # row doesn't shift the remaining rows' values onto their neighbors.
    rows = []
    for row_id in st.session_state.ingr_row_ids:
        ingr_col, amt_col, units_col, remove_col = st.columns([3, 1, 1, 0.3], vertical_alignment="bottom")
        ingr = ingr_col.selectbox("Ingredient", options=pantry_names, index=None,
                                  placeholder="Type to search", key=f"ingr_{row_id}")
        amt = amt_col.number_input("Amount", min_value=0.0, value=None, key=f"amt_{row_id}")

        unit_options = compatible_units.get(ingr, [])
        # If the ingredient changed to one in a different category, the old unit is no longer valid
        if st.session_state.get(f"units_{row_id}") not in unit_options:
            st.session_state[f"units_{row_id}"] = None
        units = units_col.selectbox("Units", options=unit_options, index=None, key=f"units_{row_id}")

        # A callback (runs before the next rerun) rather than `if st.button(...): st.rerun()`:
        # rerunning mid-loop skips drawing the rows after this one, and Streamlit
        # then discards their values.
        remove_col.button("✕", key=f"remove_{row_id}", on_click=st.session_state.ingr_row_ids.remove, args=(row_id,))
        rows.append((ingr, amt, units))

    if st.button("+ Add ingredient"):
        st.session_state.ingr_row_ids.append(st.session_state.next_row_id)
        st.session_state.next_row_id += 1
        st.rerun()

    if not st.button("Save recipe", type="primary"):
        return

    header_filled = name.strip() and servings and servings_amt and servings_units
    rows_filled = rows and all(ingr and amt and units for ingr, amt, units in rows)
    if not (header_filled and rows_filled):
        st.error("Fill in the recipe name, servings, and every ingredient row (amounts must be more than 0).")
        return

    ingredients = [Ingredient(ingr_name=ingr, ingredient_amt=amt, ingredient_units=units) for ingr, amt, units in rows]
    try:
        with DataLoader(user=st.session_state.username, pw=st.session_state.pw, db_name=db_name) as loader:
            loader.add_recipe_via_staging(ingredients=ingredients, name=name.strip(), servings=servings,
                                          servings_amt=servings_amt, servings_units=servings_units)
    except Exception as e:
        # Covers duplicate recipe names and duplicate ingredient sets; the form keeps what was entered
        st.error(f"Could not save recipe: {e}")
        return

    # Clear the form. Widget values can't be changed after the widget is drawn
    # in this run, so delete their state and rerun to redraw them empty.
    for key in ["recipe_name", "servings", "servings_amt", "servings_units"]:
        del st.session_state[key]
    for row_id in st.session_state.ingr_row_ids:
        for prefix in ["ingr", "amt", "units"]:
            del st.session_state[f"{prefix}_{row_id}"]
    del st.session_state.ingr_row_ids
    # Refetch the lists too, in case pantry items or units were added outside the webapp (e.g. via the CLI)
    del st.session_state.compatible_units
    st.session_state.saved_recipe_name = name.strip()
    st.rerun()


if not st.session_state.get("logged_in"):
    login()
else:
    st.navigation([st.Page(dashboard, title="Dashboard"), st.Page(add_data, title="Add data")]).run()
