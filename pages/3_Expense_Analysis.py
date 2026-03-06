"""
Expense Analysis – Upload, column mapping, categories, recurring spend, KPIs, benchmark by geography.
"""
from pathlib import Path

import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="Expense Analysis | Courser", page_icon="💰", layout="wide")

st.title("Expense Analysis")
st.subheader("Review spend analytics for cost consolidation opportunities and benchmarking")

data_dir = Path(__file__).parent.parent / "data"

# Standard expense categories used in sample data and Step 3
EXPENSE_CATEGORIES = [
    "Technology vendors",
    "Professional fees",
    "Shipping fees",
    "Building lease",
    "Building Maintenance",
    "Office supplies",
]

# Step 1: Import your general ledger full history of accounts payable data
with st.expander("**Step 1: Import your general ledger full history of accounts payable data**", expanded=True):
    file = st.file_uploader("Upload expense data (CSV or Excel)", type=["csv", "xlsx", "xls"])
    use_sample = st.checkbox("Use sample expense data", value=True)
    st.caption("Upload a file or use the sample dataset to explore expense analytics.")

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
    # Step 2: Column mapping to match Excel to the application
    with st.expander("**Step 2: Column mapping to match Excel to the application**", expanded=True):
        st.caption("Select which columns represent Date, Vendor Name, Expense Amount, Expense Description, and optionally City, State, and Category.")
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
        # Optional Category column
        has_category = "Category" in df_raw.columns
        if not has_category and len(cols) >= 5:
            cat_col_select = st.selectbox("Category (optional)", ["(none)"] + cols, key="ex_cat")
            if cat_col_select and cat_col_select != "(none)":
                df_raw = df_raw.rename(columns={cat_col_select: "Category"})
        # Optional City / State mapping if columns exist with different names
        has_geo = "City" in df_raw.columns and "State" in df_raw.columns
        if not has_geo and len(cols) >= 5:
            c5, c6 = st.columns(2)
            with c5:
                city_col = st.selectbox("City (optional)", ["(none)"] + cols, key="ex_city")
            with c6:
                state_col = st.selectbox("State (optional)", ["(none)"] + cols, key="ex_state")
            if city_col and city_col != "(none)":
                df_raw = df_raw.rename(columns={city_col: "City"})
            if state_col and state_col != "(none)":
                df_raw = df_raw.rename(columns={state_col: "State"})

    df = df_raw.copy()
    df["Date"] = pd.to_datetime(df[date_col], errors="coerce")
    df["Vendor"] = df[vendor_col].astype(str).str.strip()
    df["Amount"] = pd.to_numeric(df[amount_col], errors="coerce").fillna(0)
    df["Description"] = df[desc_col].astype(str)
    if "City" not in df.columns:
        df["City"] = ""
    if "State" not in df.columns:
        df["State"] = ""
    df["City"] = df["City"].astype(str).str.strip()
    df["State"] = df["State"].astype(str).str.strip()
    if "Category" not in df.columns:
        df["Category"] = ""
    else:
        df["Category"] = df["Category"].astype(str).str.strip()
    df = df.dropna(subset=["Date"])

    # Step 3: Group expense categories (standard: Technology vendors, Professional fees, Shipping fees, Building lease, Building Maintenance, Office supplies)
    with st.expander("**Step 3: Group expense categories**", expanded=False):
        st.caption("Map each vendor to one of the standard categories. Sample data is pre-mapped.")
        vendors = df["Vendor"].unique().tolist()
        category_map = {}
        for i, v in enumerate(vendors[:20]):
            vendor_cats = df[df["Vendor"] == v]["Category"].dropna().astype(str).str.strip()
            existing = vendor_cats.iloc[0] if len(vendor_cats) > 0 and vendor_cats.iloc[0] else ""
            try:
                default_idx = EXPENSE_CATEGORIES.index(existing) if existing in EXPENSE_CATEGORIES else 0
            except (ValueError, TypeError):
                default_idx = 0
            cat = st.selectbox(f"Category for: {v[:40]}", EXPENSE_CATEGORIES, index=default_idx, key=f"cat_{i}")
            category_map[v] = cat
        df["Category"] = df["Vendor"].map(lambda x: category_map.get(x, x or "Uncategorized"))

    # Step 4: Analyze Key Metrics
    with st.expander("**Step 4: Analyze Key Metrics**", expanded=False):
        total_spend = df["Amount"].sum()
        by_vendor = df.groupby("Vendor")["Amount"].sum().sort_values(ascending=False)
        top_vendor = by_vendor.index[0] if len(by_vendor) > 0 else "N/A"
        top_vendor_amt = by_vendor.iloc[0] if len(by_vendor) > 0 else 0

        df["Month"] = df["Date"].dt.to_period("M").astype(str)
        monthly_totals = df.groupby("Month")["Amount"].sum()
        if len(monthly_totals) >= 2:
            mom = monthly_totals.diff().dropna()
            largest_mom_increase = mom.max() if len(mom) > 0 else 0
            largest_mom_month = mom.idxmax() if len(mom) > 0 else "N/A"
        else:
            largest_mom_increase = 0
            largest_mom_month = "N/A"

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

        st.markdown("**Monthly vendor spend (YTD trend)**")
        trend_df = df.groupby("Month")["Amount"].sum().reset_index()
        trend_df["Month"] = pd.to_datetime(trend_df["Month"] + "-01")
        fig = px.line(trend_df, x="Month", y="Amount", title="Total expense by month")
        fig.update_layout(xaxis_title="Month", yaxis_title="Amount ($)")
        st.plotly_chart(fig, use_container_width=True)

        top_n = st.slider("Top N vendors for trend", 3, 15, 5, key="top_n")
        top_vendors_list = by_vendor.head(top_n).index.tolist()
        df_top = df[df["Vendor"].isin(top_vendors_list)]
        pivot = df_top.pivot_table(index="Month", columns="Vendor", values="Amount", aggfunc="sum").fillna(0)
        pivot.index = pd.to_datetime(pivot.index + "-01")
        fig2 = px.area(pivot, title=f"Monthly spend by top {top_n} vendors")
        st.plotly_chart(fig2, use_container_width=True)

    # Step 5: Review Recurring Spend by Vendor
    with st.expander("**Step 5: Review Recurring Spend by Vendor**", expanded=False):
        monthly = df.groupby(["Vendor", "Month"])["Amount"].sum().reset_index()
        vendor_monthly_avg = monthly.groupby("Vendor")["Amount"].mean().reset_index()
        vendor_monthly_avg.columns = ["Vendor", "AvgMonthly"]
        vendor_total = monthly.groupby("Vendor")["Amount"].sum().reset_index()
        vendor_total.columns = ["Vendor", "Total"]
        recurring = vendor_monthly_avg.merge(vendor_total, on="Vendor")
        month_counts = monthly.groupby("Vendor")["Month"].count().reset_index()
        month_counts.columns = ["Vendor", "Months"]
        recurring = recurring.merge(month_counts, on="Vendor")
        recurring = recurring[recurring["Months"] >= 2].sort_values("AvgMonthly", ascending=False)
        recurring = recurring.rename(columns={"AvgMonthly": "Total monthly (avg)", "Total": "Total YTD"})
        st.caption("Vendors with recurring spend (2+ months), descending by total monthly expense.")
        st.dataframe(recurring[["Vendor", "Total monthly (avg)", "Total YTD", "Months"]].head(20), use_container_width=True)

    # Step 6: Benchmark Spend by Category and Geography
    with st.expander("**Step 6: Benchmark Spend by Category and Geography**", expanded=False):
        if (df["State"].str.strip() != "").any():
            by_cat_region = df.groupby(["Category", "State"], as_index=False)["Amount"].sum()
            benchmark = by_cat_region.groupby("Category")["Amount"].transform("mean")
            by_cat_region["Benchmark_Avg"] = benchmark
            by_cat_region["Diff_$"] = by_cat_region["Amount"] - by_cat_region["Benchmark_Avg"]
            by_cat_region["Diff_%"] = (by_cat_region["Diff_$"] / by_cat_region["Benchmark_Avg"].replace(0, float("nan")) * 100).round(1)
            by_cat_region = by_cat_region.rename(columns={"Amount": "Spend", "Benchmark_Avg": "Category_Avg"})
            by_cat_region = by_cat_region.sort_values(["Category", "Spend"], ascending=[True, False])
            st.caption("Spend by category and state vs. category average. Use $ and % differential to spot regional anomalies.")
            st.dataframe(by_cat_region[["Category", "State", "Spend", "Category_Avg", "Diff_$", "Diff_%"]], use_container_width=True)
            # Optional: show by City if we have multiple cities per state
            if (df["City"].str.strip() != "").any():
                by_cat_city = df[df["City"].str.strip() != ""].groupby(["Category", "City", "State"], as_index=False)["Amount"].sum()
                cat_avg = by_cat_city.groupby("Category")["Amount"].transform("mean")
                by_cat_city["Category_Avg"] = cat_avg
                by_cat_city["Diff_$"] = by_cat_city["Amount"] - by_cat_city["Category_Avg"]
                by_cat_city["Diff_%"] = (by_cat_city["Diff_$"] / by_cat_city["Category_Avg"].replace(0, float("nan")) * 100).round(1)
                by_cat_city = by_cat_city.rename(columns={"Amount": "Spend"}).sort_values(["Category", "Spend"], ascending=[True, False])
                st.markdown("**By city**")
                st.dataframe(by_cat_city[["Category", "City", "State", "Spend", "Category_Avg", "Diff_$", "Diff_%"]], use_container_width=True)
        else:
            st.info("Add City and State to your data (or use sample data) to see benchmark by category and geography.")
else:
    st.info("Complete Step 1: upload a file or use sample expense data to analyze expenses.")
