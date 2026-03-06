"""
Financial Close – Roadmap, automatching, and export.
"""
import io
from pathlib import Path

import pandas as pd
import streamlit as st

from components import render_sidebar_logo

st.set_page_config(page_title="Financial Close | Courser", page_icon="📋", layout="wide")
render_sidebar_logo()

st.title("Financial Close")

# --- Roadmap ---
st.subheader("Close cycle roadmap")
roadmap = [
    "1) Download bank statements",
    "2) Download credit card transactions",
    "3) Create T&M invoices and record spend",
    "4) Review AP invoices and accruals",
    "5) Reconcile balance sheet accounts",
    "6) Run trial balance and variance review",
    "7) Management review and sign-off",
]
cols = st.columns(2)
for i, step in enumerate(roadmap):
    cols[i % 2].markdown(f"- **{step}**")
st.markdown("---")

# --- File upload ---
st.subheader("Automatching: upload two files")
col1, col2 = st.columns(2)
with col1:
    file_left = st.file_uploader("File 1 (e.g. bank/GL)", type=["csv", "xlsx", "xls"], key="close_left")
with col2:
    file_right = st.file_uploader("File 2 (e.g. statements)", type=["csv", "xlsx", "xls"], key="close_right")

# Load sample data option
data_dir = Path(__file__).parent.parent / "data"
use_sample = st.checkbox("Use sample data (two CSVs for demo)", value=False)

def load_df(uploaded, default_path):
    if uploaded is not None:
        if uploaded.name.endswith(".csv"):
            return pd.read_csv(uploaded)
        return pd.read_excel(uploaded)
    if use_sample and default_path and default_path.exists():
        return pd.read_csv(default_path)
    return None

df_left = load_df(file_left, data_dir / "close_sample_left.csv")
df_right = load_df(file_right, data_dir / "close_sample_right.csv")

