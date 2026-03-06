"""
Financial Close – Accounts reconciliation, checklist, roadmap, category review, automatching, adjustments.
"""
import io
from pathlib import Path
from datetime import datetime

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(page_title="Financial Close | Courser", page_icon="📋", layout="wide")

st.title("Financial Close")

# --- Session state for accounts and checklist ---
if "account_approvals" not in st.session_state:
    st.session_state.account_approvals = {}  # account_id -> {"approved_by": "user", "approved_at": datetime}
if "checklist_approvals" not in st.session_state:
    st.session_state.checklist_approvals = {}  # step_id -> {"approved_by": "user", "approved_at": datetime}
if "adjustments_submitted" not in st.session_state:
    st.session_state.adjustments_submitted = []

# Sample accounts for reconciliation
SAMPLE_ACCOUNTS = [
    {"Account": "1000 - Cash - Operating", "Status": "Open", "Outstanding_Diff": 125.50},
    {"Account": "1100 - Cash - Payroll", "Status": "Open", "Outstanding_Diff": 0.00},
    {"Account": "1200 - Accounts Receivable", "Status": "Open", "Outstanding_Diff": 3400.00},
    {"Account": "2000 - Accounts Payable", "Status": "Closed", "Outstanding_Diff": 0.00},
    {"Account": "2100 - Accrued Expenses", "Status": "Open", "Outstanding_Diff": 89.22},
]
ROADMAP_ITEMS = [
    "Download bank statements",
    "Download credit card transactions",
    "Create T&M invoices and record spend",
    "Review AP invoices and accruals",
    "Reconcile balance sheet accounts",
    "Run trial balance and variance review",
    "Management review and sign-off",
]

# ---------- Section 1: Account reconciliation (collapsible, collapsed) ----------
with st.expander("**Account reconciliation status** (open/closed, outstanding differences)", expanded=False):
    st.caption("Approve an account to mark it closed. Approval is recorded with your user and timestamp.")
    accounts_df = pd.DataFrame(SAMPLE_ACCOUNTS)
    # Apply session state overrides for status and approval info
    display_rows = []
    for i, row in accounts_df.iterrows():
        acc_name = row["Account"]
        status = row["Status"]
        diff = row["Outstanding_Diff"]
        if acc_name in st.session_state.account_approvals:
            rec = st.session_state.account_approvals[acc_name]
            status = "Closed"
            approved_by = rec.get("approved_by", "—")
            approved_at = rec.get("approved_at", "—")
            if isinstance(approved_at, datetime):
                approved_at = approved_at.strftime("%Y-%m-%d %H:%M")
        else:
            approved_by = "—"
            approved_at = "—"
        display_rows.append({
            "Account": acc_name,
            "Status": status,
            "Outstanding Difference": diff,
            "Approved By": approved_by,
            "Approved At": approved_at,
        })
    display_df = pd.DataFrame(display_rows)
    st.dataframe(display_df, use_container_width=True)
    open_accounts = [r["Account"] for r in display_rows if r["Status"] == "Open"]
    account_to_approve = st.selectbox("Approve account (set to Closed)", open_accounts if open_accounts else ["(none open)"], key="approve_acc")
    if st.button("Approve selected account"):
        if account_to_approve and account_to_approve != "(none open)":
            st.session_state.account_approvals[account_to_approve] = {
                "approved_by": "Current User",
                "approved_at": datetime.now(),
            }
            st.rerun()

