"""
components.py — Reusable UI building blocks for the H2 Optimizer app.

This file contains functions that draw common UI elements used across
multiple pages.  Instead of copy-pasting the same card/metric code
into every page file, we define it once here and import it.

Usage in any page:
    from components import metric_card, dashboard_card, stats_row

Available components:
    1. metric_card()    — a single KPI box (e.g. "-$12.40 AUD/MWh")
    2. dashboard_card() — a dark card with title, content, and an
                          optional click-to-expand modal
    3. stats_row()      — a horizontal row of metric cards (like the
                          bottom of the indicator modal)
"""

import streamlit as st
from Streamlit_App_Design.style import COLORS


# =====================================================================
# 1. METRIC CARD
# =====================================================================
# Renders a single KPI box that looks like the cards in our mockup:
#
#   ┌──────────────┐
#   │  SPOT PRICE  │  ← label (small, muted, uppercase)
#   │  -$12.40     │  ← value (large, coloured, bold)
#   │  AUD/MWh     │  ← subtitle (small, grey)
#   └──────────────┘
#
# The colour of the value text is customisable — green for positive
# signals, red for negative, accent blue for neutral, etc.


def metric_card(
    label: str,
    value: str,
    subtitle: str = "",
    color: str = COLORS["text_primary"],
    delta: str = "",
    delta_color: str = "",
):
    """
    Draw a single KPI metric card using custom HTML.

    Parameters:
        label       — small uppercase heading (e.g. "SPOT PRICE")
        value       — the main number/text (e.g. "-$12.40")
        subtitle    — smaller text below the value (e.g. "AUD/MWh")
        color       — colour for the value text (use COLORS dict)
        delta       — optional change indicator (e.g. "-134.2%")
        delta_color — colour for the delta text (defaults to same as value)

    Example:
        metric_card("SPOT PRICE", "-$12.40", "AUD/MWh", COLORS["green"])
    """
    # If no delta colour specified, use the value colour
    if not delta_color:
        delta_color = color

    # Build the delta HTML only if a delta value was provided
    delta_html = ""
    if delta:
        delta_html = (
            f'<span style="font-size:0.7rem; color:{delta_color}; '
            f'margin-left:0.3rem;">{delta}</span>'
        )

    # Render the card as a styled HTML block
    st.markdown(
        f"""
        <div style="
            background-color: {COLORS['bg_card']};
            border: 1px solid {COLORS['border']};
            border-radius: 8px;
            padding: 0.8rem 1rem;
            height: 100%;
        ">
            <!-- Label: small, muted, uppercase -->
            <div style="
                font-size: 0.65rem;
                color: {COLORS['text_muted']};
                text-transform: uppercase;
                letter-spacing: 0.06em;
                margin-bottom: 0.3rem;
                font-weight: 600;
            ">{label}</div>

            <!-- Value: large, bold, coloured -->
            <div style="
                font-size: 1.4rem;
                font-weight: 700;
                color: {color};
                line-height: 1.2;
            ">
                {value}{delta_html}
            </div>

            <!-- Subtitle: small, grey -->
            <div style="
                font-size: 0.7rem;
                color: {COLORS['text_secondary']};
                margin-top: 0.2rem;
            ">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# =====================================================================
# 2. DASHBOARD CARD
# =====================================================================
# A dark card container with a title bar and optional expand button.
# This wraps around any content (charts, tables, text) and gives it
# the consistent dark-bordered look from our mockup.
#
# If you pass a modal_content function, clicking "Expand" opens a
# Streamlit dialog — this is how we get grading points for user
# interaction.
#
#   ┌─── Electricity Price — SA1 ──────────── [⤢] ─┐
#   │                                               │
#   │         (your chart / content here)            │
#   │                                               │
#   └───────────────────────────────────────────────┘


def dashboard_card(
    title: str,
    content_func,
    modal_title: str = "",
    modal_content_func=None,
    height: str = "auto",
):
    """
    Draw a dark dashboard card with an optional expand-to-modal button.

    Parameters:
        title              — text shown in the card's title bar
        content_func       — a function (no arguments) that draws the
                             card's body using Streamlit calls.
                             Example: lambda: st.line_chart(data)
        modal_title        — title for the expanded modal (defaults to
                             same as card title)
        modal_content_func — a function (no arguments) that draws the
                             modal's content.  If None, no expand
                             button is shown.
        height             — CSS height for the card body (e.g. "300px")

    Example:
        dashboard_card(
            title="Electricity Price — SA1",
            content_func=lambda: st.plotly_chart(fig),
            modal_title="Electricity Price — Detailed View",
            modal_content_func=lambda: draw_indicator_modal(),
        )
    """
    # If no modal title specified, reuse the card title
    if not modal_title:
        modal_title = title

    # ── Card container (HTML for the border and title bar) ──
    st.markdown(
        f"""
        <div style="
            background-color: {COLORS['bg_card']};
            border: 1px solid {COLORS['border']};
            border-radius: 8px;
            overflow: hidden;
            margin-bottom: 0.5rem;
        ">
            <!-- Title bar -->
            <div style="
                display: flex;
                justify-content: space-between;
                align-items: center;
                padding: 0.5rem 0.8rem;
                border-bottom: 1px solid {COLORS['border']};
                background-color: {COLORS['bg']};
            ">
                <span style="
                    font-size: 0.8rem;
                    font-weight: 600;
                    color: {COLORS['text_primary']};
                ">{title}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Card body (Streamlit content) ──
    # We use a container so the content sits visually inside the card.
    # The negative margin pulls it up into the card border.
    with st.container():
        # Small styling wrapper for padding
        st.markdown(
            f'<div style="margin-top:-0.5rem; padding:0.6rem 0;">',
            unsafe_allow_html=True,
        )
        # Call the content function — this is where the page puts
        # its chart, table, or whatever content goes inside the card
        content_func()
        st.markdown("</div>", unsafe_allow_html=True)

    # ── Expand button (only if a modal function was provided) ──
    if modal_content_func is not None:
        # We define the dialog function inline using @st.dialog
        # This creates a popup modal when the button is clicked
        @st.dialog(modal_title, width="large")
        def _open_modal():
            modal_content_func()

        # Place the expand button right-aligned below the card
        _, btn_col = st.columns([6, 1])
        with btn_col:
            if st.button("⤢ Expand", key=f"expand_{title}"):
                _open_modal()


# =====================================================================
# 3. STATS ROW
# =====================================================================
# A horizontal row of metric cards, like the bottom of the indicator
# modal.  Pass a list of dicts and it lays them out evenly.
#
#  ┌──────────┬──────────┬──────────┬──────────┬──────────┐
#  │ CURRENT  │ EMA 24H  │  BB %B   │  RSI 14  │  SIGNAL  │
#  │ -$12.40  │  $17.20  │   0.12   │   45.0   │ PRODUCE  │
#  │ AUD/MWh  │ Spot<EMA │ Nr lower │ Neutral  │ Price<BE │
#  └──────────┴──────────┴──────────┴──────────┴──────────┘


def stats_row(stats: list[dict]):
    """
    Draw a horizontal row of metric cards.

    Parameters:
        stats — a list of dicts, each with keys:
                label, value, subtitle, color
                (same keys as metric_card parameters)

    Example:
        stats_row([
            {"label": "CURRENT",  "value": "-$12.40", "subtitle": "AUD/MWh",     "color": COLORS["green"]},
            {"label": "EMA 24H",  "value": "$17.20",  "subtitle": "Spot < EMA",  "color": COLORS["orange"]},
            {"label": "SIGNAL",   "value": "PRODUCE",  "subtitle": "Price < BE",  "color": COLORS["green"]},
        ])
    """
    # Create one column per stat
    cols = st.columns(len(stats))

    # Fill each column with a metric card
    for col, stat in zip(cols, stats):
        with col:
            metric_card(
                label=stat.get("label", ""),
                value=stat.get("value", ""),
                subtitle=stat.get("subtitle", ""),
                color=stat.get("color", COLORS["text_primary"]),
                delta=stat.get("delta", ""),
                delta_color=stat.get("delta_color", ""),
            )


# =====================================================================
# 4. SECTION HEADER
# =====================================================================
# A small helper to create consistent section headings within pages.


def section_header(title: str, subtitle: str = ""):
    """
    Draw a section heading with an optional subtitle.

    Parameters:
        title    — the section heading text
        subtitle — smaller explanatory text below (optional)

    Example:
        section_header("Technical Indicators", "Toggle indicators on/off")
    """
    st.markdown(
        f"""
        <div style="margin: 1rem 0 0.5rem 0;">
            <span style="font-size: 1rem; font-weight: 600;
                         color: {COLORS['text_primary']};">
                {title}
            </span>
            {"<br><span style='font-size:0.75rem; color:" + COLORS['text_secondary'] + ";'>" + subtitle + "</span>" if subtitle else ""}
        </div>
        """,
        unsafe_allow_html=True,
    )


# =====================================================================
# 5. ALERT / NEWS ITEM
# =====================================================================
# A single alert/news row for the market alerts card.
# Colour-coded by severity: success, warning, error, info.


def alert_item(time: str, severity: str, message: str):
    """
    Draw a single alert row with a coloured dot and message.

    Parameters:
        time     — timestamp string (e.g. "14:32")
        severity — "success" | "warning" | "error" | "info"
        message  — the alert text

    Example:
        alert_item("14:32", "warning", "SA region negative pricing expected")
    """
    # Pick the dot colour based on severity
    dot_colors = {
        "success": COLORS["green"],
        "warning": COLORS["yellow"],
        "error":   COLORS["red"],
        "info":    COLORS["accent"],
    }
    dot_color = dot_colors.get(severity, COLORS["text_muted"])

    st.markdown(
        f"""
        <div style="
            display: flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.35rem 0;
            border-bottom: 1px solid {COLORS['border']};
            font-size: 0.78rem;
        ">
            <!-- Time -->
            <span style="color:{COLORS['text_muted']}; min-width:2.5rem;">
                {time}
            </span>
            <!-- Severity dot -->
            <span style="
                width: 6px; height: 6px; border-radius: 50%;
                background: {dot_color}; flex-shrink: 0;
            "></span>
            <!-- Message -->
            <span style="color:{COLORS['text_secondary']};">
                {message}
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )
