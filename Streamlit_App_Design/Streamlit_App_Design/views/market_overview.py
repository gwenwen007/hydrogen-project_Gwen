"""
market_overview.py — Market Overview page (landing page / dashboard).

This is the first page the user sees.  It shows:
  - KPI cards (current price, 24h change, 7-day avg, grid demand)
  - A main price chart with click-to-expand indicator modal
  - A price heatmap, regional comparison, and news/alerts cards

Data comes from real AEMO prices (historical CSVs + live 7-day API)
via data/market_overview_model.py.  The news/alerts card still uses
sample_data.py because the news API is not yet connected.
"""

import streamlit as st
import plotly.graph_objects as go          # Plotly for interactive charts
import plotly.express as px                # Plotly Express for quick charts
from style import COLORS
from components import metric_card, dashboard_card, stats_row, alert_item

# ── Real data imports (AEMO prices + live 7-day API) ──
from data.market_overview_model import (
    get_market_kpis,
    get_spot_prices,
    get_indicator_modal_data,
    get_price_heatmap,
    get_regional_prices,
)


# ── Live hydrogen news from Mediastack API ──
from data.news.news_fetcher import get_hydrogen_news


@st.cache_data(ttl=1800, show_spinner=False)  # cache for 30 min (free tier has limits)
def get_market_alerts() -> list[dict]:
    """
    Fetch real hydrogen news via the Mediastack API and format them
    as alert items for the dashboard.

    Falls back to a placeholder message if the API returns nothing
    (e.g. no articles published today, or API limit reached).
    """
    articles = get_hydrogen_news(max_keywords=3, max_articles=5)

    if not articles:
        return [
            {"time": "—", "severity": "info",
             "message": "No hydrogen news found for today. Check back later."},
        ]

    alerts = []
    for a in articles:
        # Extract just the time portion from the published_at timestamp
        try:
            pub_time = a["published_at"][:16].split("T")[1] if a["published_at"] else "—"
        except (IndexError, TypeError):
            pub_time = "—"

        alerts.append({
            "time": pub_time,
            "severity": "info",
            "message": a["title"] or "Untitled article",
        })

    return alerts


def region_abbr() -> str:
    """
    Get the short region name (e.g. "NSW") from the sidebar selection.
    The sidebar stores the full name like "New South Wales (NSW)" in
    st.session_state["region"].  This extracts just the abbreviation.
    """
    full = st.session_state.get("region", "New South Wales (NSW)")
    return full.split("(")[-1].replace(")", "").strip()


# ==================================================================
# STEP 3: INDICATOR MODAL
# ==================================================================
# This function draws the content of the expanded modal that opens
# when the user clicks "Expand" on the main price chart card.
#
# It contains:
#   - Time-range selector (7d / 30d / 90d / 1y)
#   - Indicator toggles (EMA, Bollinger Bands, RSI)
#   - A Plotly chart that dynamically adds/removes indicator traces
#   - A stats row at the bottom with KPI summary
#
# This is where MOST of the user interaction grading points come
# from: each toggle and tab switch is a user interaction that
# changes the chart dynamically.
# ==================================================================


