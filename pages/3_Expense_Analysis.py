"""
Expense Analysis – Upload, column mapping, categories, recurring subscriptions, KPIs.
"""
from pathlib import Path

import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="Expense Analysis | Courser", page_icon="💰", layout="wide")

st.title("Expense Analysis")

# Upload
file = st.file_uploader("Upload expense data (CSV or Excel)", type=["csv", "xlsx", "xls"])
data_dir = Path(__file__).parent.parent / "data"
use_sample = st.checkbox("Use sample expense data", value=False)

def load_expense_df():
    if file is not None:
        if file.name.endswith(".csv"):
            return pd.read_csv(file)
        return pd.read_excel(file)
    if use_sample and (data_dir / "expense_sample.csv").exists():
        return pd.read_csv(data_dir / "expense_sample.csv")
    return None

df_raw = load_expense_df()

if df_raw is not None:
    st.subheader("Column mapping")
    st.caption("Select which columns represent Date, Vendor Name, Expense Amount, and Expense Description.")
    cols = list(df_raw.columns)
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        date_col = st.selectbox("Date", cols, index=min(0, len(cols) - 1), key="ex_date")
    with c2:
        vendor_col = st.selectbox("Vendor Name", cols, index=min(1, len(cols) - 1), key="ex_vendor")
    with c3:
        amount_col = st.selectbox("Expense Amount", [c for c in cols if pd.api.types.is_numeric_dtype(df_raw[c])] or cols, key="ex_amt")
    with c4:
        desc_col = st.selectbox("Expense Description", cols, index=min(3, len(cols) - 1), key="ex_desc")

    df = df_raw.copy()
    df["Date"] = pd.to_datetime(df[date_col], errors="coerce")
    df["Vendor"] = df[vendor_col].astype(str).str.strip()
    df["Amount"] = pd.to_numeric(df[amount_col], errors="coerce").fillna(0)
    df["Description"] = df[desc_col].astype(str)
    df = df.dropna(subset=["Date"])

    # Group expense categories (user can add custom groupings later)
    st.subheader("Group expense categories")
    st.caption("Optionally group vendors into categories. Add mappings below or use vendors as-is.")
    vendors = df["Vendor"].unique().tolist()
    category_map = {}
    with st.expander("Add vendor → category mappings"):
        for i, v in enumerate(vendors[:15]):  # limit UI
            cat = st.text_input(f"Category for: {v[:40]}", value=v, key=f"cat_{i}")
            if cat:
                category_map[v] = cat
    if not category_map:
        category_map = {v: v for v in vendors}
    df["Category"] = df["Vendor"].map(lambda x: category_map.get(x, x))

    # Recurring: same vendor, similar amount month-over-month
    df["Month"] = df["Date"].dt.to_period("M").astype(str)
    monthly = df.groupby(["Vendor", "Month"])["Amount"].sum().reset_index()
    vendor_monthly_avg = monthly.groupby("Vendor")["Amount"].mean().reset_index()
    vendor_monthly_avg.columns = ["Vendor", "AvgMonthly"]
    vendor_total = monthly.groupby("Vendor")["Amount"].sum().reset_index()
    vendor_total.columns = ["Vendor", "Total"]
    recurring = vendor_monthly_avg.merge(vendor_total, on="Vendor")
    # Count months present
    month_counts = monthly.groupby("Vendor")["Month"].count().reset_index()
    month_counts.columns = ["Vendor", "Months"]
    recurring = recurring.merge(month_counts, on="Vendor")
    recurring = recurring[recurring["Months"] >= 2].sort_values("AvgMonthly", ascending=False)
    recurring = recurring.rename(columns={"AvgMonthly": "Total monthly (avg)", "Total": "Total YTD"})

    with st.expander("**Recurring subscriptions** (descending by total monthly expense)", expanded=False):
        st.dataframe(recurring[["Vendor", "Total monthly (avg)", "Total YTD", "Months"]].head(20), use_container_width=True)

    # KPIs
    st.subheader("Key metrics")
    total_spend = df["Amount"].sum()
    by_vendor = df.groupby("Vendor")["Amount"].sum().sort_values(ascending=False)
    top_vendor = by_vendor.index[0] if len(by_vendor) > 0 else "N/A"
    top_vendor_amt = by_vendor.iloc[0] if len(by_vendor) > 0 else 0

    monthly_totals = df.groupby("Month")["Amount"].sum()
    if len(monthly_totals) >= 2:
        mom = monthly_totals.diff()
        mom = mom.dropna()
        if len(mom) > 0:
            largest_mom_increase = mom.max()
            largest_mom_month = mom.idxmax()
        else:
            largest_mom_increase = 0
            largest_mom_month = "N/A"
    else:
        largest_mom_increase = 0
        largest_mom_month = "N/A"

    # New vendors: first appearance per vendor
    first_seen = df.groupby("Vendor")["Date"].min().reset_index()
    first_seen.columns = ["Vendor", "FirstSeen"]
    df_with_first = df.merge(first_seen, on="Vendor")
    df_with_first["IsNew"] = df_with_first["Date"] == df_with_first["FirstSeen"]
    new_vendor_spend = df_with_first[df_with_first["IsNew"]].groupby("Vendor")["Amount"].sum().sort_values(ascending=False)
    top_new_vendor = new_vendor_spend.index[0] if len(new_vendor_spend) > 0 else "N/A"
    top_new_vendor_amt = new_vendor_spend.iloc[0] if len(new_vendor_spend) > 0 else 0

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Top spend (vendor)", top_vendor, f"${top_vendor_amt:,.2f}")
    k2.metric("Largest MoM spend increase", str(largest_mom_month), f"${largest_mom_increase:,.2f}" if pd.notna(largest_mom_increase) else "N/A")
    k3.metric("Top new vendor spend", top_new_vendor, f"${top_new_vendor_amt:,.2f}")
    k4.metric("Total spend YTD", "", f"${total_spend:,.2f}")

    # Trend: monthly vendor spend YTD
    st.subheader("Monthly vendor spend (YTD trend)")
    trend_df = df.groupby("Month")["Amount"].sum().reset_index()
    trend_df["Month"] = pd.to_datetime(trend_df["Month"] + "-01")
    fig = px.line(trend_df, x="Month", y="Amount", title="Total expense by month")
    fig.update_layout(xaxis_title="Month", yaxis_title="Amount ($)")
    st.plotly_chart(fig, use_container_width=True)

    # By-vendor trend (stacked or top N)
    top_n = st.slider("Top N vendors for trend", 3, 15, 5)
    top_vendors_list = by_vendor.head(top_n).index.tolist()
    df_top = df[df["Vendor"].isin(top_vendors_list)]
    pivot = df_top.pivot_table(index="Month", columns="Vendor", values="Amount", aggfunc="sum").fillna(0)
    pivot.index = pd.to_datetime(pivot.index + "-01")
    fig2 = px.area(pivot, title=f"Monthly spend by top {top_n} vendors")
    st.plotly_chart(fig2, use_container_width=True)
else:
    st.info("Upload a CSV or Excel file or use sample data to analyze expenses.")
