"""
Courser – Financial Close, Revenue Forecasting & Expense Analysis
"""
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

pages = [
    st.Page("pages/getting_started.py", title="Getting Started"),
    st.Page("pages/1_Financial_Close.py", title="Financial Close"),
    st.Page("pages/2_Revenue_Forecasting.py", title="Revenue Forecasting"),
    st.Page("pages/3_Expense_Analysis.py", title="Expense Analysis"),
]
pg = st.navigation(pages, position="sidebar")
pg.run()