# ---------- Section 2: Close cycle checklist (collapsible, collapsed) ----------
with st.expander("**Close cycle checklist** (approve with timestamp)", expanded=False):
    checklist_rows = []
    for i, step in enumerate(ROADMAP_ITEMS):
        step_id = f"step_{i}"
        if step_id in st.session_state.checklist_approvals:
            rec = st.session_state.checklist_approvals[step_id]
            approved_at = rec.get("approved_at")
            if isinstance(approved_at, datetime):
                approved_at = approved_at.strftime("%Y-%m-%d %H:%M")
            checklist_rows.append({"Step": f"{i+1}) {step}", "Complete": "Yes", "Approved By": rec.get("approved_by", "—"), "Approved At": approved_at})
        else:
            checklist_rows.append({"Step": f"{i+1}) {step}", "Complete": "No", "Approved By": "—", "Approved At": "—"})
    checklist_df = pd.DataFrame(checklist_rows)
    st.dataframe(checklist_df, use_container_width=True)
    step_to_approve = st.selectbox("Mark step complete", [f"{i+1}) {s}" for i, s in enumerate(ROADMAP_ITEMS)], key="check_step")
    if st.button("Mark selected step complete"):
        idx = next((i for i, s in enumerate(ROADMAP_ITEMS) if step_to_approve.startswith(f"{i+1})")), 0)
        st.session_state.checklist_approvals[f"step_{idx}"] = {"approved_by": "Current User", "approved_at": datetime.now()}
        st.rerun()

# ---------- Section 3: Financial close journey (Mermaid) + roadmap (collapsible, collapsed) ----------
with st.expander("**Close cycle roadmap & journey**", expanded=False):
    mermaid_chart = """
    flowchart LR
        A[Download Bank & CC] --> B[Record Invoices & Spend]
        B --> C[Review AP & Accruals]
        C --> D[Reconcile Balance Sheet]
        D --> E[Trial Balance & Variance]
        E --> F[Management Sign-off]
        F --> G[Close Complete]
    """
    # Render Mermaid via HTML + Mermaid.js CDN
    mermaid_html = f"""
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
    <div class="mermaid">
    {mermaid_chart}
    </div>
    <script>mermaid.initialize({{ startOnLoad: true, theme: 'neutral' }});</script>
    """
    components.html(mermaid_html, height=280)
    st.markdown("**Checklist items:**")
    for i, step in enumerate(ROADMAP_ITEMS):
        st.markdown(f"- {i+1}) {step}")

# ---------- Section 4: Category review – agree or suggest new spend category (collapsible, collapsed) ----------
with st.expander("**Category review** – agree with current category or suggest new spend category", expanded=False):
    # Sample descriptions and current categories
    sample_review = [
        {"Description": "Office Supplies Inc", "Current_Category": "Supplies"},
        {"Description": "Cloud Hosting Co", "Current_Category": "Technology"},
        {"Description": "Payroll - Salaries", "Current_Category": "Payroll"},
        {"Description": "Acme Software License", "Current_Category": "Software"},
        {"Description": "Electric Company", "Current_Category": "Utilities"},
        {"Description": "Vendor ABC Payment", "Current_Category": "Professional Services"},
    ]
    review_df = pd.DataFrame(sample_review)
    # Simple rule-based "suggested" category based on keywords (English)
    def suggest_category(desc):
        d = str(desc).lower()
        if "payroll" in d or "salaries" in d:
            return "Payroll"
        if "cloud" in d or "hosting" in d or "software" in d or "license" in d:
            return "Technology / Software"
        if "supplies" in d or "office" in d:
            return "Supplies"
        if "electric" in d or "utility" in d:
            return "Utilities"
        if "vendor" in d or "consulting" in d or "professional" in d:
            return "Professional Services"
        return "Other"
    review_df["Suggested_Category"] = review_df["Description"].apply(suggest_category)
    review_df["Agree"] = review_df["Current_Category"] == review_df["Suggested_Category"]
    st.dataframe(review_df, use_container_width=True)
    st.caption("Suggested category is based on description text. Use your judgment to agree or reclassify.")

