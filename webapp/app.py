# app.py
#
# Streamlit entry point: login, then navigation between the pages in pages/.
#
# Written by Claude Code

import streamlit as st
import yaml

from forkwise.data_getter import DataGetter
from forkwise.utils import CONFIG_PATH, DASHBOARD_TITLE

st.set_page_config(page_title=DASHBOARD_TITLE, layout="wide")


def login() -> None:
    # Sets st.session_state.logged_in, username, pw, db_name and targets, which the pages read.
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
        # Open a connection just to check the credentials. Each page opens its own
        # short-lived connections on each run rather than keeping one open all session.
        with DataGetter(user=username, pw=pw, db_name=config["db"]["db_name"]):
            pass
    except Exception as e:
        st.error(f"Could not connect: {e}")
        return

    st.session_state.logged_in = True
    st.session_state.username = username
    st.session_state.pw = pw
    # Config is read once here, rather than on every rerun of a page
    st.session_state.db_name = config["db"]["db_name"]
    st.session_state.targets = config.get("targets", {})
    # Without this, the pages wouldn't render until some other widget
    # interaction triggered a second run: setting session_state here doesn't
    # retroactively change which branch this run took.
    st.rerun()


if not st.session_state.get("logged_in"):
    login()
else:
    # Pages are files (not functions) so tests can reach them with AppTest.switch_page.
    # Using st.navigation means Streamlit doesn't also auto-list pages/ in the sidebar.
    st.navigation([
        st.Page("pages/dashboard.py", title="Dashboard"),
        st.Page("pages/add_data.py", title="Add recipes"),
    ]).run()
