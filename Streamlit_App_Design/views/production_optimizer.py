"""
production_optimizer.py — Production Optimizer page.

This is the core "hydrogen" page.  It lets the user:
  1. Set electrolyser parameters (capacity, break-even price, window)
  2. See an optimal production schedule — green = produce, red = hold
  3. View cost summary KPIs (total cost, H₂ output, cost per kg)
  4. Compare "Optimised" vs "Naive 24/7" production strategies

The optimizer logic is simple: for each hour, if the forecasted
electricity price is below the user's break-even threshold → produce.
Otherwise → hold.  The front-end visualises the result.

Data sources:
  - Real AEMO prices: data/electricity_prices_loader.py
  - ML forecast:      data/price_forecast_model.py (LinearRegression)
  - Combined in:      data/production_optimizer_model.py
"""

import streamlit as st
import plotly.graph_objects as go              # Plotly for interactive charts
from style import COLORS
from components import metric_card, dashboard_card, stats_row

# ── Real data imports (no more sample_data.py!) ──
# get_electrolyser_defaults() → dict with default slider values
# get_optimised_schedule()    → DataFrame using real AEMO prices + ML forecast
# get_optimizer_summary()     → dict comparing optimised vs naive strategy
from data.production_optimizer_model import (
    get_electrolyser_defaults,
    get_optimised_schedule,
    get_optimizer_summary,
)