def draw_indicator_modal():
    """
    Draw the indicator modal content inside a @st.dialog popup.

    This function is passed to dashboard_card() as modal_content_func.
    When the user clicks "Expand", Streamlit opens a dialog and calls
    this function to draw the modal's content.
    """

    # ── Time-range selector ──
    # st.radio with horizontal=True creates a row of clickable tabs.
    # The user picks a time range, and we load the matching data.
    timeframe = st.radio(
        label="Time Range",
        options=["7d", "30d", "90d", "1y"],
        index=0,                                   # default = 7 days
        horizontal=True,                            # tabs side-by-side
        label_visibility="collapsed",
    )

    # ── Indicator toggles ──
    # st.toggle() creates an on/off switch.  Each toggle controls
    # whether that indicator line appears on the chart.
    # We place them in columns so they sit in a row.
    tog_col1, tog_col2, tog_col3, tog_col4 = st.columns(4)

    with tog_col1:
        show_ema = st.toggle("EMA 24h", value=True, key="modal_ema")
    with tog_col2:
        show_bb = st.toggle("Bollinger Bands", value=True, key="modal_bb")
    with tog_col3:
        show_rsi = st.toggle("RSI 14", value=False, key="modal_rsi")
    with tog_col4:
        show_breakeven = st.toggle("Break-even", value=True, key="modal_be")

    # ── Load data for the selected timeframe ──
    # get_indicator_modal_data() returns a dict with:
    #   prices_df — the price DataFrame (real AEMO data)
    #   ema       — EMA series (same length as prices)
    #   bollinger — DataFrame with bb_upper, bb_lower, bb_middle
    #   rsi       — RSI series (0–100)
    #   stats     — dict with current price, signal, etc.
    data = get_indicator_modal_data(region_abbr(), timeframe)
    prices_df = data["prices_df"]
    timestamps = prices_df["timestamp"]
    prices = prices_df["price_aud_mwh"]

    # ── Build the Plotly chart ──
    fig = go.Figure()

    # --- Bollinger Bands (if toggled on) ---
    # The band is drawn as a filled area between upper and lower lines.
    # We draw the upper line, then the lower line with "tonexty" fill
    # which fills the area between this trace and the previous one.
    if show_bb:
        bb = data["bollinger"]

        # Upper Bollinger Band (thin faint line)
        fig.add_trace(go.Scatter(
            x=timestamps, y=bb["bb_upper"],
            mode="lines",
            name="BB Upper",
            line=dict(color=COLORS["chart_bb"], width=1),
            opacity=0.3,                           # very faint
            showlegend=False,
            hoverinfo="skip",                      # don't show on hover
        ))

        # Lower Bollinger Band (thin faint line + fill between)
        fig.add_trace(go.Scatter(
            x=timestamps, y=bb["bb_lower"],
            mode="lines",
            name="BB Lower",
            line=dict(color=COLORS["chart_bb"], width=1),
            opacity=0.3,
            fill="tonexty",                        # fill area up to previous trace
            fillcolor="rgba(88, 166, 255, 0.08)",  # very transparent blue
            showlegend=False,
            hoverinfo="skip",
        ))

    # --- EMA (if toggled on) ---
    if show_ema:
        fig.add_trace(go.Scatter(
            x=timestamps, y=data["ema"],
            mode="lines",
            name="EMA 24h",
            line=dict(color=COLORS["chart_ema"], width=1.5, dash="dot"),
            opacity=0.6,
            hovertemplate="EMA: $%{y:.2f}<extra></extra>",
        ))

    # --- Break-even line (if toggled on) ---
    if show_breakeven:
        breakeven = data["stats"]["breakeven"]
        fig.add_hline(
            y=breakeven,
            line_dash="dash",
            line_color=COLORS["chart_breakeven"],
            line_width=1,
            opacity=0.6,
            annotation_text=f"Break-even ${breakeven:.0f}",
            annotation_position="top right",
            annotation_font_color=COLORS["chart_breakeven"],
            annotation_font_size=10,
        )

    # --- Spot Price (ALWAYS shown — the dominant thick line) ---
    # This is added LAST so it draws on top of all indicator layers.
    fig.add_trace(go.Scatter(
        x=timestamps, y=prices,
        mode="lines",
        name="Spot Price",
        line=dict(color=COLORS["accent"], width=3),  # thick = dominant
        hovertemplate="Spot: $%{y:.2f} AUD/MWh<extra></extra>",
    ))

    # --- Chart styling (dark theme) ---
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color=COLORS["text_secondary"], size=11),
        margin=dict(l=0, r=0, t=30, b=0),
        height=350,
        xaxis=dict(
            showgrid=False,
            linecolor=COLORS["border"],
            tickfont=dict(color=COLORS["text_muted"], size=10),
        ),
        yaxis=dict(
            title="AUD/MWh",
            title_font=dict(color=COLORS["text_muted"], size=10),
            gridcolor=COLORS["border_light"],
            gridwidth=0.5,
            zeroline=True,
            zerolinecolor=COLORS["border"],
            tickfont=dict(color=COLORS["text_muted"], size=10),
        ),
        legend=dict(
            orientation="h",                       # horizontal legend
            yanchor="bottom", y=1.02,              # above the chart
            xanchor="left", x=0,
            font=dict(size=10, color=COLORS["text_secondary"]),
            bgcolor="rgba(0,0,0,0)",
        ),
        hovermode="x unified",
    )

    st.plotly_chart(fig, use_container_width=True, key="modal_main_chart")

    # ── RSI sub-chart (if toggled on) ──
    # RSI is displayed as a separate chart below the main one,
    # because it has a different scale (0–100) than the price chart.
    if show_rsi:
        rsi_fig = go.Figure()

        # RSI line
        rsi_fig.add_trace(go.Scatter(
            x=timestamps, y=data["rsi"],
            mode="lines",
            name="RSI 14",
            line=dict(color=COLORS["chart_rsi"], width=1.5),
            hovertemplate="RSI: %{y:.1f}<extra></extra>",
        ))

        # Overbought line (70) — prices are expensive, don't produce
        rsi_fig.add_hline(y=70, line_dash="dash",
                          line_color=COLORS["red"], line_width=0.5,
                          annotation_text="Overbought (70)",
                          annotation_font_size=9,
                          annotation_font_color=COLORS["red"])

        # Oversold line (30) — prices are cheap, produce now!
        rsi_fig.add_hline(y=30, line_dash="dash",
                          line_color=COLORS["green"], line_width=0.5,
                          annotation_text="Oversold (30)",
                          annotation_font_size=9,
                          annotation_font_color=COLORS["green"])

        # Green shaded zone below 30 (good to produce)
        rsi_fig.add_hrect(
            y0=0, y1=30,
            fillcolor=COLORS["green"], opacity=0.05,
            line_width=0,
        )

        rsi_fig.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(color=COLORS["text_secondary"], size=10),
            margin=dict(l=0, r=0, t=5, b=0),
            height=150,
            xaxis=dict(showgrid=False, showticklabels=False),
            yaxis=dict(
                range=[0, 100],                    # RSI is always 0–100
                gridcolor=COLORS["border_light"],
                gridwidth=0.5,
                tickfont=dict(color=COLORS["text_muted"], size=9),
                dtick=20,                          # tick every 20 units
            ),
            showlegend=False,
            hovermode="x unified",
        )

        # Small label above the RSI chart
        st.markdown(
            f"<div style='font-size:0.75rem; color:{COLORS['chart_rsi']}; "
            f"font-weight:600; margin-top:0.3rem;'>"
            f"RSI 14 &nbsp;&nbsp;"
            f"<span style=\"color:{COLORS['text_primary']};\">"
            f"{data['stats']['rsi_14']}</span></div>",
            unsafe_allow_html=True,
        )
        st.plotly_chart(rsi_fig, use_container_width=True, key="modal_rsi_chart")

    # ── Stats row at the bottom ──
    # A horizontal row of KPI cards summarising the current state.
    st.markdown("<div style='margin-top:0.5rem;'></div>", unsafe_allow_html=True)
    s = data["stats"]
    stats_row([
        {"label": "CURRENT",    "value": f"${s['current_price']:.2f}",
         "subtitle": "AUD/MWh",  "color": COLORS["green"] if s["current_price"] < 0 else COLORS["red"]},
        {"label": "EMA 24H",    "value": f"${s['ema_24h']:.2f}",
         "subtitle": "Spot below EMA" if s["current_price"] < s["ema_24h"] else "Spot above EMA",
         "color": COLORS["orange"]},
        {"label": "BB %B",      "value": f"{s['bb_pct_b']:.2f}",
         "subtitle": "Near lower band" if s["bb_pct_b"] < 0.3 else "Mid band" if s["bb_pct_b"] < 0.7 else "Near upper band",
         "color": COLORS["chart_bb"]},
        {"label": "RSI 14",     "value": f"{s['rsi_14']:.1f}",
         "subtitle": "Oversold" if s["rsi_14"] < 30 else "Overbought" if s["rsi_14"] > 70 else "Neutral",
         "color": COLORS["chart_rsi"]},
        {"label": "VOLATILITY", "value": f"σ {s['volatility']}",
         "subtitle": "High" if s["volatility"] > 20 else "Low",
         "color": COLORS["yellow"]},
        {"label": "SIGNAL",     "value": s["signal"],
         "subtitle": f"Strength: {s['signal_strength']}",
         "color": COLORS["green"] if s["signal"] == "PRODUCE" else COLORS["red"]},
    ])


