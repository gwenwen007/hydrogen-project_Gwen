"""
style.py — Visual styling for the H2 Optimizer app.

This file contains:
  1. COLORS  — a dictionary of all the colours used in the app
  2. inject_css() — a function that injects custom CSS into Streamlit
                    to override its default white/light theme with our
                    dark finance dashboard look

Usage:
    from style import inject_css, COLORS
    inject_css()   # call once at the top of app.py

WHY DO WE NEED THIS?
  Streamlit's built-in dark theme is limited.  To get a proper dark
  finance dashboard (like Interactive Brokers or Swissquote), we need
  to inject our own CSS.  This is standard practice in Streamlit apps
  and is done via st.markdown() with unsafe_allow_html=True.
"""

import streamlit as st


# ── Colour Palette ──────────────────────────────────────────────────
# These are the exact colours from our PowerPoint mockups.
# Use COLORS["accent"] instead of hardcoding "#0066FF" everywhere —
# that way, if we ever change the accent colour, we only change it
# in one place.

COLORS = {
    # Backgrounds (darkest to lightest)
    "bg":             "#0D1117",    # main page background
    "bg_card":        "#161B22",    # card / panel background
    "bg_hover":       "#1C2333",    # card hover state
    "bg_sidebar":     "#0D1117",    # sidebar background

    # Borders
    "border":         "#30363D",    # card borders, dividers
    "border_light":   "#21262D",    # subtle grid lines

    # Accent
    "accent":         "#0066FF",    # electric blue — our single accent colour

    # Text
    "text_primary":   "#E6EDF3",    # main text (headings, values)
    "text_secondary": "#8B949E",    # labels, descriptions
    "text_muted":     "#484F58",    # very subtle text (timestamps, etc.)

    # Status colours (for KPIs, alerts, indicators)
    "green":          "#3FB950",    # positive / produce signal
    "red":            "#F85149",    # negative / warning
    "yellow":         "#D29922",    # caution / break-even
    "cyan":           "#39D2C0",    # informational
    "purple":         "#A371F7",    # RSI indicator
    "orange":         "#F0883E",    # EMA indicator

    # Chart-specific (indicator colours)
    "chart_spot":     "#0066FF",    # spot price (same as accent)
    "chart_ema":      "#F0883E",    # EMA line
    "chart_bb":       "#58A6FF",    # Bollinger Bands
    "chart_rsi":      "#A371F7",    # RSI
    "chart_breakeven":"#D29922",    # break-even threshold
}


