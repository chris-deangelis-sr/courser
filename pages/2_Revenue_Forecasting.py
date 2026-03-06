"""
Revenue Forecasting – Managed IT Services sample data, forecast, and SHAP interpretability.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import LabelEncoder
import shap

from components import render_sidebar_logo

st.set_page_config(page_title="Revenue Forecasting | Courser", page_icon="📈", layout="wide")
render_sidebar_logo()

st.title("Revenue Forecasting")

# Load sample or user data
data_dir = Path(__file__).parent.parent / "data"
sample_path = data_dir / "revenue_sample.csv"
df = None

st.subheader("Data source")
use_sample = st.checkbox("Use sample data (Managed IT Services)", value=True)
if use_sample and sample_path.exists():
    df = pd.read_csv(sample_path)
    df["Date"] = pd.to_datetime(df["Date"])
else:
    uploaded = st.file_uploader("Upload CSV or Excel to refresh forecast", type=["csv", "xlsx", "xls"])
    if uploaded is not None:
        if uploaded.name.endswith(".csv"):
            df = pd.read_csv(uploaded)
        else:
            df = pd.read_excel(uploaded)
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        date_col = st.selectbox("Date column", df.columns, key="rf_date")
        cat_col = st.selectbox("Category column", df.columns, key="rf_cat")
        sub_col = st.selectbox("Subcategory column", df.columns, key="rf_sub")
        amt_col = st.selectbox("Amount column", [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])], key="rf_amt") if df is not None else None
        if amt_col:
            df = df.rename(columns={date_col: "Date", cat_col: "Category", sub_col: "Subcategory", amt_col: "Amount"})
            df = df[["Date", "Category", "Subcategory", "Amount"]].dropna()
    else:
        st.info("Use sample data or upload a file with Date, Category, Subcategory (and Amount).")

if df is not None and len(df) > 0:
    # Ensure categories
    categories = ["Managed Services", "Cloud Services", "Project Revenue", "Product Revenue"]
    if "Category" not in df.columns and "Amount" not in df.columns:
        amt_col = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])][0]
        df = df.rename(columns={amt_col: "Amount"})
    if "Amount" not in df.columns:
        df["Amount"] = np.random.uniform(5000, 50000, len(df))

    st.subheader("Revenue by category (sample / uploaded)")
    by_cat = df.groupby("Category", as_index=False)["Amount"].sum()
    fig_cat = px.bar(by_cat, x="Category", y="Amount", title="Total revenue by category")
    st.plotly_chart(fig_cat, use_container_width=True)

    # Drilldown: subcategories
    if "Subcategory" in df.columns:
        st.subheader("Drilldown: subcategories")
        chosen_cat = st.selectbox("Category", df["Category"].unique(), key="drill_cat")
        sub_df = df[df["Category"] == chosen_cat].groupby("Subcategory", as_index=False)["Amount"].sum()
        st.plotly_chart(px.bar(sub_df, x="Subcategory", y="Amount", title=f"Subcategories under {chosen_cat}"), use_container_width=True)

    # Build features for forecasting: month, category encoded, lag
    df = df.sort_values("Date")
    df["Month"] = df["Date"].dt.to_period("M").astype(str)
    df["MonthNum"] = (df["Date"].dt.year - df["Date"].dt.year.min()) * 12 + df["Date"].dt.month

    # Aggregate to month × category (and optionally subcategory) for training
    agg = df.groupby(["Month", "MonthNum", "Category"], as_index=False)["Amount"].sum()
    le_cat = LabelEncoder()
    agg["CategoryEnc"] = le_cat.fit_transform(agg["Category"])

    # Simple trend + category model for next 6 months and 1 year
    X = agg[["MonthNum", "CategoryEnc"]].values
    y = agg["Amount"].values
    model = GradientBoostingRegressor(n_estimators=50, max_depth=3, random_state=42)
    model.fit(X, y)

    # Forecast: next 6 months and month 12
    last_month = agg["MonthNum"].max()
    future_months = list(range(last_month + 1, last_month + 7))  # 6 months
    future_months += [last_month + 12]  # 1 year
    future_months = sorted(set(future_months))

    forecast_rows = []
    for m in future_months:
        for cat_enc, cat in enumerate(le_cat.classes_):
            pred = model.predict([[m, cat_enc]])[0]
            pred = max(0, pred)
            forecast_rows.append({"MonthNum": m, "Month": f"Month {m}", "Category": cat, "Amount": round(pred, 0)})
    forecast_df = pd.DataFrame(forecast_rows)

    st.subheader("Forecast: next 6 months and 1 year")
    pivot = forecast_df.pivot_table(index="Category", columns="MonthNum", values="Amount", aggfunc="sum").fillna(0)
    st.dataframe(pivot.style.format("${:,.0f}"), use_container_width=True)
    fig_fc = px.bar(forecast_df, x="MonthNum", y="Amount", color="Category", title="Revenue forecast by category", barmode="stack")
    st.plotly_chart(fig_fc, use_container_width=True)

    # SHAP interpretability
    st.subheader("Interpretability: what drives the forecast? (SHAP)")
    explainer = shap.TreeExplainer(model, X)
    shap_vals = explainer.shap_values(X)
    if isinstance(shap_vals, list):
        shap_vals = np.array(shap_vals)
    mean_abs = np.abs(shap_vals).mean(axis=0)
    if mean_abs.ndim > 1:
        mean_abs = mean_abs.mean(axis=0)
    feature_names = ["Month (trend)", "Category"]
    imp_df = pd.DataFrame({"Feature": feature_names[: len(mean_abs)], "Importance": mean_abs})
    imp_df = imp_df.sort_values("Importance", ascending=True).reset_index(drop=True)
    fig_shap = px.bar(imp_df, x="Importance", y="Feature", orientation="h", title="Feature importance (mean |SHAP|)")
    st.plotly_chart(fig_shap, use_container_width=True)
    st.caption("Higher values indicate the feature has more impact on the forecast.")

else:
    st.info("Load sample data or upload a file to see the forecast and interpretability.")
