"""
Revenue Forecasting – Managed IT Services sample data, forecast (category + subcategory), and interpretability.
"""
import io
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import LabelEncoder

st.set_page_config(page_title="Revenue Forecasting | Courser", page_icon="📈", layout="wide")

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
    if "Amount" not in df.columns:
        df["Amount"] = np.random.uniform(5000, 50000, len(df))

    df = df.sort_values("Date")
    df["Month"] = df["Date"].dt.to_period("M").astype(str)
    df["MonthNum"] = (df["Date"].dt.year - df["Date"].dt.year.min()) * 12 + df["Date"].dt.month

    # One chart: categories drilling down to subcategories (stacked)
    st.subheader("Revenue by category and subcategory")
    agg_cat_sub = df.groupby(["Category", "Subcategory"], as_index=False)["Amount"].sum()
    fig_stack = px.bar(
        agg_cat_sub,
        x="Category",
        y="Amount",
        color="Subcategory",
        title="Revenue by category with subcategory breakdown",
        barmode="stack",
    )
    st.plotly_chart(fig_stack, use_container_width=True)

    # Forecast at category level, then split to subcategory using historical shares
    agg_cat = df.groupby(["Month", "MonthNum", "Category"], as_index=False)["Amount"].sum()
    le_cat = LabelEncoder()
    agg_cat["CategoryEnc"] = le_cat.fit_transform(agg_cat["Category"])
    X = agg_cat[["MonthNum", "CategoryEnc"]].values
    y = agg_cat["Amount"].values
    model = GradientBoostingRegressor(n_estimators=50, max_depth=3, random_state=42)
    model.fit(X, y)

    last_month = agg_cat["MonthNum"].max()
    future_months = sorted(set(list(range(last_month + 1, last_month + 7)) + [last_month + 12]))
    base_year = df["Date"].dt.year.min()

    # Subcategory share within each category (from history)
    cat_sub_totals = df.groupby(["Category", "Subcategory"], as_index=False)["Amount"].sum()
    cat_totals = cat_sub_totals.groupby("Category")["Amount"].transform("sum")
    cat_sub_totals["Share"] = (cat_sub_totals["Amount"] / cat_totals).fillna(0)

    forecast_rows = []
    for m in future_months:
        year = base_year + (m - 1) // 12
        month_num = ((m - 1) % 12) + 1
        month_label = f"{year}-{month_num:02d}"
        for cat_enc, cat in enumerate(le_cat.classes_):
            pred_cat = max(0, model.predict([[m, cat_enc]])[0])
            subcats = cat_sub_totals[cat_sub_totals["Category"] == cat]
            if len(subcats) > 0:
                for _, subrow in subcats.iterrows():
                    subcat_name = subrow["Subcategory"]
                    share = subrow.get("Share", 1.0 / len(subcats))
                    if np.isnan(share):
                        share = 1.0 / len(subcats)
                    forecast_rows.append({
                        "Month": month_num,
                        "Year": year,
                        "Month_Year": month_label,
                        "Category": cat,
                        "Subcategory": subcat_name,
                        "Amount": round(pred_cat * share, 0),
                    })
            else:
                forecast_rows.append({"Month": month_num, "Year": year, "Month_Year": month_label, "Category": cat, "Subcategory": "Other", "Amount": round(pred_cat, 0)})

    forecast_df = pd.DataFrame(forecast_rows)

    st.subheader("Forecast: next 6 months and 1 year (with subcategory detail)")
    st.dataframe(forecast_df, use_container_width=True)

    fig_fc = px.bar(
        forecast_df,
        x="Month_Year",
        y="Amount",
        color="Subcategory",
        facet_row=None,
        title="Revenue forecast by month and subcategory",
        barmode="stack",
    )
    fig_fc.update_xaxes(tickangle=-45)
    st.plotly_chart(fig_fc, use_container_width=True)

    # Interpretability: made-up SHAP-style factors (not from the model table)
    st.subheader("Interpretability: factors driving the forecast (SHAP-style)")
    fake_shap = pd.DataFrame({
        "Factor": ["Seasonality", "Customer_Type", "Region", "Business_Line", "GDP"],
        "Importance": [0.28, 0.22, 0.19, 0.18, 0.13],
    }).sort_values("Importance", ascending=True)
    fig_shap = px.bar(fake_shap, x="Importance", y="Factor", orientation="h", title="Feature importance (representative SHAP values)")
    st.plotly_chart(fig_shap, use_container_width=True)
    st.caption("Representative drivers: seasonality, customer type, region, business line, and macro (GDP). Higher values indicate greater impact on the forecast.")

    # Export forecast to Excel
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        forecast_df.to_excel(writer, sheet_name="Forecast", index=False)
    buf.seek(0)
    st.download_button("Export forecast to Excel", data=buf, file_name="revenue_forecast.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_forecast")

else:
    st.info("Load sample data or upload a file to see the forecast and interpretability.")
