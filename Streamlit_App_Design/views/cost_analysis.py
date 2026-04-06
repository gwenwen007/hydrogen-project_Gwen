"""
cost_analysis.py — Cost Analysis page.

This page gives the user a full picture of hydrogen production costs:
  1. Cost breakdown donut chart — electricity vs other cost categories
  2. Historical cost trend — monthly cost-per-kg over the past 12 months
  3. Sensitivity analysis — how H₂ cost changes when electricity price moves
  4. CSV export button — download combined data for offline analysis

Data comes from data/sample_data.py.  When the real optimizer output
is available, just swap the import source — the page code stays
the same because the data format is identical.
"""

import streamlit as st
import plotly.graph_objects as go              # Plotly for interactive charts
from style import COLORS
from components import metric_card, dashboard_card, stats_row

# Import placeholder data functions.
# get_cost_breakdown()        → DataFrame: category, cost_aud
# get_historical_cost_trend() → DataFrame: month, cost_per_kg_aud, volume_kg
# get_sensitivity_analysis()  → DataFrame: price_change_pct, h2_cost_per_kg, change_vs_base
# get_export_data()           → DataFrame: combined prices + schedule + costs
from data.sample_data import (
    get_cost_breakdown,
    get_historical_cost_trend,
    get_sensitivity_analysis,
    get_export_data,
)


