"""
app.py — Main entry point for the H2 Optimizer Streamlit application.

This is the file you run with:  streamlit run app.py

It does three things:
  1. Configures the page (dark theme, wide layout, title)
  2. Builds the sidebar (navigation, region selector, timeframe, status)
  3. Routes to the correct page based on the user's sidebar selection

All visual styling is handled by style.py (imported below).
All reusable UI components live in components.py.
Each page has its own file in the pages/ folder.
"""

# ── Imports ──────────────────────────────────────────────────────────
# Streamlit is the web framework that turns this Python script into
# an interactive web app.  Every Streamlit function starts with "st."
import streamlit as st
from datetime import datetime

# Our own files (same folder):
from style import inject_css, COLORS          # visual styling
# from components import top_bar              # uncomment once components.py is built

# Page modules — each file contains a render() function that draws
# one full page.  We import them here so we can call the right one
# based on which sidebar link the user clicked.
# NOTE: the folder is called "views" (not "pages") because Streamlit
# auto-detects a folder named "pages" and tries to use its own
# multi-page system, which conflicts with our manual routing.
from views import market_overview
from views import price_forecast
from views import production_optimizer
from views import cost_analysis


# ── 1. Page Configuration ───────────────────────────────────────────
# This MUST be the very first Streamlit command in the script.
# If you put any other st.* call before this, Streamlit will crash.
st.set_page_config(
    page_title="H2 Optimizer",           # text shown in the browser tab
    layout="wide",                        # use the full width of the screen
    initial_sidebar_state="expanded",     # sidebar open by default
)


# ── 2. Inject Custom CSS ────────────────────────────────────────────
# Streamlit's default look is white/light.  We override it with our
# dark finance theme by injecting CSS.  See style.py for details.
inject_css()


# ── 3. Sidebar ──────────────────────────────────────────────────────
# The sidebar is the dark panel on the left side of the screen.
# It contains: the app logo/title, navigation links, filters, and
# a status indicator.

with st.sidebar:

    # ── Logo & Title ──
    # st.markdown() lets us write HTML directly.  We use it here to
    # style the app name with our accent colour.
    st.markdown(
        f"""
        <div style="padding: 0.5rem 0 1.2rem 0;">
            <span style="font-size: 1.5rem; font-weight: 700; color: {COLORS['accent']};">
                H2 Optimizer
            </span>
            <br>
            <span style="font-size: 0.75rem; color: {COLORS['text_secondary']};">
                Green Hydrogen Production Dashboard
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Divider line ──
    st.divider()

    # ── Navigation ──
    # st.radio creates a set of clickable options.  The user picks one,
    # and we store their choice in the variable "page".
    # Later (section 4) we use "page" to decide which page to show.
    page = st.radio(
        label="Navigate",                                    # label for screen readers
        options=[
            "Market Overview",
            "Price Forecast",
            "Production Optimizer",
            "Cost Analysis",
        ],
        index=0,                                              # default = first option
        label_visibility="collapsed",                         # hide the label visually
    )

    # ── Divider line ──
    st.divider()

    # ── Region Selector ──
    # The Australian NEM has 5 regions.  The user picks which one
    # they want to see data for.  This value is stored in
    # st.session_state so every page can access it.
    st.markdown(
        f"<span style='font-size:0.7rem; color:{COLORS['text_muted']}; "
        f"letter-spacing:0.08em;'>REGION</span>",
        unsafe_allow_html=True,
    )
    region = st.selectbox(
        label="Region",
        options=["New South Wales (NSW)", "Victoria (VIC)", "Queensland (QLD)",
                 "South Australia (SA)", "Tasmania (TAS)"],
        index=0,                                              # default = NSW
        label_visibility="collapsed",
    )
    # Save to session state so other pages can read it
    st.session_state["region"] = region

    # ── Timeframe Selector ──
    # Quick toggle for the default chart timeframe across all pages.
    st.markdown(
        f"<span style='font-size:0.7rem; color:{COLORS['text_muted']}; "
        f"letter-spacing:0.08em;'>TIMEFRAME</span>",
        unsafe_allow_html=True,
    )
    timeframe = st.radio(
        label="Timeframe",
        options=["24h", "48h", "7d", "30d"],
        index=2,                                              # default = 7d
        horizontal=True,                                      # show side-by-side
        label_visibility="collapsed",
    )
    st.session_state["timeframe"] = timeframe

    # ── Spacer ──
    # Push the status indicator to the bottom of the sidebar.
    # We add some vertical space with empty markdown lines.
    st.markdown("<br>" * 4, unsafe_allow_html=True)

    # ── API Status Indicator ──
    # Shows whether the data connection is live or using sample data.
    # For now it always shows "Sample Data" since we haven't connected
    # the real APIs yet.  Change this once the API team is done.
    using_live_api = False  # ← flip to True when real APIs are connected

    if using_live_api:
        status_color = COLORS["green"]
        status_text = "API Connected"
    else:
        status_color = COLORS["yellow"]
        status_text = "Sample Data"

    st.markdown(
        f"""
        <div style="display:flex; align-items:center; gap:0.4rem;
                    padding:0.4rem 0;">
            <span style="width:8px; height:8px; border-radius:50%;
                         background:{status_color}; display:inline-block;">
            </span>
            <span style="font-size:0.75rem; color:{COLORS['text_secondary']};">
                {status_text}
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )


# ── 4. Top Bar ──────────────────────────────────────────────────────
# A thin bar at the top of the main content area showing the page
# title, current date/time, and the selected region.

# We use st.columns() to split the top bar into left and right parts.
top_left, top_right = st.columns([3, 1])

with top_left:
    # Page title — large heading
    st.markdown(
        f"<h1 style='margin:0; padding:0.2rem 0; font-size:1.6rem; "
        f"color:{COLORS['text_primary']};'>{page}</h1>",
        unsafe_allow_html=True,
    )

with top_right:
    # Current date, NEM region abbreviation
    now = datetime.now().strftime("%d %b %Y")
    # Extract the abbreviation from parentheses, e.g. "New South Wales (NSW)" → "NSW"
    region_abbr = region.split("(")[-1].replace(")", "").strip()
    st.markdown(
        f"<div style='text-align:right; padding-top:0.5rem; "
        f"font-size:0.8rem; color:{COLORS['text_secondary']};'>"
        f"{now} &nbsp;|&nbsp; AEMO NEM &nbsp;|&nbsp; {region_abbr}"
        f"</div>",
        unsafe_allow_html=True,
    )

# Thin divider below the top bar
st.divider()


# ── 5. Page Routing ─────────────────────────────────────────────────
# Based on which sidebar option the user selected, we call the
# corresponding page's render() function.  Each page file lives in
# the pages/ folder and contains a single render() function that
# draws all the content for that page.

if page == "Market Overview":
    market_overview.render()

elif page == "Price Forecast":
    price_forecast.render()

elif page == "Production Optimizer":
    production_optimizer.render()

elif page == "Cost Analysis":
    cost_analysis.render()
