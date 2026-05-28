"""Shared radar array handling helpers for StormDeck scripts.

The ATD/KATD CfRadial files used by the replay prototypes have used both
explicit NetCDF fill values and numeric sentinel values in moment fields. Keep
this policy in one place so previews, replay exports, and 3D renderers do not
silently disagree about which gates are observed data.
"""
from __future__ import annotations

from typing import Any

MISSING_MOMENT_THRESHOLD = -999.0


def masked_numeric_array(var: Any, *, missing_threshold: float = MISSING_MOMENT_THRESHOLD):
    """Return a float64 ndarray with NetCDF masks/fill values/sentinels as NaN.

    The threshold intentionally masks values <= -999.0. That is conservative for
    ATD/KATD radar moments where -999.0 is a censored/missing gate sentinel, while
    avoiding the old divergent behavior where some tools only masked <= -9990.0.
    """
    import numpy as np  # type: ignore

    arr = var[:]
    if np.ma.isMaskedArray(arr):
        out = np.ma.asarray(arr, dtype="float64").filled(np.nan)
    else:
        out = np.asarray(arr, dtype="float64")

    fill = getattr(var, "_FillValue", None)
    if fill is not None:
        try:
            out[out == float(fill)] = np.nan
        except (TypeError, ValueError):
            pass
    out[out <= float(missing_threshold)] = np.nan
    return out