if df_left is not None and df_right is not None:
    st.caption("Detected columns – ensure each file has date, description, and amount-like columns.")
    with st.expander("Preview File 1"):
        st.dataframe(df_left.head(10), use_container_width=True)
    with st.expander("Preview File 2"):
        st.dataframe(df_right.head(10), use_container_width=True)

    # Infer key columns (first datetime-like, last two: desc + amount)
    def infer_columns(df):
        cols = list(df.columns)
        date_col = None
        for c in cols:
            if pd.api.types.is_datetime64_any_dtype(df[c]) or "date" in str(c).lower():
                date_col = c
                break
        if date_col is None and len(cols) >= 1:
            date_col = cols[0]
        # Amount: numeric column that looks like money
        amount_col = None
        for c in cols:
            if c == date_col:
                continue
            if pd.api.types.is_numeric_dtype(df[c]):
                amount_col = c
                break
        if amount_col is None:
            amount_col = cols[-1] if cols else None
        desc_col = None
        for c in cols:
            if c not in (date_col, amount_col) and (df[c].dtype == object or "desc" in str(c).lower() or "name" in str(c).lower()):
                desc_col = c
                break
        if desc_col is None:
            desc_col = [c for c in cols if c not in (date_col, amount_col)]
            desc_col = desc_col[0] if desc_col else cols[1] if len(cols) > 1 else None
        return date_col, desc_col, amount_col

    d_l, desc_l, amt_l = infer_columns(df_left)
    d_r, desc_r, amt_r = infer_columns(df_right)

    c1, c2, c3 = st.columns(3)
    with c1:
        amt_l = st.selectbox("File 1 – Amount column", df_left.columns, index=df_left.columns.get_loc(amt_l) if amt_l in df_left.columns else 0, key="amt_l")
    with c2:
        desc_l = st.selectbox("File 1 – Description column", df_left.columns, index=df_left.columns.get_loc(desc_l) if desc_l in df_left.columns else 0, key="desc_l")
    with c3:
        amt_r = st.selectbox("File 2 – Amount column", df_right.columns, index=df_right.columns.get_loc(amt_r) if amt_r in df_right.columns else 0, key="amt_r")
    desc_r = st.selectbox("File 2 – Description column", df_right.columns, index=df_right.columns.get_loc(desc_r) if desc_r in df_right.columns else 0, key="desc_r")

    # Normalize amount
    df_left = df_left.copy()
    df_right = df_right.copy()
    df_left["_amount"] = pd.to_numeric(df_left[amt_l], errors="coerce").fillna(0)
    df_right["_amount"] = pd.to_numeric(df_right[amt_r], errors="coerce").fillna(0)
    df_left["_desc"] = df_left[desc_l].astype(str).str.strip().str.lower()
    df_right["_desc"] = df_right[desc_r].astype(str).str.strip().str.lower()

    # Exact match first
    tolerance_exact = 0.01
    tolerance_fuzzy = st.slider("Fuzzy amount tolerance (for near-matches)", 0.0, 50.0, 5.0, 0.5)

    def simple_similarity(a, b):
        if a == b:
            return 1.0
        if not a or not b:
            return 0.0
        a, b = a[:50], b[:50]
        overlap = sum(1 for i, c in enumerate(a) if i < len(b) and b[i] == c)
        return overlap / max(len(a), len(b), 1)

    matched_pairs = []
    used_left = set()
    used_right = set()

    # Exact amount match
    for i, row_l in df_left.iterrows():
        for j, row_r in df_right.iterrows():
            if j in used_right:
                continue
            if abs(row_l["_amount"] - row_r["_amount"]) <= tolerance_exact:
                matched_pairs.append((i, j, "exact", 0.0))
                used_left.add(i)
                used_right.add(j)
                break

    # Fuzzy amount + description
    for i, row_l in df_left.iterrows():
        if i in used_left:
            continue
        for j, row_r in df_right.iterrows():
            if j in used_right:
                continue
            diff = abs(row_l["_amount"] - row_r["_amount"])
            if diff <= tolerance_fuzzy and simple_similarity(row_l["_desc"], row_r["_desc"]) > 0.3:
                matched_pairs.append((i, j, "fuzzy", diff))
                used_left.add(i)
                used_right.add(j)
                break

    # Build matched / unmatched dataframes
    matched_rows = []
    for i, j, match_type, amt_diff in matched_pairs:
        r_l = df_left.loc[i]
        r_r = df_right.loc[j]
        matched_rows.append({
            "File1_Amount": r_l["_amount"],
            "File2_Amount": r_r["_amount"],
            "Amount_Diff": round(r_l["_amount"] - r_r["_amount"], 2),
            "File1_Description": r_l[desc_l],
            "File2_Description": r_r[desc_r],
            "Match_Type": match_type,
        })
    df_matched = pd.DataFrame(matched_rows) if matched_rows else pd.DataFrame()

    unmatched_left = df_left.loc[[x for x in df_left.index if x not in used_left]].copy()
    unmatched_right = df_right.loc[[x for x in df_right.index if x not in used_right]].copy()
    unmatched_left["Source"] = "File 1"
    unmatched_right["Source"] = "File 2"
    if not unmatched_left.empty and not unmatched_right.empty:
        df_unmatched = pd.concat([unmatched_left[[desc_l, amt_l, "Source"]].rename(columns={desc_l: "Description", amt_l: "Amount"}), 
                                  unmatched_right[[desc_r, amt_r, "Source"]].rename(columns={desc_r: "Description", amt_r: "Amount"})], ignore_index=True)
    elif not unmatched_left.empty:
        df_unmatched = unmatched_left[[desc_l, amt_l, "Source"]].rename(columns={desc_l: "Description", amt_l: "Amount"})
    elif not unmatched_right.empty:
        df_unmatched = unmatched_right[[desc_r, amt_r, "Source"]].rename(columns={desc_r: "Description", amt_r: "Amount"})
    else:
        df_unmatched = pd.DataFrame()

    # KPIs
    total_left = df_left["_amount"].sum()
    total_right = df_right["_amount"].sum()
    matched_amount = df_matched["File1_Amount"].sum() if not df_matched.empty else 0
    unmatched_left_amt = unmatched_left["_amount"].sum() if not unmatched_left.empty else 0
    unmatched_right_amt = unmatched_right["_amount"].sum() if not unmatched_right.empty else 0

    st.markdown("---")
    st.subheader("Match KPIs")
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Matched amount", f"${matched_amount:,.2f}")
    k2.metric("Unmatched (File 1)", f"${unmatched_left_amt:,.2f}")
    k3.metric("Unmatched (File 2)", f"${unmatched_right_amt:,.2f}")
    k4.metric("Match rate", f"{(matched_amount / total_left * 100) if total_left else 0:.1f}%" if total_left else "N/A")

    # Largest differences (in matched)
    if not df_matched.empty and "Amount_Diff" in df_matched.columns:
        st.subheader("Largest amount differences (matched pairs)")
        diff_sorted = df_matched.reindex(df_matched["Amount_Diff"].abs().sort_values(ascending=False).index)
        st.dataframe(diff_sorted.head(10), use_container_width=True)

    # Largest unmatched (by amount)
    if not df_unmatched.empty:
        st.subheader("Largest unmatched amounts")
        if "Amount" in df_unmatched.columns:
            um = df_unmatched.copy()
            um["Amount"] = pd.to_numeric(um["Amount"], errors="coerce").fillna(0)
            st.dataframe(um.nlargest(10, "Amount"), use_container_width=True)

    st.subheader("Matched records")
    st.dataframe(df_matched, use_container_width=True)

    st.subheader("Unmatched records")
    st.dataframe(df_unmatched, use_container_width=True)

    # Export
    st.markdown("---")
    st.subheader("Export to Excel")
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df_matched.to_excel(writer, sheet_name="Matched", index=False)
        df_unmatched.to_excel(writer, sheet_name="Unmatched", index=False)
    buf.seek(0)
    st.download_button("Download matched and unmatched as Excel", data=buf, file_name="close_automatch_export.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
else:
    st.info("Upload two files (CSV or Excel) or check 'Use sample data' and click Run to see automatching.")