# ---------- Section 5: Automatching (collapsible, collapsed) ----------
with st.expander("**Automatching** – upload two files, match records, export", expanded=False):
    data_dir = Path(__file__).parent.parent / "data"
    file_left = st.file_uploader("File 1 (e.g. bank/GL)", type=["csv", "xlsx", "xls"], key="close_left")
    file_right = st.file_uploader("File 2 (e.g. statements)", type=["csv", "xlsx", "xls"], key="close_right")
    use_sample = st.checkbox("Use sample data (two CSVs for demo)", value=False, key="fc_sample")

    def load_df(uploaded, default_path):
        if uploaded is not None:
            return pd.read_csv(uploaded) if uploaded.name.endswith(".csv") else pd.read_excel(uploaded)
        if use_sample and default_path and default_path.exists():
            return pd.read_csv(default_path)
        return None

    df_left = load_df(file_left, data_dir / "close_sample_left.csv")
    df_right = load_df(file_right, data_dir / "close_sample_right.csv")

    if df_left is not None and df_right is not None:
        def infer_columns(df):
            cols = list(df.columns)
            date_col = next((c for c in cols if "date" in str(c).lower()), cols[0] if cols else None)
            amount_col = next((c for c in cols if c != date_col and pd.api.types.is_numeric_dtype(df[c])), cols[-1] if cols else None)
            desc_col = next(
                (c for c in cols if c not in (date_col, amount_col) and pd.api.types.is_object_dtype(df[c])),
                cols[1] if len(cols) > 1 else None,
            )
            return date_col, desc_col, amount_col

        d_l, desc_l, amt_l = infer_columns(df_left)
        d_r, desc_r, amt_r = infer_columns(df_right)
        amt_l = st.selectbox("File 1 – Amount column", df_left.columns, index=list(df_left.columns).index(amt_l) if amt_l in df_left.columns else 0, key="amt_l")
        desc_l = st.selectbox("File 1 – Description column", df_left.columns, index=list(df_left.columns).index(desc_l) if desc_l in df_left.columns else 0, key="desc_l")
        amt_r = st.selectbox("File 2 – Amount column", df_right.columns, index=list(df_right.columns).index(amt_r) if amt_r in df_right.columns else 0, key="amt_r")
        desc_r = st.selectbox("File 2 – Description column", df_right.columns, index=list(df_right.columns).index(desc_r) if desc_r in df_right.columns else 0, key="desc_r")

        df_left = df_left.copy()
        df_right = df_right.copy()
        df_left["_amount"] = pd.to_numeric(df_left[amt_l], errors="coerce").fillna(0)
        df_right["_amount"] = pd.to_numeric(df_right[amt_r], errors="coerce").fillna(0)
        df_left["_desc"] = df_left[desc_l].astype(str).str.strip().str.lower()
        df_right["_desc"] = df_right[desc_r].astype(str).str.strip().str.lower()

        tolerance_fuzzy = st.slider("Fuzzy amount tolerance", 0.0, 50.0, 5.0, 0.5, key="tol")
        def simple_similarity(a, b):
            if a == b: return 1.0
            if not a or not b: return 0.0
            a, b = a[:50], b[:50]
            return sum(1 for i, c in enumerate(a) if i < len(b) and b[i] == c) / max(len(a), len(b), 1)

        used_left, used_right = set(), set()
        matched_pairs = []
        for i, row_l in df_left.iterrows():
            for j, row_r in df_right.iterrows():
                if j in used_right: continue
                if abs(row_l["_amount"] - row_r["_amount"]) <= 0.01:
                    matched_pairs.append((i, j, "exact", 0.0))
                    used_left.add(i); used_right.add(j)
                    break
        for i, row_l in df_left.iterrows():
            if i in used_left: continue
            for j, row_r in df_right.iterrows():
                if j in used_right: continue
                if abs(row_l["_amount"] - row_r["_amount"]) <= tolerance_fuzzy and simple_similarity(row_l["_desc"], row_r["_desc"]) > 0.3:
                    matched_pairs.append((i, j, "fuzzy", abs(row_l["_amount"] - row_r["_amount"])))
                    used_left.add(i); used_right.add(j)
                    break

        matched_rows = [{"File1_Amount": df_left.loc[i]["_amount"], "File2_Amount": df_right.loc[j]["_amount"], "Amount_Diff": round(df_left.loc[i]["_amount"] - df_right.loc[j]["_amount"], 2), "File1_Description": df_left.loc[i][desc_l], "File2_Description": df_right.loc[j][desc_r], "Match_Type": mt} for i, j, mt, _ in matched_pairs]
        df_matched = pd.DataFrame(matched_rows) if matched_pairs else pd.DataFrame()
        unmatched_left = df_left.loc[[x for x in df_left.index if x not in used_left]]
        unmatched_right = df_right.loc[[x for x in df_right.index if x not in used_right]]
        if not unmatched_left.empty and not unmatched_right.empty:
            df_unmatched = pd.concat([unmatched_left[[desc_l, amt_l]].assign(Source="File 1").rename(columns={desc_l: "Description", amt_l: "Amount"}), unmatched_right[[desc_r, amt_r]].assign(Source="File 2").rename(columns={desc_r: "Description", amt_r: "Amount"})], ignore_index=True)
        elif not unmatched_left.empty:
            df_unmatched = unmatched_left[[desc_l, amt_l]].assign(Source="File 1").rename(columns={desc_l: "Description", amt_l: "Amount"})
        else:
            df_unmatched = unmatched_right[[desc_r, amt_r]].assign(Source="File 2").rename(columns={desc_r: "Description", amt_r: "Amount"}) if not unmatched_right.empty else pd.DataFrame()

        total_left = df_left["_amount"].sum()
        matched_amount = df_matched["File1_Amount"].sum() if not df_matched.empty else 0
        k1, k2, k3 = st.columns(3)
        k1.metric("Matched amount", f"${matched_amount:,.2f}")
        k2.metric("Unmatched (File 1)", f"${unmatched_left['_amount'].sum():,.2f}" if not unmatched_left.empty else "$0")
        k3.metric("Match rate", f"{(matched_amount/total_left*100):.1f}%" if total_left else "N/A")
        st.dataframe(df_matched, use_container_width=True)
        st.dataframe(df_unmatched, use_container_width=True)
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df_matched.to_excel(writer, sheet_name="Matched", index=False)
            df_unmatched.to_excel(writer, sheet_name="Unmatched", index=False)
        buf.seek(0)
        st.download_button("Download matched and unmatched as Excel", data=buf, file_name="close_automatch_export.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="dl_auto")
    else:
        st.info("Upload two files or use sample data.")

# ---------- Section 6: Adjustments (collapsible, collapsed) ----------
with st.expander("**Adjustments** – select account, amount, reason; submit", expanded=False):
    if "adjustments_editor_df" not in st.session_state:
        st.session_state.adjustments_editor_df = pd.DataFrame({"Account": [""], "Adjustment_Amount": [0.0], "Reason": [""]})
    account_options = [r["Account"] for r in SAMPLE_ACCOUNTS]
    editor_df = st.session_state.adjustments_editor_df.copy()
    edited = st.data_editor(
        editor_df,
        column_config={
            "Account": st.column_config.SelectboxColumn("Account", options=account_options, required=True),
            "Adjustment_Amount": st.column_config.NumberColumn("Adjustment Amount", format="%.2f"),
            "Reason": st.column_config.TextColumn("Reason"),
        },
        use_container_width=True,
        num_rows="dynamic",
        key="adj_editor",
    )
    if st.button("Submit adjustment"):
        valid = edited[edited["Account"].astype(str).str.strip() != ""].dropna(how="all")
        if not valid.empty:
            for _, row in valid.iterrows():
                if str(row.get("Account", "")).strip():
                    st.session_state.adjustments_submitted.append({
                        "Account": row["Account"],
                        "Amount": float(row.get("Adjustment_Amount", 0) or 0),
                        "Reason": str(row.get("Reason", "")),
                    })
            st.session_state.adjustments_editor_df = pd.DataFrame({"Account": [""], "Adjustment_Amount": [0.0], "Reason": [""]})
            st.success("Adjustment submitted.")
        else:
            st.warning("Add at least one row with an account selected.")
    if st.session_state.adjustments_submitted:
        st.dataframe(pd.DataFrame(st.session_state.adjustments_submitted), use_container_width=True)
