def _is_nan(value) -> bool:
    try:
        return value != value  # NaN check
    except Exception:
        return False


def format_percent(value, input_is_fraction=None) -> str:
    if value is None or _is_nan(value):
        return ""
    try:
        numeric = float(value)
    except Exception:
        return str(value)

    if input_is_fraction is None:
        is_fraction = numeric <= 1.2
    else:
        is_fraction = bool(input_is_fraction)

    percent = numeric * 100 if is_fraction else numeric
    return f"{percent:.2f}%"


def format_value(value, unit: str) -> str:
    if value is None or _is_nan(value):
        return ""
    try:
        numeric = float(value)
    except Exception:
        return str(value)

    unit_key = (unit or "").lower()
    if unit_key in ("mw", "mwh"):
        return f"{numeric:.2f}"
    if unit_key == "kv":
        return f"{numeric:.2f}"
    if unit_key == "v":
        return f"{numeric:.0f}"
    if unit_key == "kva":
        return f"{numeric:.0f}"
    if unit_key == "mva":
        return f"{numeric:.3f}"
    if unit_key == "hz":
        return f"{numeric:.0f}"
    if unit_key in ("pf",):
        return f"{numeric:.2f}"
    if unit_key in ("%", "percent"):
        return format_percent(numeric)
    return str(value)