def inject_css():
    """
    Inject custom CSS to override Streamlit's default styling.

    Call this once at the top of app.py, right after st.set_page_config().
    It uses st.markdown() with a <style> block to apply CSS globally.

    The CSS below targets Streamlit's internal class names (like
    .stApp, .stSidebar, etc.).  These may change if Streamlit releases
    a major update, but they've been stable for a long time.
    """
    st.markdown(
        f"""
        <style>
        /* ──────────────────────────────────────────────────────────
           GLOBAL: dark background for the entire app
           ────────────────────────────────────────────────────────── */
        .stApp {{
            background-color: {COLORS['bg']};
            color: {COLORS['text_primary']};
        }}

        /* ──────────────────────────────────────────────────────────
           SIDEBAR: dark background, styled text
           ────────────────────────────────────────────────────────── */
        section[data-testid="stSidebar"] {{
            background-color: {COLORS['bg_sidebar']};
            border-right: 1px solid {COLORS['border']};
        }}

        /* Sidebar text colour */
        section[data-testid="stSidebar"] * {{
            color: {COLORS['text_secondary']};
        }}

        /* Sidebar radio buttons — highlight the active page */
        section[data-testid="stSidebar"] div[role="radiogroup"] label[data-checked="true"] {{
            background-color: {COLORS['bg_hover']} !important;
            border-left: 3px solid {COLORS['accent']} !important;
            color: {COLORS['text_primary']} !important;
        }}

        /* Sidebar radio buttons — hover effect */
        section[data-testid="stSidebar"] div[role="radiogroup"] label:hover {{
            background-color: {COLORS['bg_hover']} !important;
        }}

        /* ──────────────────────────────────────────────────────────
           DIVIDERS: subtle dark lines instead of bright grey
           ────────────────────────────────────────────────────────── */
        hr {{
            border-color: {COLORS['border']} !important;
            margin: 0.5rem 0 !important;
        }}

        /* ──────────────────────────────────────────────────────────
           SELECT BOXES & INPUTS: dark styling
           ────────────────────────────────────────────────────────── */
        div[data-baseweb="select"] {{
            background-color: {COLORS['bg_card']};
        }}

        div[data-baseweb="select"] > div {{
            background-color: {COLORS['bg_card']} !important;
            border-color: {COLORS['border']} !important;
            color: {COLORS['text_primary']} !important;
        }}

        input, textarea {{
            background-color: {COLORS['bg_card']} !important;
            color: {COLORS['text_primary']} !important;
            border-color: {COLORS['border']} !important;
        }}

        /* ──────────────────────────────────────────────────────────
           BUTTONS: accent-coloured
           ────────────────────────────────────────────────────────── */
        .stButton > button {{
            background-color: {COLORS['accent']};
            color: white;
            border: none;
            border-radius: 4px;
            padding: 0.4rem 1rem;
            font-weight: 600;
        }}

        .stButton > button:hover {{
            background-color: #0055DD;
            color: white;
        }}

        /* ──────────────────────────────────────────────────────────
           METRIC CARDS: Streamlit's built-in st.metric widget
           Override to match our dark card style
           ────────────────────────────────────────────────────────── */
        div[data-testid="stMetric"] {{
            background-color: {COLORS['bg_card']};
            border: 1px solid {COLORS['border']};
            border-radius: 8px;
            padding: 0.8rem 1rem;
        }}

        div[data-testid="stMetric"] label {{
            color: {COLORS['text_muted']} !important;
            font-size: 0.7rem !important;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        div[data-testid="stMetric"] div[data-testid="stMetricValue"] {{
            color: {COLORS['text_primary']} !important;
            font-size: 1.4rem !important;
            font-weight: 700;
        }}

        /* ──────────────────────────────────────────────────────────
           TABS: dark background with accent underline
           ────────────────────────────────────────────────────────── */
        .stTabs [data-baseweb="tab-list"] {{
            gap: 0;
            background-color: transparent;
        }}

        .stTabs [data-baseweb="tab"] {{
            background-color: transparent;
            color: {COLORS['text_secondary']};
            border: none;
            padding: 0.5rem 1rem;
        }}

        .stTabs [aria-selected="true"] {{
            color: {COLORS['accent']} !important;
            border-bottom: 2px solid {COLORS['accent']} !important;
        }}

        /* ──────────────────────────────────────────────────────────
           SCROLLBAR: thin and dark (looks cleaner)
           ────────────────────────────────────────────────────────── */
        ::-webkit-scrollbar {{
            width: 6px;
            height: 6px;
        }}
        ::-webkit-scrollbar-track {{
            background: {COLORS['bg']};
        }}
        ::-webkit-scrollbar-thumb {{
            background: {COLORS['border']};
            border-radius: 3px;
        }}

        /* ──────────────────────────────────────────────────────────
           EXPANDER: dark styling for st.expander widgets
           ────────────────────────────────────────────────────────── */
        .streamlit-expanderHeader {{
            background-color: {COLORS['bg_card']} !important;
            color: {COLORS['text_primary']} !important;
            border: 1px solid {COLORS['border']};
            border-radius: 8px;
        }}

        /* ──────────────────────────────────────────────────────────
           DIALOG / MODAL: dark background for @st.dialog popups
           ────────────────────────────────────────────────────────── */
        div[data-testid="stModal"] > div {{
            background-color: {COLORS['bg_card']} !important;
            border: 1px solid {COLORS['border']};
            border-radius: 12px;
        }}

        /* ──────────────────────────────────────────────────────────
           PLOTLY CHARTS: transparent background so they blend in
           ────────────────────────────────────────────────────────── */
        .stPlotlyChart {{
            background-color: transparent !important;
        }}

        </style>
        """,
        unsafe_allow_html=True,
    )
