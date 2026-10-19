# add_data.py
#
# Add recipes page: form for adding a recipe from existing pantry items.
#
# Written by Claude Code

import streamlit as st

from forkwise.data_loader import DataLoader
from forkwise.fork_dataclasses import Ingredient
from forkwise.fork_db import ForkDB


def add_data() -> None:
    # Form for adding a recipe built from existing pantry items, one ingredient per row.
    # Not an st.form: forms hold back reruns until submit, so a row's unit list
    # couldn't update when its ingredient changes.
    # Streamlit draws widgets in the order they're called, so the calls below are
    # also the page layout, top to bottom.
    st.title("Add a recipe")

    load_units()
    show_saved_message() # Show a message if a recipe was saved
    name, servings, servings_amt, servings_units = recipe_header_inputs()
    ingrs = ingredient_rows()

    if not st.button("Save recipe", type="primary"):
        return
    if save_recipe(name.strip(), servings, servings_amt, servings_units, ingrs):
        clear_form(name.strip())


def load_units() -> None:
    # Sets st.session_state.all_units and st.session_state.compatible_units,
    # which recipe_header_inputs and ingredient_rows read.
    # When adding an ingredient for a recipe, provide a drop-down of compatible units for that pantry
    # item. And provide a drop-down of allowed units when creating the recipe.
    # So first get all allowed units and per-ingredient compatible units from the db.
    # Fetched once per session rather than on every rerun (each widget change reruns the page).
    # Nothing on this page changes these lists. A future page that adds pantry items or
    # units should delete st.session_state.compatible_units so they're refetched here.
    if "compatible_units" not in st.session_state:
        with ForkDB(user=st.session_state.username, pw=st.session_state.pw, db_name=st.session_state.db_name) as db:
            st.session_state.all_units = db.list_all_units()
            st.session_state.compatible_units = db.list_compatible_units()


def show_saved_message() -> None:
    # Reads st.session_state.saved_recipe_name, set by clear_form after a successful
    # save on the previous run (which then cleared the form and reran).
    saved_name = st.session_state.pop("saved_recipe_name", None)
    if saved_name is not None:
        st.success(f"Added recipe {saved_name}.")


def recipe_header_inputs() -> tuple[str, float | None, float | None, str | None]:
    # Recipe name and servings info. Returns what's currently entered (None for empty boxes).
    name = st.text_input("Recipe name", key="recipe_name")
    servings_col, amt_col, units_col = st.columns(3)
    # value=None leaves the box empty until filled in; 0 is caught on save
    # +/- change these by 0.5 (the default step, 0.01, is too fine)
    servings = servings_col.number_input("Servings that the recipe makes:", min_value=0.0, value=None, step=0.5, key="servings")
    servings_amt = amt_col.number_input("Amount per serving", min_value=0.0, value=None, step=0.5, key="servings_amt")
    servings_units = units_col.selectbox("Servings units", options=st.session_state.all_units, index=None, key="servings_units")
    return name, servings, servings_amt, servings_units


def ingredient_rows() -> list[tuple[str | None, float | None, str | None]]:
    # One row per ingredient (ingredient, amount, units), plus remove and "+ Add ingredient" buttons.
    # Returns (ingredient, amount, units) per row, None for anything not filled in yet.
    # Keeps the list of row ids in st.session_state.ingr_row_ids (clear_form deletes it to reset to one row).
    st.subheader("Ingredients")
    if "ingr_row_ids" not in st.session_state:
        st.session_state.ingr_row_ids = [0]
        st.session_state.next_row_id = 1

    pantry_names = sorted(st.session_state.compatible_units, key=str.lower)
    # Widget keys use a row id rather than the row's position, so removing a
    # row doesn't shift the remaining rows' values onto their neighbors.
    rows = []
    for row_id in st.session_state.ingr_row_ids:
        ingr_col, amt_col, units_col, remove_col = st.columns([3, 1, 1, 0.3], vertical_alignment="bottom")
        ingr = ingr_col.selectbox("Ingredient", options=pantry_names, index=None,
                                  placeholder="Type to search", key=f"ingr_{row_id}")
        amt = amt_col.number_input("Amount", min_value=0.0, value=None, step=0.1, key=f"amt_{row_id}")

        unit_options = st.session_state.compatible_units.get(ingr, [])
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

    return rows


def save_recipe(name: str, servings: float | None, servings_amt: float | None,
                servings_units: str | None, rows: list[tuple[str | None, float | None, str | None]]) -> bool:
    # Checks that everything is filled in, then saves the recipe. Returns True if it was saved;
    # otherwise shows an error and returns False, leaving the form as entered.
    header_filled = name and servings and servings_amt and servings_units
    rows_filled = rows and all(ingr and amt and units for ingr, amt, units in rows)
    if not (header_filled and rows_filled):
        st.error("Fill in the recipe name, servings, and every ingredient row (amounts must be more than 0).")
        return False

    ingredients = [Ingredient(ingr_name=ingr, ingredient_amt=amt, ingredient_units=units) for ingr, amt, units in rows]
    try:
        with DataLoader(user=st.session_state.username, pw=st.session_state.pw, db_name=st.session_state.db_name) as loader:
            loader.add_recipe_via_staging(ingredients=ingredients, name=name, servings=servings,
                                          servings_amt=servings_amt, servings_units=servings_units)
    except Exception as e:
        # Covers duplicate recipe names and duplicate ingredient sets
        st.error(f"Could not save recipe: {e}")
        return False
    return True


def clear_form(saved_name: str) -> None:
    # Widget values can't be changed after the widget is drawn in this run,
    # so delete their state and rerun to redraw them empty.
    # Sets st.session_state.saved_recipe_name for show_saved_message on the rerun.
    for key in ["recipe_name", "servings", "servings_amt", "servings_units"]:
        del st.session_state[key]
    for row_id in st.session_state.ingr_row_ids:
        for prefix in ["ingr", "amt", "units"]:
            del st.session_state[f"{prefix}_{row_id}"]
    del st.session_state.ingr_row_ids
    st.session_state.saved_recipe_name = saved_name
    st.rerun()


add_data()
