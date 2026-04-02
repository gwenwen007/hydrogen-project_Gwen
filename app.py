#placeholder <- Entry point (landing page / overview)
import streamlit as st

st.set_page_config(page_title="Hydrogen Optimizer", layout="wide")

st.title("Hydrogen Optimizer")
st.write("Welcome to the hydrogen production optimization dashboard.")

st.markdown("""
Use the sidebar to navigate between:
- Market Overview
- Price Forecast
- Production Optimizer
- Cost Analysis
""")
