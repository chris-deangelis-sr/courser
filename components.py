"""Shared UI components for the Courser Streamlit app."""
from pathlib import Path

import streamlit as st


def render_sidebar_logo():
    """Render the Courser logo at the top of the collapsible sidebar."""
    assets_dir = Path(__file__).parent / "assets"
    logo_path = assets_dir / "logo.png"
    if logo_path.exists():
        st.sidebar.image(str(logo_path), use_container_width=True)
        st.sidebar.markdown("---")
