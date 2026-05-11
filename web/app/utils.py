from datetime import date, datetime
from decimal import Decimal, InvalidOperation


def clean_text(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_bool(value) -> bool:
    return str(value).lower() in {"on", "true", "1", "yes"}


def parse_int(value, field_name: str, allow_none: bool = False) -> int | None:
    text = clean_text(value)
    if text is None:
        if allow_none:
            return None
        raise ValueError(f"{field_name} is required.")
    try:
        return int(text)
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an integer.") from exc


def parse_decimal(value, field_name: str, allow_none: bool = False) -> Decimal | None:
    text = clean_text(value)
    if text is None:
        if allow_none:
            return None
        raise ValueError(f"{field_name} is required.")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise ValueError(f"{field_name} must be a decimal number.") from exc


def parse_date(value, field_name: str, allow_none: bool = False) -> date | None:
    text = clean_text(value)
    if text is None:
        if allow_none:
            return None
        raise ValueError(f"{field_name} is required.")
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError as exc:
        raise ValueError(f"{field_name} must be in YYYY-MM-DD format.") from exc


def parse_datetime_local(value, field_name: str, allow_none: bool = False) -> datetime | None:
    text = clean_text(value)
    if text is None:
        if allow_none:
            return None
        raise ValueError(f"{field_name} is required.")
    for fmt in ("%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(f"{field_name} must be a valid date and time.")


def value_or_dash(value):
    if value is None or value == "":
        return "—"
    return value


def build_options(rows, value_key: str, label_key: str, blank_label: str | None = None):
    options = []
    if blank_label is not None:
        options.append({"value": "", "label": blank_label})
    for row in rows:
        options.append({"value": row[value_key], "label": row[label_key]})
    return options