def render():
    """Draw the Cost Analysis page.  Called by app.py."""

    # ==============================================================
    # STEP 1: COST BREAKDOWN DONUT CHART
    # ==============================================================
    # A donut chart (pie chart with a hole) showing how total
    # hydrogen production cost is split across categories:
    #   - Electricity (the biggest chunk — what the optimizer targets)
    #   - Water, Maintenance, Labour, Depreciation, Other
    #
    # The donut shape lets us put a total-cost label in the centre.
    # Wrapped in dashboard_card() for the consistent dark look.

    # Fetch the cost breakdown data.
    # This returns a DataFrame with "category" and "cost_aud" columns.
    cost_df = get_cost_breakdown()

    # Calculate the total cost — we'll display it in the donut centre
    total_cost = cost_df["cost_aud"].sum()

    def draw_donut():
        """
        Draw a donut chart showing the cost breakdown by category.

        Each slice = one cost category.  The size of the slice is
        proportional to its share of total cost.  Electricity is
        typically the largest slice (~65-70%).
        """

        # ── Define colours for each slice ──
        # We use a list of colours that match our dark theme.
        # Electricity gets the accent blue (it's the most important),
        # the rest get progressively muted tones.
        slice_colors = [
            COLORS["accent"],          # Electricity — accent blue (dominant)
            COLORS["cyan"],            # Water — cyan
            COLORS["orange"],          # Maintenance — orange
            COLORS["yellow"],          # Labour — yellow
            COLORS["text_secondary"],  # Depreciation — grey
            COLORS["border"],          # Other — dark grey
        ]

        fig_donut = go.Figure()

        fig_donut.add_trace(go.Pie(
            labels=cost_df["category"],            # category names
            values=cost_df["cost_aud"],            # cost in AUD
            hole=0.55,                             # size of the centre hole (0–1)
            marker=dict(
                colors=slice_colors,               # custom colours per slice
                line=dict(
                    color=COLORS["bg"],            # dark border between slices
                    width=2,                       # border thickness
                ),
            ),

            # Text displayed on each slice
            textinfo="label+percent",              # show category name + percentage
            textfont=dict(size=10, color=COLORS["text_primary"]),

            # Hover tooltip showing the exact AUD amount
            hovertemplate=(
                "<b>%{label}</b><br>"
                "$%{value:,.0f} AUD<br>"
                "%{percent}<br>"
                "<extra></extra>"
            ),
        ))

        # ── Layout styling ──
        fig_donut.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",         # transparent background
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=COLORS["text_muted"], size=11),
            margin=dict(l=20, r=20, t=20, b=20),  # tight margins
            height=340,
            showlegend=False,                      # labels are on the slices

            # Centre annotation — shows the total cost inside the donut hole.
            # We build the text string separately to avoid backslash issues
            # inside f-strings (Python <3.12 doesn't allow them).
            annotations=[dict(
                text=(
                    "<b>$" + f"{total_cost:,.0f}" + "</b><br>"
                    "<span style='font-size:10px;color:" + COLORS["text_muted"] + "'>"
                    "Total AUD</span>"
                ),
                x=0.5, y=0.5,                     # centre of the donut
                font=dict(size=16, color=COLORS["text_primary"]),
                showarrow=False,
            )],
        )

        st.plotly_chart(fig_donut, use_container_width=True, key="cost_donut")

    # ── Donut modal — shows a detailed table alongside the chart ──
    def draw_donut_modal():
        """
        Expanded view: donut chart + a breakdown table with exact
        amounts and percentages for each category.
        """
        # Re-draw the donut at a larger size
        draw_donut()

        # ── Detailed breakdown table ──
        # Show each category with its cost, percentage of total,
        # and a visual bar using st.progress-style HTML.
        st.markdown(
            f'<div style="font-size:0.8rem;font-weight:600;'
            f'color:{COLORS["text_primary"]};margin:0.8rem 0 0.5rem 0;">'
            f'Detailed Breakdown</div>',
            unsafe_allow_html=True,
        )

        # Loop through each cost category and draw a row
        for _, row in cost_df.iterrows():
            # Calculate this category's percentage of total cost
            pct = row["cost_aud"] / total_cost * 100

            # Draw a row: category name | bar | amount
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:0.5rem;'
                f'padding:0.3rem 0;border-bottom:1px solid {COLORS["border"]};">'
                f'<span style="min-width:100px;font-size:0.75rem;'
                f'color:{COLORS["text_secondary"]};">{row["category"]}</span>'
                f'<div style="flex:1;height:6px;background:{COLORS["border"]};'
                f'border-radius:3px;overflow:hidden;">'
                f'<div style="width:{pct}%;height:100%;'
                f'background:{COLORS["accent"]};border-radius:3px;"></div></div>'
                f'<span style="min-width:90px;text-align:right;font-size:0.75rem;'
                f'color:{COLORS["text_primary"]};">${row["cost_aud"]:,.0f} '
                f'({pct:.1f}%)</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

    # ==============================================================
    # STEP 2: HISTORICAL COST TREND
    # ==============================================================
    # A line chart showing monthly cost-per-kg of H₂ over the past
    # 12 months.  This reveals seasonal patterns:
    #   - Spring/autumn: cheaper (more solar + wind generation)
    #   - Summer/winter: more expensive (higher demand, less renewables)
    #
    # A secondary bar layer shows monthly production volume so the
    # user can see if cost and volume are correlated.

    # Fetch the historical cost trend data.
    # Returns a DataFrame with: month, cost_per_kg_aud, volume_kg
    trend_df = get_historical_cost_trend()

    def draw_cost_trend():
        """
        Draw a dual-axis chart:
          - Line (left y-axis): cost per kg of H₂ over time
          - Bars (right y-axis): monthly production volume in kg

        The dual axes let the user see both metrics on one chart
        without the scales clashing.
        """

        # ── Create a figure with two y-axes ──
        # Plotly supports secondary y-axes via make_subplots, but
        # for simplicity we use the layout trick: one trace on yaxis,
        # another on yaxis2.
        fig_trend = go.Figure()

        # ── Layer 1: Volume bars (background, right y-axis) ──
        # Drawn first so the line sits on top of the bars visually.
        fig_trend.add_trace(go.Bar(
            x=trend_df["month"],                   # monthly timestamps
            y=trend_df["volume_kg"],               # production volume
            name="Volume (kg)",
            marker_color=COLORS["accent"],
            opacity=0.2,                           # very faint background
            yaxis="y2",                            # link to right y-axis
            hovertemplate=(
                "<b>%{x|%b %Y}</b><br>"
                "Volume: %{y:,.0f} kg<br>"
                "<extra></extra>"
            ),
        ))

        # ── Layer 2: Cost-per-kg line (foreground, left y-axis) ──
        fig_trend.add_trace(go.Scatter(
            x=trend_df["month"],                   # monthly timestamps
            y=trend_df["cost_per_kg_aud"],         # cost in AUD/kg
            mode="lines+markers",                  # line with dots at each month
            name="Cost/kg (AUD)",
            line=dict(color=COLORS["accent"], width=2),
            marker=dict(size=6, color=COLORS["accent"]),
            hovertemplate=(
                "<b>%{x|%b %Y}</b><br>"
                "Cost: $%{y:.2f}/kg<br>"
                "<extra></extra>"
            ),
        ))

        # ── Layout with dual y-axes ──
        fig_trend.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=COLORS["text_muted"], size=11),
            margin=dict(l=50, r=50, t=20, b=40),
            height=320,

            # Left y-axis: cost per kg
            yaxis=dict(
                title="AUD / kg H₂",
                title_font=dict(size=10, color=COLORS["text_muted"]),
                gridcolor=COLORS["border_light"],
                gridwidth=0.5,
                tickfont=dict(color=COLORS["text_muted"], size=10),
            ),

            # Right y-axis: volume
            yaxis2=dict(
                title="Volume (kg)",
                title_font=dict(size=10, color=COLORS["text_muted"]),
                overlaying="y",                    # overlay on the same plot
                side="right",                      # position on the right
                showgrid=False,                    # no extra grid lines
                tickfont=dict(color=COLORS["text_muted"], size=9),
            ),

            # X-axis: months
            xaxis=dict(
                showgrid=False,
                linecolor=COLORS["border"],
                tickfont=dict(color=COLORS["text_muted"], size=10),
            ),

            # Legend at the top
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02,
                xanchor="left", x=0, font=dict(size=10),
            ),

            hovermode="x unified",
        )

        st.plotly_chart(fig_trend, use_container_width=True, key="cost_trend_chart")

    # ==============================================================
    # RENDER: Place Step 1 and Step 2 side by side
    # ==============================================================
    # Two columns: donut chart on the left, trend chart on the right.
    donut_col, trend_col = st.columns(2)

    with donut_col:
        dashboard_card(
            title="Cost Breakdown — H₂ Production",
            content_func=draw_donut,
            modal_title="Cost Breakdown — Detailed View",
            modal_content_func=draw_donut_modal,
        )

    with trend_col:
        dashboard_card(
            title="Historical Cost Trend — 12 Months",
            content_func=draw_cost_trend,
        )