def render():
    """Draw the Production Optimizer page.  Called by app.py."""

    # ==============================================================
    # STEP 1: INPUT CONTROLS
    # ==============================================================
    # Three interactive controls that let the user tweak the
    # electrolyser settings.  Every change re-runs the schedule
    # calculation and updates the entire page.
    #
    # Each control = a user interaction for grading.

    # ── Get the selected region from the sidebar ──
    # The sidebar stores e.g. "New South Wales (NSW)" in session state.
    # We extract just "NSW" to pass to the data functions.
    full_region = st.session_state.get("region", "New South Wales (NSW)")
    region_short = full_region.split("(")[-1].replace(")", "").strip()

    # Load default values for the sliders / inputs.
    # This keeps the defaults in one place so the team can adjust
    # them later without touching front-end code.
    defaults = get_electrolyser_defaults()

    # ── Layout: three columns for the controls ──
    ctrl1, ctrl2, ctrl3 = st.columns(3)

    with ctrl1:
        # Electrolyser capacity slider (in MW).
        # Bigger capacity = more H₂ per hour, but higher electricity cost.
        capacity_mw = st.slider(
            label="Electrolyser Capacity (MW)",
            min_value=defaults["capacity_range"][0],    # 1 MW
            max_value=defaults["capacity_range"][1],    # 50 MW
            value=defaults["capacity_mw"],               # default: 10 MW
            step=1,
            key="optimizer_capacity",
            help="Size of the electrolyser in megawatts. "
                 "Larger = more hydrogen per hour.",
        )

    with ctrl2:
        # Break-even electricity price (AUD/MWh).
        # If the spot price is BELOW this → produce (it's profitable).
        # If the spot price is ABOVE this → hold (too expensive).
        breakeven = st.number_input(
            label="Break-even Price (AUD/MWh)",
            min_value=defaults["breakeven_range"][0],   # 10.0
            max_value=defaults["breakeven_range"][1],   # 120.0
            value=defaults["breakeven_price"],           # default: 45.0
            step=5.0,
            key="optimizer_breakeven",
            help="Maximum electricity price at which hydrogen "
                 "production is still profitable.",
        )

    with ctrl3:
        # Production window — how many hours to plan ahead.
        # "48 h" = 2 days, "7 days" = full week
        window_label = st.radio(
            label="Planning Window",
            options=["48 h", "7 days"],
            index=1,                                     # default: 7 days
            horizontal=True,
            key="optimizer_window",
            help="How far ahead to plan the production schedule.",
        )

        # Convert label to hours: "48 h" → 48, "7 days" → 168
        horizon = 48 if window_label == "48 h" else 168

    # Small spacing between controls and content
    st.markdown("<div style='margin-top:0.8rem;'></div>", unsafe_allow_html=True)

    # ── Fetch optimised schedule and summary with user's settings ──
    # These functions now use REAL AEMO prices + ML forecast for the
    # selected region.  The slider values are passed through.
    schedule = get_optimised_schedule(
        region_abbr=region_short,
        breakeven=breakeven,
        capacity_mw=capacity_mw,
        horizon_hours=horizon,
    )
    summary = get_optimizer_summary(
        region_abbr=region_short,
        breakeven=breakeven,
        capacity_mw=capacity_mw,
    )

    # Shortcuts to the optimised and naive sub-dicts
    opt = summary["optimised"]
    naive = summary["naive"]
    savings = summary["savings"]

    # ==============================================================
    # STEP 2: KPI SUMMARY ROW
    # ==============================================================
    # Four metric cards showing the key outcomes of the optimised
    # schedule.  All values update dynamically when the user moves
    # the sliders above.

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)

    with kpi1:
        # Production hours — how many of the total hours the
        # electrolyser is actually running
        metric_card(
            label="PRODUCTION HOURS",
            value=f"{opt['production_hours']}h",
            subtitle=f"of {naive['production_hours']}h total",
            color=COLORS["accent"],
        )

    with kpi2:
        # Total H₂ output in kilograms
        metric_card(
            label="H₂ OUTPUT",
            value=f"{opt['total_h2_kg']:,.0f} kg",
            subtitle=f"vs {naive['total_h2_kg']:,.0f} kg naive",
            color=COLORS["green"],
        )

    with kpi3:
        # Total electricity cost
        # Colour green if negative (we're being PAID to consume),
        # otherwise use the default text colour
        cost_color = COLORS["green"] if opt["total_cost_aud"] < 0 else COLORS["text_primary"]
        metric_card(
            label="TOTAL COST",
            value=f"${opt['total_cost_aud']:,.0f}",
            subtitle="AUD electricity cost",
            color=cost_color,
        )

    with kpi4:
        # Cost per kg of H₂ — the bottom-line efficiency metric
        metric_card(
            label="COST PER KG",
            value=f"${opt['cost_per_kg']:.2f}",
            subtitle=f"vs ${naive['cost_per_kg']:.2f} naive",
            color=COLORS["green"] if opt["cost_per_kg"] < naive["cost_per_kg"] else COLORS["red"],
        )

    # Small spacing below KPI row
    st.markdown("<div style='margin-top:0.8rem;'></div>", unsafe_allow_html=True)

    # ==============================================================
    # STEP 3: OPTIMAL SCHEDULE CHART
    # ==============================================================
    # This is the centrepiece of the page — a bar chart where each
    # bar represents one hour.  The bar height = the electricity
    # price in that hour.  The bar colour tells the user what to do:
    #
    #   GREEN  → price is below break-even → PRODUCE hydrogen
    #   RED    → price is above break-even → HOLD (don't produce)
    #
    # A horizontal dashed line marks the break-even threshold so the
    # user can see exactly where the cut-off is.
    #
    # When the user moves the break-even slider (Step 1), more or
    # fewer bars turn green — the chart updates in real time.

    def draw_schedule_chart():
        """
        Draw the production schedule bar chart inside a dashboard_card.

        Each bar = one hour.  Colour-coded:
          - Green if the price is below break-even (produce)
          - Red   if the price is at or above break-even (hold)

        A dashed horizontal line shows the break-even threshold.
        """

        # ── Prepare the colour list ──
        # We loop through each row of the schedule DataFrame and
        # assign green or red based on the "produce" boolean column.
        bar_colors = [
            COLORS["green"] if produce else COLORS["red"]
            for produce in schedule["produce"]
        ]

        # ── Create the bar chart ──
        fig = go.Figure()

        # One bar per hour, coloured by produce/hold decision
        fig.add_trace(go.Bar(
            x=schedule["timestamp"],               # hourly timestamps on x-axis
            y=schedule["price_aud_mwh"],           # price on y-axis (bar height)
            marker_color=bar_colors,               # green = produce, red = hold
            opacity=0.8,                           # slightly transparent
            name="Hourly Price",

            # Custom hover text showing full details for each hour
            hovertemplate=(
                "<b>%{x|%a %d %b, %H:%M}</b><br>"     # e.g. "Mon 31 Mar, 14:00"
                "Price: $%{y:.2f} AUD/MWh<br>"         # the electricity price
                "<extra></extra>"                      # hides the trace name box
            ),
        ))

        # ── Break-even threshold line ──
        # A horizontal dashed line so the user can visually see where
        # green stops and red starts.  We draw this manually with
        # go.Scatter instead of fig.add_hline to avoid the same
        # Plotly compatibility issue we hit on the forecast page.
        fig.add_trace(go.Scatter(
            x=[schedule["timestamp"].iloc[0],          # start of x range
               schedule["timestamp"].iloc[-1]],        # end of x range
            y=[breakeven, breakeven],                  # flat horizontal line
            mode="lines",
            line=dict(
                color=COLORS["yellow"],                # yellow stands out
                width=1.5,
                dash="dash",                           # dashed line
            ),
            name=f"Break-even (${breakeven:.0f})",     # legend label
            hoverinfo="skip",                          # don't clutter the hover
        ))

        # ── Chart styling (dark theme) ──
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",             # transparent background
            plot_bgcolor="rgba(0,0,0,0)",              # transparent plot area
            font=dict(color=COLORS["text_muted"], size=11),
            margin=dict(l=50, r=20, t=30, b=40),      # tight margins
            height=360,                                # chart height in pixels
            bargap=0.05,                               # thin gaps between bars

            # X-axis: timestamps
            xaxis=dict(
                showgrid=False,                        # no vertical grid lines
                linecolor=COLORS["border"],            # subtle axis line
                tickfont=dict(color=COLORS["text_muted"], size=10),
            ),

            # Y-axis: price in AUD/MWh
            yaxis=dict(
                title="AUD/MWh",                       # axis label
                title_font=dict(color=COLORS["text_muted"], size=10),
                gridcolor=COLORS["border_light"],      # subtle horizontal grid
                gridwidth=0.5,
                zeroline=True,                         # show the zero line
                zerolinecolor=COLORS["border"],        # (prices can be negative)
                zerolinewidth=0.5,
                tickfont=dict(color=COLORS["text_muted"], size=10),
            ),

            # Legend at the top so it doesn't overlap the bars
            legend=dict(
                orientation="h",                       # horizontal legend
                yanchor="bottom",
                y=1.02,                                # above the chart
                xanchor="left",
                x=0,
                font=dict(size=10),
            ),

            hovermode="x unified",                     # hover follows x-axis
        )

        # Render the chart in Streamlit
        st.plotly_chart(fig, width="stretch", key="schedule_chart")

    # ── Modal for the schedule chart ──
    # When the user clicks "Expand", they get a larger version of
    # the chart plus a summary stats row at the bottom.
    def draw_schedule_modal():
        """
        Draw the expanded schedule modal content.
        Shows the same chart at a larger size plus a stats summary.
        """

        # ── Larger version of the schedule chart ──
        # (Same logic as draw_schedule_chart but taller)
        bar_colors_modal = [
            COLORS["green"] if produce else COLORS["red"]
            for produce in schedule["produce"]
        ]

        fig_modal = go.Figure()

        # Hourly price bars — green (produce) or red (hold)
        fig_modal.add_trace(go.Bar(
            x=schedule["timestamp"],
            y=schedule["price_aud_mwh"],
            marker_color=bar_colors_modal,
            opacity=0.8,
            name="Hourly Price",
            hovertemplate=(
                "<b>%{x|%a %d %b, %H:%M}</b><br>"
                "Price: $%{y:.2f} AUD/MWh<br>"
                "<extra></extra>"
            ),
        ))

        # Break-even threshold line
        fig_modal.add_trace(go.Scatter(
            x=[schedule["timestamp"].iloc[0],
               schedule["timestamp"].iloc[-1]],
            y=[breakeven, breakeven],
            mode="lines",
            line=dict(color=COLORS["yellow"], width=1.5, dash="dash"),
            name=f"Break-even (${breakeven:.0f})",
            hoverinfo="skip",
        ))

        # Dark-themed layout — same as main chart but taller
        fig_modal.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=COLORS["text_muted"], size=11),
            margin=dict(l=50, r=20, t=30, b=40),
            height=420,                                # taller in modal
            bargap=0.05,
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
                zerolinewidth=0.5,
                tickfont=dict(color=COLORS["text_muted"], size=10),
            ),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02,
                xanchor="left", x=0, font=dict(size=10),
            ),
            hovermode="x unified",
        )

        st.plotly_chart(fig_modal, width="stretch", key="modal_schedule_chart")

        # ── Stats row at the bottom of the modal ──
        # Quick summary so the user doesn't have to scroll back up
        # to the KPI cards.
        stats_row([
            {
                "label": "PRODUCE",
                "value": f"{opt['production_hours']}h",
                "subtitle": "hours below break-even",
                "color": COLORS["green"],
            },
            {
                "label": "HOLD",
                "value": f"{naive['production_hours'] - opt['production_hours']}h",
                "subtitle": "hours above break-even",
                "color": COLORS["red"],
            },
            {
                "label": "AVG PRICE",
                "value": f"${opt['avg_elec_price']:.1f}",
                "subtitle": "during production hours",
                "color": COLORS["accent"],
            },
            {
                "label": "SAVINGS",
                "value": f"${savings['absolute_aud']:,.0f}",
                "subtitle": f"{savings['percentage']:.1f}% vs naive",
                "color": COLORS["green"] if savings["absolute_aud"] > 0 else COLORS["red"],
            },
        ])

    # ── Wrap the chart in a dashboard card with the expand modal ──
    dashboard_card(
        title="Production Schedule — Produce vs Hold",
        content_func=draw_schedule_chart,
        modal_title="Production Schedule — Detailed View",
        modal_content_func=draw_schedule_modal,
    )

    # ==============================================================
    # STEP 4: OPTIMISED vs NAIVE COMPARISON CARD
    # ==============================================================
    # This is the "payoff" section — it answers the question:
    # "Why bother with an optimizer at all?"
    #
    # We show two columns side by side:
    #   Left  → "Optimised" strategy (only produce when price < break-even)
    #   Right → "Naive 24/7" strategy (run the electrolyser non-stop)
    #
    # Below that, a highlighted savings row shows how much money
    # the optimiser saves compared to running 24/7.
    #
    # All values come from get_optimizer_summary() which was already
    # fetched in Step 2 (stored in opt, naive, savings dicts).

    def draw_comparison():
        """
        Draw the optimised-vs-naive comparison inside a dashboard_card.

        Layout:
          - Two columns: left = Optimised, right = Naive 24/7
          - Each column has 4 metric cards (hours, H₂, cost, cost/kg)
          - Below: a full-width savings highlight row
        """

        # ── Column headers ──
        # Label each column so the user knows which is which.
        left_col, right_col = st.columns(2)

        with left_col:
            # "Optimised" header — styled in green to signal "good"
            st.markdown(
                f'<div style="font-size:0.85rem;font-weight:700;'
                f'color:{COLORS["green"]};margin-bottom:0.5rem;'
                f'text-transform:uppercase;letter-spacing:0.05em;">'
                f'Optimised Strategy</div>',
                unsafe_allow_html=True,
            )

            # Production hours — how long the electrolyser runs
            metric_card(
                label="PRODUCTION HOURS",
                value=f"{opt['production_hours']}h",
                subtitle=f"of {naive['production_hours']}h available",
                color=COLORS["green"],
            )

            # Total H₂ output in kilograms
            metric_card(
                label="H₂ OUTPUT",
                value=f"{opt['total_h2_kg']:,.0f} kg",
                subtitle="total hydrogen produced",
                color=COLORS["green"],
            )

            # Total electricity cost for the optimised schedule
            metric_card(
                label="ELECTRICITY COST",
                value=f"${opt['total_cost_aud']:,.0f}",
                subtitle="AUD total",
                color=COLORS["green"] if opt["total_cost_aud"] < naive["total_cost_aud"] else COLORS["red"],
            )

            # Cost per kilogram of hydrogen — the key efficiency metric
            metric_card(
                label="COST PER KG",
                value=f"${opt['cost_per_kg']:.2f}",
                subtitle="AUD per kg H₂",
                color=COLORS["green"],
            )

        with right_col:
            # "Naive 24/7" header — styled in muted/red to signal "baseline"
            st.markdown(
                f'<div style="font-size:0.85rem;font-weight:700;'
                f'color:{COLORS["red"]};margin-bottom:0.5rem;'
                f'text-transform:uppercase;letter-spacing:0.05em;">'
                f'Naive 24/7 Strategy</div>',
                unsafe_allow_html=True,
            )

            # Naive: runs every single hour regardless of price
            metric_card(
                label="PRODUCTION HOURS",
                value=f"{naive['production_hours']}h",
                subtitle="runs non-stop",
                color=COLORS["text_secondary"],
            )

            # Naive: produces more H₂ (runs more hours) but at higher cost
            metric_card(
                label="H₂ OUTPUT",
                value=f"{naive['total_h2_kg']:,.0f} kg",
                subtitle="total hydrogen produced",
                color=COLORS["text_secondary"],
            )

            # Naive: total electricity cost — typically much higher
            metric_card(
                label="ELECTRICITY COST",
                value=f"${naive['total_cost_aud']:,.0f}",
                subtitle="AUD total",
                color=COLORS["text_secondary"],
            )

            # Naive: cost per kg — higher because it buys expensive hours too
            metric_card(
                label="COST PER KG",
                value=f"${naive['cost_per_kg']:.2f}",
                subtitle="AUD per kg H₂",
                color=COLORS["text_secondary"],
            )

        # ── Savings highlight row ──
        # A full-width coloured banner showing the total savings.
        # This is the "punchline" of the entire page — it proves
        # the optimiser adds value.

        # Pick the colour: green if we're saving money, red if not
        savings_color = COLORS["green"] if savings["absolute_aud"] > 0 else COLORS["red"]

        st.markdown(
            f'<div style="background-color:{COLORS["bg_card"]};'
            f'border:2px solid {savings_color};'
            f'border-radius:8px;padding:1rem;margin-top:0.8rem;'
            f'text-align:center;">'
            f'<div style="font-size:0.7rem;color:{COLORS["text_muted"]};'
            f'text-transform:uppercase;letter-spacing:0.06em;'
            f'margin-bottom:0.3rem;">ESTIMATED SAVINGS</div>'
            f'<div style="font-size:1.6rem;font-weight:700;'
            f'color:{savings_color};">'
            f'${savings["absolute_aud"]:,.0f} AUD '
            f'({savings["percentage"]:.1f}%)</div>'
            f'<div style="font-size:0.75rem;color:{COLORS["text_secondary"]};'
            f'margin-top:0.2rem;">'
            f'compared to running the electrolyser 24/7</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

    # Wrap the comparison in a dashboard card (no modal needed —
    # the content is already detailed enough at normal size)
    dashboard_card(
        title="Optimised vs Naive — Cost Comparison",
        content_func=draw_comparison,
    )
