# Conventions
- The `webapp` layer should not contain business logic, significant data manipulations, or calculations. If you need a new API in `/src`, ask me to add it rather than hacking a workaround in `webapp`.
  - OK in `webapp`: formatting, sorting for display, choosing which columns to plot.
  - Not OK: summing nutrients, unit conversion, filtering by business rules.

# Structure
- `app.py` is the single Streamlit entry point. It gets data and calculations only from `/src` (currently `ForkDB` and `display_meal_totals`).
