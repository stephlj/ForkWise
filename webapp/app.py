# app.py
#
# Streamlit entry point: login, then navigation between the pages in pages/.
#
# Written by Claude Code

import streamlit as st
import yaml

from forkwise.utils import CONFIG_PATH, DASHBOARD_TITLE
from forkwise.fork_db import ForkDB

st.set_page_config(page_title=DASHBOARD_TITLE, layout="wide")


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
            # it; each page opens its own short-lived connections, same as
            # the existing CLI scripts, so there's no need to keep one alive
            # for the whole session.
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


if not st.session_state.get("logged_in"):
    login()
else:
    # Pages are files (not functions) so tests can reach them with AppTest.switch_page.
    # Using st.navigation means Streamlit doesn't also auto-list pages/ in the sidebar.
    st.navigation([
        st.Page("pages/dashboard.py", title="Dashboard"),
        st.Page("pages/add_data.py", title="Add data"),
    ]).run()
