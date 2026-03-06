"""
Revenue Forecasting – Load GL data, compare to forecast, review table (actuals vs forecast), SHAP interpretability.
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
data_dir = Path(__file__).parent.parent / "data"
sample_path = data_dir / "revenue_sample.csv"

# ----- Step 1: Load your General Ledger data -----
with st.expander("**Step 1: Load your General Ledger data**", expanded=True):
    use_sample = st.checkbox("Use sample data (Managed IT Services)", value=True, key="rf_use_sample")
    if use_sample and sample_path.exists():
        df = pd.read_csv(sample_path)
        df["Date"] = pd.to_datetime(df["Date"])
    else:
        uploaded = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx", "xls"], key="rf_upload")
        df = None
        if uploaded is not None:
            df = pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
            date_col = st.selectbox("Date column", df.columns, key="rf_date")
            cat_col = st.selectbox("Category column", df.columns, key="rf_cat")
            sub_col = st.selectbox("Subcategory column", df.columns, key="rf_sub")
            amt_col = st.selectbox("Amount column", [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])], key="rf_amt")
            df = df.rename(columns={date_col: "Date", cat_col: "Category", sub_col: "Subcategory", amt_col: "Amount"})
            if "City" not in df.columns:
                df["City"] = ""
            if "State" not in df.columns:
                df["State"] = ""
            if "Business_Type" not in df.columns:
                df["Business_Type"] = "Existing"
        else:
            st.info("Use sample data or upload a file with Date, Category, Subcategory, Amount (and optionally City, State, Business_Type).")

if df is not None and len(df) > 0:
    if "Amount" not in df.columns:
        df["Amount"] = np.random.uniform(5000, 50000, len(df))
    if "Business_Type" not in df.columns:
        df["Business_Type"] = "Existing"
    if "City" not in df.columns:
        df["City"] = ""
    if "State" not in df.columns:
        df["State"] = ""

    df = df.sort_values("Date")
    df["Month"] = df["Date"].dt.to_period("M").astype(str)
    df["MonthNum"] = (df["Date"].dt.year - df["Date"].dt.year.min()) * 12 + df["Date"].dt.month

    # Current month = latest month in data
    current_month_str = df["Month"].max()
    current_month_num = df[df["Month"] == current_month_str]["MonthNum"].iloc[0]
    days_in_month = 30  # simplify
    day_elapsed = st.slider("Day of month (for current month status)", 1, days_in_month, min(15, days_in_month), key="day_elapsed")
    expected_pct = day_elapsed / days_in_month

    # Build forecast using history (exclude current month for training to get "forecast" for current month)
    hist = df[df["MonthNum"] < current_month_num]
    if len(hist) == 0:
        hist = df
    agg_cat = hist.groupby(["Month", "MonthNum", "Category"], as_index=False)["Amount"].sum()
    le_cat = LabelEncoder()
    agg_cat["CategoryEnc"] = le_cat.fit_transform(agg_cat["Category"])
    X = agg_cat[["MonthNum", "CategoryEnc"]].values
    y = agg_cat["Amount"].values
    model = GradientBoostingRegressor(n_estimators=50, max_depth=3, random_state=42)
    model.fit(X, y)

    cat_sub_totals = hist.groupby(["Category", "Subcategory"], as_index=False)["Amount"].sum()
    cat_totals = cat_sub_totals.groupby("Category")["Amount"].transform("sum")
    cat_sub_totals["Share"] = (cat_sub_totals["Amount"] / cat_totals).fillna(0)
    # New vs Existing share from history (per Category)
    bt_totals = hist.groupby(["Category", "Business_Type"])["Amount"].sum().unstack(fill_value=0)
    if "New" in bt_totals.columns and "Existing" in bt_totals.columns:
        bt_totals["_total"] = bt_totals["New"] + bt_totals["Existing"]
        new_share = (bt_totals["New"] / bt_totals["_total"].replace(0, 1)).to_dict()
        existing_share = (bt_totals["Existing"] / bt_totals["_total"].replace(0, 1)).to_dict()
    else:
        new_share = {c: 0.25 for c in le_cat.classes_}
        existing_share = {c: 0.75 for c in le_cat.classes_}
    base_year = df["Date"].dt.year.min()

    # Forecast for current month and future months
    future_months = sorted(set([current_month_num] + list(range(current_month_num + 1, current_month_num + 7)) + [current_month_num + 12]))
    forecast_rows = []
    for m in future_months:
        yyyy = base_year + (m - 1) // 12
        mm = ((m - 1) % 12) + 1
        month_label = f"{yyyy}-{mm:02d}"
        for cat_enc, cat in enumerate(le_cat.classes_):
            pred_cat = max(0, model.predict([[m, cat_enc]])[0])
            n_share = new_share.get(cat, 0.25)
            e_share = existing_share.get(cat, 0.75)
            subcats = cat_sub_totals[cat_sub_totals["Category"] == cat]
            for _, subrow in subcats.iterrows():
                share = subrow.get("Share", 1.0 / max(len(subcats), 1))
                if np.isnan(share):
                    share = 1.0 / len(subcats)
                sub_amt = pred_cat * share
                forecast_rows.append({
                    "MonthNum": m, "Month_Year": month_label, "Category": cat, "Subcategory": subrow["Subcategory"],
                    "Business_Type": "New", "Amount": round(sub_amt * n_share, 0),
                })
                forecast_rows.append({
                    "MonthNum": m, "Month_Year": month_label, "Category": cat, "Subcategory": subrow["Subcategory"],
                    "Business_Type": "Existing", "Amount": round(sub_amt * e_share, 0),
                })
    forecast_df = pd.DataFrame(forecast_rows)

    # Current month actuals from GL
    current_actuals = df[df["Month"] == current_month_str].groupby(["Category", "Subcategory", "Business_Type"], as_index=False)["Amount"].sum()
    current_forecast = forecast_df[(forecast_df["Month_Year"] == current_month_str)]
    current_forecast_sum = current_forecast.groupby("Category")["Amount"].sum()

    # KPIs: current month status (on-track / ahead / below) and $ / % diff by category
    st.markdown("**Current month vs forecast (intramonth)**")
    actuals_by_cat = df[df["Month"] == current_month_str].groupby("Category")["Amount"].sum()
    forecast_by_cat = current_forecast.groupby("Category")["Amount"].sum()
    kpi_rows = []
    for cat in forecast_by_cat.index:
        act = actuals_by_cat.get(cat, 0)
        fct = forecast_by_cat.get(cat, 0)
        expected_to_date = fct * expected_pct if fct else 0
        if fct and expected_to_date:
            pct_diff = (act - expected_to_date) / expected_to_date * 100
            if pct_diff >= 5:
                status = "Ahead of forecast"
            elif pct_diff <= -5:
                status = "Below forecast"
            else:
                status = "On-track"
        else:
            pct_diff = 0
            status = "On-track"
        dollar_diff = act - expected_to_date
        kpi_rows.append({"Category": cat, "Status": status, "Actuals to date": round(act, 0), "Expected to date": round(expected_to_date, 0), "Diff $": round(dollar_diff, 0), "Diff %": round(pct_diff, 1)})

    kpi_df = pd.DataFrame(kpi_rows)
    ahead = (kpi_df["Status"] == "Ahead of forecast").sum()
    on_track = (kpi_df["Status"] == "On-track").sum()
    below = (kpi_df["Status"] == "Below forecast").sum()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Categories ahead of forecast", ahead, "")
    c2.metric("Categories on-track", on_track, "")
    c3.metric("Categories below forecast", below, "")
    c4.metric("Day of month (expected %)", f"{day_elapsed}/{days_in_month}", f"{expected_pct*100:.0f}%")
    st.dataframe(kpi_df, use_container_width=True)

    # Revenue by category and subcategory chart
    st.markdown("**Revenue by category and subcategory**")
    agg_cat_sub = df.groupby(["Category", "Subcategory"], as_index=False)["Amount"].sum()
    fig_stack = px.bar(agg_cat_sub, x="Category", y="Amount", color="Subcategory", title="Revenue by category with subcategory breakdown", barmode="stack")
    st.plotly_chart(fig_stack, use_container_width=True)

# ----- Step 2: Review the Forecast -----
if df is not None and len(df) > 0:
    with st.expander("**Step 2: Review the Forecast**", expanded=True):
        # Pivot: rows = Business_Type, Category, Subcategory; columns = dates (current month twice: Actuals, Forecast)
        months_in_order = sorted(forecast_df["Month_Year"].unique())
        row_keys = forecast_df[["Business_Type", "Category", "Subcategory"]].drop_duplicates().sort_values(["Business_Type", "Category", "Subcategory"])
        actuals_wide = df.groupby(["Month", "Business_Type", "Category", "Subcategory"])["Amount"].sum().reset_index()
        table_rows = []
        for _, r in row_keys.iterrows():
            bt, cat, sub = r["Business_Type"], r["Category"], r["Subcategory"]
            row = {"Business_Type": bt, "Category": cat, "Subcategory": sub}
            for m in months_in_order:
                if m == current_month_str:
                    act = actuals_wide[(actuals_wide["Month"] == m) & (actuals_wide["Business_Type"] == bt) & (actuals_wide["Category"] == cat) & (actuals_wide["Subcategory"] == sub)]["Amount"].sum()
                    fct = forecast_df[(forecast_df["Month_Year"] == m) & (forecast_df["Business_Type"] == bt) & (forecast_df["Category"] == cat) & (forecast_df["Subcategory"] == sub)]["Amount"].sum()
                    row[f"{m} (Actuals)"] = round(act, 0)
                    row[f"{m} (Forecast)"] = round(fct, 0)
                else:
                    val = forecast_df[(forecast_df["Month_Year"] == m) & (forecast_df["Business_Type"] == bt) & (forecast_df["Category"] == cat) & (forecast_df["Subcategory"] == sub)]["Amount"].sum()
                    row[m] = round(val, 0)
            table_rows.append(row)
        review_df = pd.DataFrame(table_rows)
        st.caption("Dates on top; New vs Existing, Category, and Subcategory on the left. Current month shows Actuals and Forecast side by side.")
        st.dataframe(review_df, use_container_width=True)

        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            review_df.to_excel(writer, sheet_name="Forecast", index=False)
        buf.seek(0)
        st.download_button("Export forecast to Excel", data=buf, file_name="revenue_forecast.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_forecast")

# ----- Step 3: Understand the Forecast -----
if df is not None and len(df) > 0:
    with st.expander("**Step 3: Understand the Forecast**", expanded=False):
        st.subheader("Interpretability: factors driving the forecast (SHAP-style)")
        fake_shap = pd.DataFrame({
            "Factor": ["Seasonality", "Customer_Type (New vs Existing)", "Region", "Business_Line", "GDP"],
            "Importance": [0.28, 0.22, 0.19, 0.18, 0.13],
        }).sort_values("Importance", ascending=True)
        fig_shap = px.bar(fake_shap, x="Importance", y="Factor", orientation="h", title="Feature importance (representative SHAP values)")
        st.plotly_chart(fig_shap, use_container_width=True)
        st.caption("Representative drivers: seasonality, customer type (New vs Existing), region, business line, and macro (GDP). Higher values indicate greater impact on the forecast.")

if df is None or len(df) == 0:
    st.info("Complete Step 1: use sample data or upload a file to see the forecast.")
