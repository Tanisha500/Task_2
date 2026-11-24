"""Strict validation for patient form inputs and unchanged assignment rows."""

from datetime import date, datetime
import re

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
NUMERIC_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")


def validate_patient(data, *, assignment_date_format=False):
    errors = {}
    for field in ("full_name", "email", "date_of_birth", "glucose", "haemoglobin", "cholesterol"):
        if not str(data.get(field, "")).strip():
            errors[field] = "This field is required."

    email = str(data.get("email", ""))
    if email and not EMAIL_RE.fullmatch(email):
        errors["email"] = "Enter a valid email address (for example, name@example.com)."

    raw_date = str(data.get("date_of_birth", ""))
    if raw_date:
        date_format = "%d.%m.%Y" if assignment_date_format else "%d/%m/%Y"
        expected = "DD.MM.YYYY" if assignment_date_format else "DD/MM/YYYY"
        try:
            parsed = datetime.strptime(raw_date, date_format).date()
            if parsed.strftime(date_format) != raw_date:
                raise ValueError
            if parsed > date.today():
                errors["date_of_birth"] = "Date of birth cannot be in the future."
        except ValueError:
            errors["date_of_birth"] = f"Enter a real date in {expected} format."

    cleaned = {}
    for field in ("glucose", "haemoglobin", "cholesterol"):
        raw = str(data.get(field, ""))
        if raw and not NUMERIC_RE.fullmatch(raw):
            errors[field] = "Enter a numeric value; the supplied value is not changed."
        elif raw:
            cleaned[field] = raw

    if errors:
        return None, errors
    return {
        "full_name": str(data["full_name"]).strip(),
        "date_of_birth": raw_date,
        "email": email.strip(),
        **cleaned,
    }, {}
