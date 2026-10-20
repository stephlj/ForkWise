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
    name, servings, servings_amt, servings_units = recipe_header_inputs()
    ingrs = ingredient_rows()

    save_col, clear_col, _ = st.columns([1, 1, 4])
    clear_col.button("Clear form", on_click=clear_form)
    if not save_col.button("Save recipe", type="primary"):
        return
    # The form keeps everything entered after a save, so a closely related recipe
    # can be added by editing it. Saving again unchanged is rejected by
    # add_recipe_via_staging as a duplicate.
    if save_recipe(name.strip(), servings, servings_amt, servings_units, ingrs):
        st.success(f"Added recipe {name.strip()}.")


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
    # Keeps the list of row ids in st.session_state.ingr_row_ids.
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


def clear_form() -> None:
    # Callback for "Clear form" (runs before the next rerun, so the form is then drawn empty).
    # Sets the header fields' values and st.session_state.ingr_row_ids, which
    # recipe_header_inputs and ingredient_rows read.
    # Values must be set, not deleted: deleting a field's value on the server
    # doesn't tell the browser, which keeps showing the old one.
    st.session_state.recipe_name = ""
    for key in ["servings", "servings_amt", "servings_units"]:
        st.session_state[key] = None
    # A fresh row id makes new ingredient widgets, which start empty. The old rows'
    # values are dropped by Streamlit once their widgets are no longer drawn.
    st.session_state.ingr_row_ids = [st.session_state.next_row_id]
    st.session_state.next_row_id += 1


add_data()
