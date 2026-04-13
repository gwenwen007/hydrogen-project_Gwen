"""
app.py - Main entry point for the H2 Production Optimizer Streamlit app.

CODE VERSION: 2026-04-13-v4 (fixed API params + enhanced diagnostics)

This file sets up:
  1. Page config (title, icon, layout)
  2. Custom CSS injection (dark finance theme)
  3. Sidebar (navigation, region selector, timeframe, API diagnostics)
  4. Top bar (page title + current time)
  5. Page routing (imports and calls the selected view's render())

Run with:
    streamlit run app.py
"""

import streamlit as st
from datetime import datetime, timezone

# Custom styling
from style import inject_css, COLORS


# ==================================================================
# 1. PAGE CONFIG - must be the very first Streamlit command
# ==================================================================
st.set_page_config(
    page_title="H2 Production Optimizer",
    page_icon="\u26a1",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Inject our dark finance CSS (overrides Streamlit default theme)
inject_css()


# ==================================================================
# 2. SIDEBAR - Navigation, Region, Timeframe, API Status
# ==================================================================

with st.sidebar:
    # Logo / app title
    st.markdown(
        f"""
        <div style="text-align:center; padding:1rem 0 0.5rem;">
            <span style="font-size:2rem;">\u26a1</span>
            <h2 style="margin:0.3rem 0 0; color:{COLORS['text_primary']};
                        font-size:1.2rem; font-weight:700;">
                H\u2082 Production Optimizer
            </h2>
            <p style="color:{COLORS['text_muted']}; font-size:0.75rem;
                       margin:0;">
                Group 4.04 &mdash; Not Found
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.divider()

    # Page navigation
    pages = [
        "Market Overview",
        "Price Forecast",
        "Production Optimizer",
        "Cost Analysis",
    ]

    page = st.radio(
        label="Navigate",
        options=pages,
        index=0,
        label_visibility="collapsed",
    )

    st.divider()

    # Region selector
    regions = [
        "New South Wales (NSW)",
        "Victoria (VIC)",
        "Queensland (QLD)",
        "South Australia (SA)",
        "Tasmania (TAS)",
    ]

    selected_region = st.selectbox(
        "NEM Region",
        options=regions,
        index=0,
        key="region",
    )

    # Timeframe selector
    timeframe = st.selectbox(
        "Timeframe",
        options=["24h", "48h", "7d", "30d", "90d", "1y"],
        index=2,  # default = 7d
        key="timeframe",
    )

    st.divider()

    # API status indicator
    st.markdown(
        f"<p style='color:{COLORS['text_muted']}; font-size:0.75rem; "
        f"margin-bottom:0.3rem;'>API STATUS</p>",
        unsafe_allow_html=True,
    )

    # Check live price API
    from data.electricity_prices_loader import load_live_prices

    region_abbr = selected_region.split("(")[-1].replace(")", "").strip()
    live_df = load_live_prices(region_abbr)
    api_error = st.session_state.get("_api_error")

    if not live_df.empty:
        st.markdown(
            f"<span style='color:{COLORS['green']}; font-size:0.8rem;'>"
            f"\u25cf Price API &mdash; Online ({len(live_df)} pts)</span>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"<span style='color:{COLORS['red']}; font-size:0.8rem;'>"
            f"\u25cf Price API &mdash; Offline</span>",
            unsafe_allow_html=True,
        )

    # Carbon API
    st.markdown(
        f"<span style='color:{COLORS['green']}; font-size:0.8rem;'>"
        f"\u25cf Carbon API &mdash; Online</span>",
        unsafe_allow_html=True,
    )

    # API Diagnostics (expandable - for debugging)
    with st.expander("API Diagnostics", expanded=False):
        if api_error:
            st.error(f"Price API: {api_error}")
        elif not live_df.empty:
            st.success(f"Price API: {len(live_df)} hours of live data")
        else:
            st.warning("Price API: No data returned (no error recorded)")

        # Show which params were used on last API call
        params_used = st.session_state.get("_api_params_used")
        if params_used:
            st.caption(f"Params used: {params_used}")
        rows_parsed = st.session_state.get("_api_rows_parsed")
        if rows_parsed is not None:
            st.caption(f"Rows parsed: {rows_parsed}")
        json_keys = st.session_state.get("_api_json_keys")
        if json_keys:
            st.caption(f"JSON keys: {json_keys}")

        # Quick connectivity test button
        if st.button("Test Price API Now", key="test_api"):
            import requests
            try:
                now_utc = datetime.now(timezone.utc)
                from datetime import timedelta
                start_utc = now_utc - timedelta(hours=6)
                resp = requests.get(
                    "https://api.openelectricity.org.au/v4/market/network/NEM",
                    headers={
                        "Authorization": "Bearer oe_DYiKF1FeoE9VzmEPNuzUCV"
                    },
                    params={
                        "interval": "5m",
                        "metrics": "price",
                        "primaryGrouping": "network_region",
                        "dateStart": start_utc.strftime(
                            "%Y-%m-%dT%H:%M:%SZ"
                        ),
                        "dateEnd": now_utc.strftime(
                            "%Y-%m-%dT%H:%M:%SZ"
                        ),
                    },
                    timeout=15,
                )
                st.code(
                    f"Status: {resp.status_code}\n"
                    f"Body (first 500 chars):\n{resp.text[:500]}"
                )
            except Exception as e:
                st.error(f"Request failed: {e}")

        st.divider()

        # News API diagnostics
        news_error = st.session_state.get("_news_error")
        news_status = st.session_state.get("_news_api_status")
        news_preview = st.session_state.get("_news_api_preview")

        if news_error:
            st.warning(f"News API: {news_error}")
        if news_status:
            st.caption(f"News HTTP status: {news_status}")
        if news_preview:
            st.caption(f"News response: {news_preview[:200]}")

        # Quick news test button
        if st.button("Test News API Now", key="test_news"):
            import requests as _req
            try:
                _resp = _req.get(
                    "http://api.mediastack.com/v1/news",
                    params={
                        "access_key": "cfd9b9b3f23e9a769b6725c0f7bc480c",
                        "keywords": "green hydrogen",
                        "languages": "en",
                        "limit": 3,
                    },
                    timeout=10,
                )
                st.code(
                    f"Status: {_resp.status_code}\n"
                    f"Body:\n{_resp.text[:500]}"
                )
            except Exception as e:
                st.error(f"News request failed: {e}")

    # Version stamp
    st.caption("Code: v4 | 2026-04-13")


# ==================================================================
# 3. TOP BAR - Page title + current date/time
# ==================================================================

top_left, top_right = st.columns([3, 1])

with top_left:
    st.markdown(
        f"<h1 style='margin:0; padding:0.2rem 0; font-size:1.6rem; "
        f"color:{COLORS['text_primary']};'>{page}</h1>",
        unsafe_allow_html=True,
    )

with top_right:
    now_str = datetime.now().strftime("%d %b %Y | %H:%M")
    st.markdown(
        f"<p style='text-align:right; color:{COLORS['text_muted']}; "
        f"font-size:0.8rem; padding-top:0.6rem;'>"
        f"{now_str} &nbsp;|&nbsp; {region_abbr}</p>",
        unsafe_allow_html=True,
    )


# ==================================================================
# 4. PAGE ROUTING - render the selected page
# ==================================================================

if page == "Market Overview":
    from views.market_overview import render
    render()

elif page == "Price Forecast":
    from views.price_forecast import render
    render()

elif page == "Production Optimizer":
    from views.production_optimizer import render
    render()

elif page == "Cost Analysis":
    from views.cost_analysis import render
    render()