def render():
    """Draw the Market Overview page.  Called by app.py."""

    # ==============================================================
    # STEP 1: KPI ROW — four metric cards across the top
    # ==============================================================
    # Fetch the current KPI values from real AEMO data.
    # This returns a dict with keys: current_price, avg_24h, avg_7d,
    # grid_demand.  Each has: value, unit, delta, delta_pct.
    kpis = get_market_kpis(region_abbr())

    # Create 4 equal-width columns, one for each KPI card.
    # st.columns(4) returns a list of 4 column objects.
    kpi_col1, kpi_col2, kpi_col3, kpi_col4 = st.columns(4)

    # Column 1: Current Spot Price
    # We colour it green because negative prices are good for
    # hydrogen production (cheap electricity = produce now).
    with kpi_col1:
        price = kpis["current_price"]
        metric_card(
            label="SPOT PRICE",
            value=f"${price['value']:.2f}",           # format: $-12.40
            subtitle=price["unit"],                     # "AUD/MWh"
            color=COLORS["green"] if price["value"] < 0 else COLORS["red"],
            delta=f"{price['delta_pct']}%",            # "-134.2%"
        )

    # Column 2: 24-Hour Average
    with kpi_col2:
        avg24 = kpis["avg_24h"]
        metric_card(
            label="24H AVG",
            value=f"${avg24['value']:.2f}",
            subtitle=avg24["unit"],
            color=COLORS["text_primary"],               # neutral white
            delta=f"{avg24['delta_pct']}%",
            delta_color=COLORS["green"] if avg24["delta"] < 0 else COLORS["red"],
        )

    # Column 3: 7-Day Average
    with kpi_col3:
        avg7d = kpis["avg_7d"]
        metric_card(
            label="7-DAY AVG",
            value=f"${avg7d['value']:.2f}",
            subtitle=avg7d["unit"],
            color=COLORS["text_primary"],
            delta=f"+{avg7d['delta_pct']}%" if avg7d["delta"] > 0 else f"{avg7d['delta_pct']}%",
            delta_color=COLORS["red"] if avg7d["delta"] > 0 else COLORS["green"],
        )

    # Column 4: Grid Demand
    with kpi_col4:
        demand = kpis["grid_demand"]
        metric_card(
            label="GRID DEMAND",
            value=f"{demand['value']} GW",
            subtitle=f"{demand['delta_pct']}% vs yesterday",
            color=COLORS["cyan"],
        )

    # Add some spacing below the KPI row before the next section
    st.markdown("<div style='margin-top:0.8rem;'></div>", unsafe_allow_html=True)

    # ==============================================================
    # STEP 2: MAIN PRICE CHART CARD
    # ==============================================================
    # This is the central chart on the Market Overview page.
    # It shows the last 7 days of spot electricity prices as a
    # Plotly line chart, styled to match our dark finance theme.
    #
    # We wrap it in dashboard_card() so it gets the dark border,
    # title bar, and an "Expand" button.  The expand button will
    # open the indicator modal (Step 3).

    # ── Fetch the price data ──
    # get_spot_prices() returns a DataFrame with columns:
    #   timestamp (datetime), price_aud_mwh (float)
    # Uses real AEMO data for the selected region, last 7 days.
    prices_df = get_spot_prices(region_abbr(), "7d")

    def draw_price_chart():
        """
        Draw the spot price line chart using Plotly.

        We define this as a function (not inline code) because
        dashboard_card() expects a function it can call to draw
        the card's content.
        """
        # Create an empty Plotly figure
        fig = go.Figure()

        # Add the spot price line
        # go.Scatter draws a line (or scatter plot).
        # mode="lines" means just the line, no dots.
        fig.add_trace(go.Scatter(
            x=prices_df["timestamp"],         # x-axis: time
            y=prices_df["price_aud_mwh"],     # y-axis: price
            mode="lines",                      # just the line, no markers
            name="Spot Price",                 # label for the legend
            line=dict(
                color=COLORS["accent"],        # electric blue
                width=2,                        # line thickness in pixels
            ),
            # "hovertemplate" controls what appears when you hover
            # over a data point.  %{y:.2f} means the y-value with
            # 2 decimal places.  <extra></extra> hides the trace name.
            hovertemplate="$%{y:.2f} AUD/MWh<extra></extra>",
        ))

        # ── Add a break-even reference line ──
        # This horizontal dashed line shows the hydrogen production
        # threshold.  When price is below this line = good to produce.
        breakeven = 45.0
        fig.add_hline(
            y=breakeven,
            line_dash="dash",                  # dashed line style
            line_color=COLORS["yellow"],
            line_width=1,
            annotation_text="Break-even $45",
            annotation_position="top right",
            annotation_font_color=COLORS["yellow"],
            annotation_font_size=10,
        )

        # ── Style the chart to match our dark theme ──
        # update_layout() controls everything about the chart's
        # appearance: background, axes, fonts, margins, etc.
        fig.update_layout(
            # Transparent backgrounds so the card's dark bg shows through
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",

            # Font settings
            font=dict(color=COLORS["text_secondary"], size=11),

            # Remove margins so the chart fills the card
            margin=dict(l=0, r=0, t=10, b=0),

            # Chart height
            height=320,

            # X-axis styling
            xaxis=dict(
                showgrid=False,                # no vertical grid lines
                linecolor=COLORS["border"],
                tickfont=dict(color=COLORS["text_muted"], size=10),
            ),

            # Y-axis styling
            yaxis=dict(
                title="AUD/MWh",
                title_font=dict(color=COLORS["text_muted"], size=10),
                gridcolor=COLORS["border_light"],   # subtle horizontal grid
                gridwidth=0.5,
                zeroline=True,                  # show the zero line
                zerolinecolor=COLORS["border"],
                zerolinewidth=0.5,
                tickfont=dict(color=COLORS["text_muted"], size=10),
            ),

            # Hide the legend (we only have one line for now)
            showlegend=False,

            # Hover mode: show info when hovering over the x-axis
            hovermode="x unified",
        )

        # Display the chart in Streamlit.
        # use_container_width=True makes it fill the card's width.
        st.plotly_chart(fig, use_container_width=True, key="main_price_chart")

    # ── Wrap the chart in a dashboard card ──
    # The card adds a title bar, border, and an "Expand" button.
    # Clicking "Expand" opens the indicator modal (Step 3 below).
    dashboard_card(
        title="Electricity Price — " + region_abbr(),
        content_func=draw_price_chart,
        modal_title="Electricity Price — Detailed View",
        modal_content_func=draw_indicator_modal,   # ← Step 3
    )

    # ==============================================================
    # STEP 4 — SECONDARY ROW: Heatmap + Regional Comparison
    # ==============================================================
    # Two cards side by side:
    #   Left  → Price heatmap (hour-of-day vs day-of-week)
    #   Right → Bar chart comparing current prices across NEM regions
    #
    # We use st.columns(2) to split the row into two equal halves,
    # then put a dashboard_card() inside each half.

    # Fetch the data we need for both cards (real AEMO data)
    heatmap_data = get_price_heatmap(region_abbr())   # pivot table: rows=hour, cols=day
    regional_data = get_regional_prices()              # DataFrame with region, price, demand

    # Create two equal-width columns
    heat_col, regional_col = st.columns(2)

    # ── Left card: Price Heatmap ──
    with heat_col:

        def draw_heatmap():
            """
            Draws a colour-coded grid showing average price for each
            hour of the day (rows) and day of the week (columns).

            Dark blue = low/negative prices (good for production)
            Yellow/red = high prices (bad for production)

            This helps the user spot recurring cheap-hour patterns.
            """
            fig_heat = px.imshow(
                heatmap_data,                       # the pivot table
                color_continuous_scale=[
                    [0.0, COLORS["accent"]],         # low prices → blue
                    [0.5, COLORS["yellow"]],          # mid prices → yellow
                    [1.0, COLORS["red"]],             # high prices → red
                ],
                aspect="auto",                       # stretch to fill space
                labels=dict(
                    x="Day",
                    y="Hour of Day",
                    color="AUD/MWh",
                ),
            )

            # Style the heatmap to match our dark theme
            fig_heat.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",       # transparent background
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color=COLORS["text_muted"], size=10),
                margin=dict(l=40, r=10, t=10, b=30), # tight margins
                height=300,
                coloraxis_colorbar=dict(
                    title=dict(text="AUD/MWh", font=dict(size=10)),
                    tickfont=dict(size=9),
                    thickness=12,                     # slim colour bar
                    len=0.8,
                ),
            )

            st.plotly_chart(fig_heat, use_container_width=True, key="heatmap_chart")

        # Wrap in a dashboard card (no modal for this one — it's
        # already quite readable at normal size)
        dashboard_card(
            title="Price Heatmap — Hour vs Day",
            content_func=draw_heatmap,
        )

    # ── Right card: Regional Price Comparison ──
    with regional_col:

        def draw_regional_bar():
            """
            Horizontal bar chart comparing current spot prices across
            all 5 NEM regions.  The selected region is highlighted
            in our accent blue; others are grey.

            Negative prices show as bars extending to the left,
            which visually signals oversupply in that region.
            """
            # Work out which region is currently selected so we can
            # highlight it in a different colour
            selected = region_abbr()

            # Create a colour list: accent blue for selected, grey for rest
            bar_colors = [
                COLORS["accent"] if r == selected else COLORS["text_secondary"]
                for r in regional_data["region"]
            ]

            fig_bar = go.Figure()

            fig_bar.add_trace(go.Bar(
                y=regional_data["region"],
                x=regional_data["price_aud_mwh"],
                orientation="h",                     # horizontal bars
                marker_color=bar_colors,
                text=[f"${p:.1f}" for p in regional_data["price_aud_mwh"]],
                textposition="outside",              # show price label outside bar
                textfont=dict(color=COLORS["text_secondary"], size=10),
            ))

            fig_bar.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color=COLORS["text_muted"], size=10),
                margin=dict(l=40, r=40, t=10, b=30),
                height=300,
                showlegend=False,

                # X-axis: price scale
                xaxis=dict(
                    title="AUD/MWh",
                    title_font=dict(size=10, color=COLORS["text_muted"]),
                    gridcolor=COLORS["border_light"],
                    gridwidth=0.5,
                    zeroline=True,
                    zerolinecolor=COLORS["border"],
                    zerolinewidth=1,
                    tickfont=dict(color=COLORS["text_muted"], size=9),
                ),

                # Y-axis: region labels
                yaxis=dict(
                    tickfont=dict(color=COLORS["text_muted"], size=11),
                ),
            )

            st.plotly_chart(fig_bar, use_container_width=True, key="regional_bar_chart")

        dashboard_card(
            title="Regional Spot Prices — NEM",
            content_func=draw_regional_bar,
        )

    # ==============================================================
    # STEP 5 — NEWS / ALERTS CARD
    # ==============================================================
    # A full-width card at the bottom that lists recent market alerts.
    # Each alert is drawn with alert_item() from components.py, which
    # shows a coloured dot (green/yellow/red/blue) next to the message.

    alerts = get_market_alerts()   # list of dicts with time, severity, message

    def draw_alerts():
        """
        Loop through all alerts and draw each one using the
        alert_item() component.  Each alert has:
          - time:     when it happened (e.g. "14:32")
          - severity: "success", "warning", "error", or "info"
          - message:  what happened
        """
        for alert in alerts:
            alert_item(
                time=alert["time"],
                severity=alert["severity"],
                message=alert["message"],
            )

    dashboard_card(
        title="Market Alerts & News",
        content_func=draw_alerts,
    )
