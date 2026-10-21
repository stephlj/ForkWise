# Conventions
- The `webapp` layer should not contain business logic, significant data manipulations, or calculations. If you need a new API in `/src`, ask me to add it rather than hacking a workaround in `webapp`.
  - OK in `webapp`: formatting, sorting for display, choosing which columns to plot.
  - Not OK: summing nutrients, unit conversion, filtering by business rules.
- To reset a widget's value, set it in `st.session_state` (from an `on_click` callback, so it runs before the widget is drawn). Don't `del` it: the server forgets the value but the browser keeps showing it, and `AppTest` can't detect the mismatch because it only sees server state. See `clear_form` in `views/add_data.py`.

# Structure
- `app.py` is the single Streamlit entry point: login, then `st.navigation` over the pages in `views/` (one file per page). Pages get data and calculations only from `/src` (currently `ForkDB`, `DataGetter`, `DataLoader` and `display_meal_totals`).
