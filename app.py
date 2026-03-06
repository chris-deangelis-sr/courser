"""
Courser – Financial Close, Revenue Forecasting & Expense Analysis
"""
from pathlib import Path

import streamlit as st

from components import render_sidebar_logo

st.set_page_config(
    page_title="Courser",
    page_icon="🐴",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Logo at top of sidebar; page links appear below via st.navigation
render_sidebar_logo()

# Resolve page paths relative to this file so deployment (e.g. Streamlit Cloud) finds them
_app_dir = Path(__file__).resolve().parent
pages = [
    st.Page(str(_app_dir / "pages" / "getting_started.py"), title="Getting Started"),
    st.Page(str(_app_dir / "pages" / "1_Financial_Close.py"), title="Financial Close"),
    st.Page(str(_app_dir / "pages" / "2_Revenue_Forecasting.py"), title="Revenue Forecasting"),
    st.Page(str(_app_dir / "pages" / "3_Expense_Analysis.py"), title="Expense Analysis"),
]
pg = st.navigation(pages, position="sidebar")
pg.run()
