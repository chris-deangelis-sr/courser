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

render_sidebar_logo()

st.title("Welcome to Courser")
st.markdown(
    "Use the **sidebar** to navigate between:  \n"
    "- **Financial Close** – Close roadmap, file automatching, and export  \n"
    "- **Revenue Forecasting** – Managed IT Services revenue forecast and interpretability  \n"
    "- **Expense Analysis** – Upload, categorize, and analyze expenses  \n"
)
st.info("Select a page from the sidebar to get started.")
