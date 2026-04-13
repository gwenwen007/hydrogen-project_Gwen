"""
cost_analysis.py — Cost Analysis page.

This page gives the user a full picture of hydrogen production costs:
  1. Cost breakdown donut chart — electricity vs other cost categories
  2. Historical cost trend — monthly cost-per-kg from real AEMO data
  3. Sensitivity analysis — how H₂ cost changes when electricity price moves
  4. CSV export button — download combined data for offline analysis

Data now comes from data/cost_analysis_model.py, which pulls real
electricity costs from the production optimizer (real AEMO prices + ML).

The donut modal includes editable cost inputs so the user can adjust
Depreciation, Labour, Maintenance, Water, and add custom cost factors.
"""

import streamlit as st
import plotly.graph_objects as go              # Plotly for interactive charts
from style import COLORS
from components import metric_card, dashboard_card, stats_row

# ── Import real-data cost functions ──
# These replace the old sample_data imports.  The data format (column
# names, types) is the same, so the chart code barely changes.
from data.cost_analysis_model import (
    get_default_cost_items,
    get_cost_breakdown,
    get_sensitivity_analysis,
    get_export_data,
    get_historical_cost_trend,
)
from data.production_optimizer_model import get_optimizer_summary


# =====================================================================
# HELPER: Get region abbreviation from session state
# =====================================================================

def _region_abbr() -> str:
    """
    Extract the 2–3 letter NEM region code from session state.
    e.g. "New South Wales (NSW)" → "NSW"
    """
    full = st.session_state.get("region", "New South Wales (NSW)")
    return full.split("(")[-1].replace(")", "").strip()


# =====================================================================
# HELPER: Get or initialise editable cost items in session state
# =====================================================================

def _get_cost_items() -> list[dict]:
    """
    Return the current non-electricity cost items from session state.
    If none exist yet, initialise with defaults.
    """
    if "cost_items" not in st.session_state:
        st.session_state["cost_items"] = get_default_cost_items()
    return st.session_state["cost_items"]


