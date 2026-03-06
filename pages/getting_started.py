"""
Getting Started – Welcome and navigation overview.
"""
import streamlit as st

st.set_page_config(page_title="Getting Started | Courser", page_icon="🐴", layout="wide")

st.title("Welcome to Courser")
st.markdown(
    "Use the **sidebar** to navigate between:  \n"
    "- **Financial Close** – Accounts reconciliation, close checklist, roadmap, category review, automatching, and adjustments  \n"
    "- **Revenue Forecasting** – Managed IT Services revenue forecast and interpretability  \n"
    "- **Expense Analysis** – Upload, categorize, and analyze expenses  \n"
)
st.info("Select a page from the sidebar to get started.")
