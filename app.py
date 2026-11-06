"""Streamlit screens for Nova Campus Tycoon (UI only).

This module only renders screens and reacts to clicks. Game rules live in
logic.py, storage lives in db.py.

Run with: uv run streamlit run app.py
"""

import streamlit as st

st.set_page_config(page_title="Nova Campus Tycoon")
st.title("Nova Campus Tycoon")
st.info("Project setup complete. The first feature is described in specs/first-feature.md.")
