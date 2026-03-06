# Courser

An open-source Streamlit application for financial operations: close management, revenue forecasting, and expense analysis.

## Features

- **Financial Close** – Roadmap for the close cycle, automatching of two files (CSV/Excel), fuzzy matching, KPIs, and export of matched/unmatched data.
- **Revenue Forecasting** – Sample data for a Managed IT Services company (Managed Services, Cloud, Projects, Product), 6-month and 1-year forecasts, optional data refresh via upload with column mapping, and interpretability (SHAP) for the forecast.
- **Expense Analysis** – Upload expenses (CSV/Excel), map columns (Date, Vendor, Amount, Description), group categories, identify recurring subscriptions, and view KPIs (top vendor spend, MoM increase, new vendor spend, YTD trend).

## Setup

```bash
cd courser
pip install -r requirements.txt
streamlit run app.py
```

## Deployment (Streamlit Community Cloud)

1. Push this repository to GitHub.
2. Go to [share.streamlit.io](https://share.streamlit.io), sign in with GitHub, and deploy.
3. Select this repo and set the main file to `app.py`.

## License

MIT