def render():
    """Draw the Cost Analysis page.  Called by app.py."""

    # ── Read current settings ──
    region = _region_abbr()
    cost_items = _get_cost_items()

    # ── Fetch real optimizer summary for KPI cards ──
    # This gives us the actual electricity cost, total H₂ produced,
    # and savings vs naive 24/7 production.
    summary = get_optimizer_summary(region)

    # ==============================================================
    # KPI ROW — Key cost metrics at a glance
    # ==============================================================
    # Show the most important numbers before the charts.
    kpi_cols = st.columns(4)

    # ── KPI 1: Optimised cost per kg ──
    opt_cost_per_kg = summary["optimised"]["cost_per_kg"]
    with kpi_cols[0]:
        metric_card(
            label="Cost / kg (Optimised)",
            value=f"${opt_cost_per_kg:.2f}",
            subtitle=f'{summary["optimised"]["production_hours"]}h production',
        )

    # ── KPI 2: Naive cost per kg (24/7 baseline) ──
    naive_cost_per_kg = summary["naive"]["cost_per_kg"]
    with kpi_cols[1]:
        metric_card(
            label="Cost / kg (24/7 Naive)",
            value=f"${naive_cost_per_kg:.2f}",
            subtitle=f'{summary["naive"]["production_hours"]}h production',
        )

    # ── KPI 3: Total electricity cost ──
    total_elec = summary["optimised"]["total_cost_aud"]
    with kpi_cols[2]:
        metric_card(
            label="Electricity Cost",
            value=f"${total_elec:,.0f}",
            subtitle=f'avg ${summary["optimised"]["avg_elec_price"]:.1f}/MWh',
        )

    # ── KPI 4: Savings vs naive ──
    savings = summary["savings"]["absolute_aud"]
    savings_pct = summary["savings"]["percentage"]
    with kpi_cols[3]:
        metric_card(
            label="Savings vs 24/7",
            value=f"${savings:,.0f}",
            subtitle=f"{savings_pct:.1f}% reduction",
        )

    # Small spacer between KPIs and charts
    st.markdown("<div style='margin-top:0.6rem;'></div>", unsafe_allow_html=True)

    # ==============================================================
    # STEP 1: COST BREAKDOWN DONUT CHART
    # ==============================================================
    # A donut chart showing how total H₂ production cost is split:
    #   - Electricity (from real optimizer — the biggest chunk)
    #   - Water, Maintenance, Labour, Depreciation (user-editable)
    #   - Any custom cost factors the user has added

    # ── Fetch cost breakdown using real data + current cost items ──
    cost_df = get_cost_breakdown(
        region_abbr=region,
        extra_costs=cost_items,
    )

    # Total cost displayed in the donut centre
    total_cost = cost_df["cost_aud"].sum()

    # ── Colour palette for the donut slices ──
    # Electricity gets accent blue.  Additional categories cycle
    # through the remaining theme colours.
    _SLICE_PALETTE = [
        COLORS["accent"],          # Electricity — accent blue (dominant)
        COLORS["cyan"],            # Water — cyan
        COLORS["orange"],          # Maintenance — orange
        COLORS["yellow"],          # Labour — yellow
        COLORS["text_secondary"],  # Depreciation — grey
        COLORS["border"],          # Custom 1 — dark grey
        COLORS["green"],           # Custom 2 — green
        COLORS["red"],             # Custom 3 — red
    ]

    def _slice_colors(n: int) -> list[str]:
        """Return n colours from the palette, cycling if needed."""
        return [_SLICE_PALETTE[i % len(_SLICE_PALETTE)] for i in range(n)]

    def draw_donut():
        """
        Draw a donut chart showing the cost breakdown by category.

        Each slice = one cost category.  The size of the slice is
        proportional to its share of total cost.  Electricity is
        typically the largest slice (~60-70%).
        """
        colors = _slice_colors(len(cost_df))

        fig_donut = go.Figure()

        fig_donut.add_trace(go.Pie(
            labels=cost_df["category"],            # category names
            values=cost_df["cost_aud"],            # cost in AUD
            hole=0.55,                             # size of the centre hole
            marker=dict(
                colors=colors,                     # custom colours per slice
                line=dict(
                    color=COLORS["bg"],            # dark border between slices
                    width=2,
                ),
            ),
            textinfo="label+percent",              # show category + percentage
            textfont=dict(size=10, color=COLORS["text_primary"]),
            hovertemplate=(
                "<b>%{label}</b><br>"
                "$%{value:,.0f} AUD<br>"
                "%{percent}<br>"
                "<extra></extra>"
            ),
        ))

        # ── Layout styling ──
        fig_donut.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=COLORS["text_muted"], size=11),
            margin=dict(l=20, r=20, t=20, b=20),
            height=340,
            showlegend=False,
            # Centre annotation: total cost inside the donut hole
            annotations=[dict(
                text=(
                    "<b>$" + f"{total_cost:,.0f}" + "</b><br>"
                    "<span style='font-size:10px;color:" + COLORS["text_muted"] + "'>"
                    "Total AUD</span>"
                ),
                x=0.5, y=0.5,
                font=dict(size=16, color=COLORS["text_primary"]),
                showarrow=False,
            )],
        )

        st.plotly_chart(fig_donut, width="stretch", key="cost_donut")

    # ==============================================================
    # DONUT MODAL — Editable cost inputs + breakdown table
    # ==============================================================
    # This is the click-to-expand detailed view.  It shows:
    #   1. The donut chart (rebuilt with unique key)
    #   2. Editable number inputs for each non-electricity cost
    #   3. An "Add Cost Factor" section
    #   4. A detailed breakdown table with bars

    def draw_donut_modal():
        """
        Expanded view: donut + editable cost inputs + breakdown table.

        The user can adjust Water, Maintenance, Labour, Depreciation
        costs, and add entirely new cost categories.  Changes are
        stored in session state and immediately reflected in the donut.
        """

        # ── Section A: Editable Cost Inputs ──
        st.markdown(
            f'<div style="font-size:0.85rem;font-weight:600;'
            f'color:{COLORS["text_primary"]};margin-bottom:0.5rem;">'
            f'Edit Cost Factors</div>',
            unsafe_allow_html=True,
        )
        st.markdown(
            f'<div style="font-size:0.75rem;color:{COLORS["text_secondary"]};'
            f'margin-bottom:0.8rem;">'
            f'Electricity cost is calculated from the Production Optimizer '
            f'using real AEMO prices.  Adjust the other costs below.</div>',
            unsafe_allow_html=True,
        )

        # Show electricity cost as read-only info
        elec_cost = cost_df.loc[cost_df["category"] == "Electricity", "cost_aud"].iloc[0]
        st.markdown(
            f'<div style="display:flex;justify-content:space-between;'
            f'padding:0.4rem 0.6rem;background:{COLORS["bg_card"]};'
            f'border:1px solid {COLORS["border"]};border-radius:6px;'
            f'margin-bottom:0.6rem;">'
            f'<span style="font-size:0.8rem;color:{COLORS["text_secondary"]};">'
            f'Electricity (from Optimizer)</span>'
            f'<span style="font-size:0.8rem;font-weight:600;'
            f'color:{COLORS["accent"]};">${elec_cost:,.2f}</span></div>',
            unsafe_allow_html=True,
        )

        # ── Editable inputs for each non-electricity cost ──
        # We use st.number_input for each item.  When the user changes
        # a value, we update session state so the donut recalculates.
        current_items = _get_cost_items()
        updated = False

        for i, item in enumerate(current_items):
            new_val = st.number_input(
                label=item["name"],
                value=float(item["cost_aud"]),
                min_value=0.0,
                step=50.0,
                format="%.2f",
                key=f"cost_edit_{i}",
                help=f"Adjust the {item['name'].lower()} cost in AUD",
            )
            # If the user changed the value, update session state
            if new_val != item["cost_aud"]:
                current_items[i]["cost_aud"] = new_val
                updated = True

        # ── Section B: Add a new custom cost factor ──
        st.markdown(
            f'<div style="font-size:0.8rem;font-weight:600;'
            f'color:{COLORS["text_primary"]};margin:1rem 0 0.4rem 0;">'
            f'Add Custom Cost Factor</div>',
            unsafe_allow_html=True,
        )

        # Two columns: name input + amount input
        add_col1, add_col2 = st.columns([2, 1])
        with add_col1:
            new_name = st.text_input(
                "Category name",
                value="",
                placeholder="e.g. Insurance",
                key="new_cost_name",
                label_visibility="collapsed",
            )
        with add_col2:
            new_amount = st.number_input(
                "Amount (AUD)",
                value=0.0,
                min_value=0.0,
                step=50.0,
                format="%.2f",
                key="new_cost_amount",
                label_visibility="collapsed",
            )

        # "Add" button — appends the new cost to session state
        if st.button("Add Cost Factor", key="add_cost_btn"):
            if new_name.strip() and new_amount > 0:
                current_items.append({
                    "name": new_name.strip(),
                    "cost_aud": new_amount,
                })
                st.session_state["cost_items"] = current_items
                st.rerun()   # refresh the page to show the new item

        # Save any edits back to session state
        if updated:
            st.session_state["cost_items"] = current_items

        # ── Section C: Donut chart (rebuilt with modal-specific key) ──
        st.markdown("<div style='margin-top:1rem;'></div>", unsafe_allow_html=True)

        # Recalculate with potentially updated costs
        modal_cost_df = get_cost_breakdown(
            region_abbr=region,
            extra_costs=current_items,
        )
        modal_total = modal_cost_df["cost_aud"].sum()
        modal_colors = _slice_colors(len(modal_cost_df))

        fig_donut_modal = go.Figure()
        fig_donut_modal.add_trace(go.Pie(
            labels=modal_cost_df["category"],
            values=modal_cost_df["cost_aud"],
            hole=0.55,
            marker=dict(
                colors=modal_colors,
                line=dict(color=COLORS["bg"], width=2),
            ),
            textinfo="label+percent",
            textfont=dict(size=10, color=COLORS["text_primary"]),
            hovertemplate=(
                "<b>%{label}</b><br>$%{value:,.0f} AUD<br>"
                "%{percent}<br><extra></extra>"
            ),
        ))
        fig_donut_modal.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=COLORS["text_muted"], size=11),
            margin=dict(l=20, r=20, t=20, b=20),
            height=340,
            showlegend=False,
            annotations=[dict(
                text=(
                    "<b>$" + f"{modal_total:,.0f}" + "</b><br>"
                    "<span style='font-size:10px;color:" + COLORS["text_muted"] + "'>"
                    "Total AUD</span>"
                ),
                x=0.5, y=0.5,
                font=dict(size=16, color=COLORS["text_primary"]),
                showarrow=False,
            )],
        )
        st.plotly_chart(fig_donut_modal, width="stretch", key="modal_cost_donut")

        # ── Section D: Detailed breakdown table with bars ──
        st.markdown(
            f'<div style="font-size:0.8rem;font-weight:600;'
            f'color:{COLORS["text_primary"]};margin:0.8rem 0 0.5rem 0;">'
            f'Detailed Breakdown</div>',
            unsafe_allow_html=True,
        )

        for _, row in modal_cost_df.iterrows():
            pct = row["cost_aud"] / modal_total * 100 if modal_total > 0 else 0
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
    # Line chart showing monthly cost-per-kg of H₂ calculated from
    # real AEMO prices.  A secondary bar layer shows estimated
    # monthly production volume.

    # Fetch real historical cost trend
    trend_df = get_historical_cost_trend(
        region_abbr=region,
        extra_costs=cost_items,
    )

    def draw_cost_trend():
        """
        Draw a dual-axis chart:
          - Line (left y-axis): cost per kg of H₂ over time
          - Bars (right y-axis): monthly production volume in kg
        """
        fig_trend = go.Figure()

        # ── Layer 1: Volume bars (background, right y-axis) ──
        fig_trend.add_trace(go.Bar(
            x=trend_df["month"],
            y=trend_df["volume_kg"],
            name="Volume (kg)",
            marker_color=COLORS["accent"],
            opacity=0.2,                           # faint background bars
            yaxis="y2",
            hovertemplate=(
                "<b>%{x|%b %Y}</b><br>"
                "Volume: %{y:,.0f} kg<br>"
                "<extra></extra>"
            ),
        ))

        # ── Layer 2: Cost-per-kg line (foreground, left y-axis) ──
        fig_trend.add_trace(go.Scatter(
            x=trend_df["month"],
            y=trend_df["cost_per_kg_aud"],
            mode="lines+markers",
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
            yaxis=dict(
                title="AUD / kg H₂",
                title_font=dict(size=10, color=COLORS["text_muted"]),
                gridcolor=COLORS["border_light"],
                gridwidth=0.5,
                tickfont=dict(color=COLORS["text_muted"], size=10),
            ),
            yaxis2=dict(
                title="Volume (kg)",
                title_font=dict(size=10, color=COLORS["text_muted"]),
                overlaying="y",
                side="right",
                showgrid=False,
                tickfont=dict(color=COLORS["text_muted"], size=9),
            ),
            xaxis=dict(
                showgrid=False,
                linecolor=COLORS["border"],
                tickfont=dict(color=COLORS["text_muted"], size=10),
            ),
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02,
                xanchor="left", x=0, font=dict(size=10),
            ),
            hovermode="x unified",
        )

        st.plotly_chart(fig_trend, width="stretch", key="cost_trend_chart")

    # ==============================================================
    # RENDER: Place Step 1 and Step 2 side by side
    # ==============================================================
    donut_col, trend_col = st.columns(2)

    with donut_col:
        dashboard_card(
            title="Cost Breakdown — H₂ Production",
            content_func=draw_donut,
            modal_title="Cost Breakdown — Edit & Detail",
            modal_content_func=draw_donut_modal,
        )

    with trend_col:
        dashboard_card(
            title="Historical Cost Trend — Real AEMO Data",
            content_func=draw_cost_trend,
        )

    # ==============================================================
    # STEP 3: SENSITIVITY ANALYSIS CHART
    # ==============================================================
    # Shows how H₂ cost changes if electricity prices move ±20%.
    # Uses real optimizer numbers for the base case.

    # Fetch sensitivity data using real optimizer output
    sens_df = get_sensitivity_analysis(
        region_abbr=region,
        extra_costs=cost_items,
    )

    def draw_sensitivity():
        """
        Bar chart: H₂ cost per kg under 7 electricity price scenarios.
        Green = cheaper, blue = base, red = more expensive.
        """
        # ── Colour each bar by scenario ──
        bar_colors = []
        for pct in sens_df["price_change_pct"]:
            if pct < 0:
                bar_colors.append(COLORS["green"])
            elif pct == 0:
                bar_colors.append(COLORS["accent"])
            else:
                bar_colors.append(COLORS["red"])

        # ── X-axis labels ──
        x_labels = []
        for pct in sens_df["price_change_pct"]:
            if pct == 0:
                x_labels.append("Base")
            elif pct > 0:
                x_labels.append(f"+{pct}%")
            else:
                x_labels.append(f"{pct}%")

        fig_sens = go.Figure()

        fig_sens.add_trace(go.Bar(
            x=x_labels,
            y=sens_df["h2_cost_per_kg"],
            marker_color=bar_colors,
            opacity=0.85,
            text=[f"${c:.2f}" for c in sens_df["h2_cost_per_kg"]],
            textposition="outside",
            textfont=dict(color=COLORS["text_secondary"], size=10),
            hovertemplate=(
                "<b>Electricity %{x}</b><br>"
                "H₂ cost: $%{y:.2f}/kg<br>"
                "<extra></extra>"
            ),
        ))

        fig_sens.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=COLORS["text_muted"], size=11),
            margin=dict(l=50, r=20, t=30, b=40),
            height=320,
            showlegend=False,
            xaxis=dict(
                title="Electricity Price Change",
                title_font=dict(size=10, color=COLORS["text_muted"]),
                tickfont=dict(color=COLORS["text_muted"], size=10),
            ),
            yaxis=dict(
                title="H₂ Cost (AUD/kg)",
                title_font=dict(size=10, color=COLORS["text_muted"]),
                gridcolor=COLORS["border_light"],
                gridwidth=0.5,
                tickfont=dict(color=COLORS["text_muted"], size=10),
            ),
        )

        st.plotly_chart(fig_sens, width="stretch", key="sensitivity_chart")

    # Wrap in a dashboard card
    dashboard_card(
        title="Sensitivity Analysis — Electricity Price Impact",
        content_func=draw_sensitivity,
    )

    # ==============================================================
    # STEP 4: CSV EXPORT BUTTON
    # ==============================================================
    # Download button for the complete optimised production schedule.
    # Uses real AEMO data + ML forecast output.

    st.markdown("<div style='margin-top:1rem;'></div>", unsafe_allow_html=True)

    def draw_export():
        """
        Export section with description, preview table, and download button.
        The CSV contains the real optimised schedule with hourly data.
        """
        st.markdown(
            f'<div style="font-size:0.8rem;color:{COLORS["text_secondary"]};'
            f'margin-bottom:0.8rem;">'
            f'Download the complete production schedule with hourly prices, '
            f'hydrogen output, and costs from real AEMO data as a CSV file. '
            f'Open it in Excel or Google Sheets for further analysis.'
            f'</div>',
            unsafe_allow_html=True,
        )

        # ── Fetch real export data ──
        export_df = get_export_data(region_abbr=region)
        csv_string = export_df.to_csv(index=False)

        # ── Preview first 5 rows ──
        st.markdown(
            f'<div style="font-size:0.75rem;font-weight:600;'
            f'color:{COLORS["text_muted"]};margin-bottom:0.3rem;">'
            f'Preview (first 5 rows of {len(export_df)} total):</div>',
            unsafe_allow_html=True,
        )

        st.dataframe(
            export_df.head(5),
            width="stretch",
            height=180,
        )

        # ── Download button ──
        st.download_button(
            label="Download CSV",
            data=csv_string,
            file_name="h2_optimizer_export.csv",
            mime="text/csv",
            key="export_csv_button",
            help="Downloads a CSV with hourly schedule, prices, and costs",
        )

    dashboard_card(
        title="Data Export",
        content_func=draw_export,
    )
