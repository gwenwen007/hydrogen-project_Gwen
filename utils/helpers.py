"""
Helpers Module — Shared Utilities
==================================
Small reusable functions that don't belong in a specific module.
Things like formatting, unit conversions, constants, etc.

Usage:
    from utils.helpers import format_currency, AUSTRALIAN_REGIONS
"""

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# NEM regions with display names and coordinates (for weather API)
AUSTRALIAN_REGIONS = {
    "NSW1": {"name": "New South Wales", "lat": -33.87, "lon": 151.21},
    "VIC1": {"name": "Victoria", "lat": -37.81, "lon": 144.96},
    "QLD1": {"name": "Queensland", "lat": -27.47, "lon": 153.03},
    "SA1":  {"name": "South Australia", "lat": -34.93, "lon": 138.60},
    "TAS1": {"name": "Tasmania", "lat": -42.88, "lon": 147.33},
}

# Default electrolyzer parameters (from NREL H2A model)
DEFAULT_EFFICIENCY_KWH_PER_KG = 52.5   # kWh per kg H2 (PEM electrolyzer)
DEFAULT_CAPACITY_MW = 10                # 10 MW electrolyzer
DEFAULT_TARGET_H2_KG = 500             # 500 kg target production


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def format_currency(value: float, currency: str = "AUD") -> str:
    """Format a number as currency, e.g. 'AUD 1,234.56'."""
    return f"{currency} {value:,.2f}"


def format_price_per_kg(total_cost: float, total_kg: float) -> str:
    """Calculate and format the cost per kg of H2."""
    if total_kg == 0:
        return "N/A"
    cost_per_kg = total_cost / total_kg
    return f"AUD {cost_per_kg:.2f}/kg"


def hours_to_text(hours: int) -> str:
    """Convert hours to a readable string, e.g. '2 days 4 hours'."""
    days = hours // 24
    remaining = hours % 24
    parts = []
    if days > 0:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if remaining > 0:
        parts.append(f"{remaining} hour{'s' if remaining != 1 else ''}")
    return " ".join(parts) if parts else "0 hours"
