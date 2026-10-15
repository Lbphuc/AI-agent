"""Package backend.app.modules.analytics.

Phan tich sau 3 cap (Diagnostic, Forecast, Prescriptive) & Mode Pills.
"""
from .availability import compute_availability, resolve_levels
from .diagnostic import run_diagnostic
from .forecast import run_forecast
from .prescriptive import run_prescriptive
from .series import aggregation_policy, infer_frequency, prepare_regular_series, window_compare
from .verify import verify_all_recommendations, verify_recommendation

__all__ = [
    "compute_availability",
    "resolve_levels",
    "run_diagnostic",
    "run_forecast",
    "run_prescriptive",
    "infer_frequency",
    "aggregation_policy",
    "prepare_regular_series",
    "window_compare",
    "verify_recommendation",
    "verify_all_recommendations",
]
