"""
Validation rule implementations for the delivery dataset.

Each rule function accepts a DataFrame and returns a list of Violation
instances. Rules never mutate the DataFrame.

The top-level ``validate()`` function composes all rules and returns a
``ValidationResult``.

Design notes
------------
- Checks are ordered so that missing-column checks run first; per-column
  checks skip silently if the column is absent (already flagged above).
- ``Time_taken (min)`` values in the raw dataset are stored as ``"(24) "``
  (digits in parentheses with a trailing space). Both the parenthesised
  format and plain integers are accepted; anything else is an error.
- Categorical domain checks produce warnings rather than errors because
  the domain list may be incomplete for future data.
"""

import re

import pandas as pd

from validation.result import Severity, ValidationResult, Violation
from validation.schema import (
    CATEGORICAL_DOMAINS,
    COORDINATE_COLUMNS,
    DATE_COLUMNS,
    DELIVERY_TIME_COLUMN,
    EXPECTED_COLUMNS,
    PRIMARY_KEY_COLUMN,
    TIME_COLUMNS,
)

# Matches "(24) " or "(24.5)" — the raw format used in Time_taken (min).
_PAREN_INT_RE = re.compile(r"^\((\d+(?:\.\d+)?)\)\s*$")


# ── Individual checks ─────────────────────────────────────────────────────────


def check_required_columns(df: pd.DataFrame) -> list[Violation]:
    """ERROR if any expected column is absent."""
    missing = [col for col in EXPECTED_COLUMNS if col not in df.columns]
    return [
        Violation(
            check="required_columns",
            column=col,
            detail=f"Required column '{col}' is missing from the dataset.",
            severity=Severity.ERROR,
        )
        for col in missing
    ]


def check_primary_identifier(df: pd.DataFrame) -> list[Violation]:
    """ERROR if the primary key column contains null values."""
    if PRIMARY_KEY_COLUMN not in df.columns:
        return []  # Already caught by check_required_columns.
    null_count = int(df[PRIMARY_KEY_COLUMN].isna().sum())
    if null_count:
        return [
            Violation(
                check="primary_identifier",
                column=PRIMARY_KEY_COLUMN,
                detail=f"{null_count} row(s) have a null primary identifier.",
                severity=Severity.ERROR,
            )
        ]
    return []


def check_coordinates(df: pd.DataFrame) -> list[Violation]:
    """
    ERROR if coordinate values are non-numeric or outside the valid range.

    Checks all four columns defined in COORDINATE_COLUMNS.
    """
    violations: list[Violation] = []
    for col, (min_val, max_val) in COORDINATE_COLUMNS.items():
        if col not in df.columns:
            continue

        numeric = pd.to_numeric(df[col], errors="coerce")

        non_numeric_count = int((numeric.isna() & df[col].notna()).sum())
        if non_numeric_count:
            violations.append(
                Violation(
                    check="coordinate_type",
                    column=col,
                    detail=(
                        f"{non_numeric_count} value(s) in '{col}' cannot be parsed as numeric."
                    ),
                    severity=Severity.ERROR,
                )
            )

        out_of_range = numeric.dropna()
        out_of_range = out_of_range[(out_of_range < min_val) | (out_of_range > max_val)]
        if not out_of_range.empty:
            violations.append(
                Violation(
                    check="coordinate_range",
                    column=col,
                    detail=(
                        f"{len(out_of_range)} value(s) in '{col}' are outside "
                        f"the valid range [{min_val}, {max_val}]."
                    ),
                    severity=Severity.ERROR,
                )
            )
    return violations


def _parse_delivery_time_series(series: pd.Series) -> pd.Series:
    """
    Parse the delivery time column to a numeric Series.

    Handles two observed formats:
    - Plain integer / float string: ``"24"``, ``"24.5"``
    - Parenthesised format from raw Kaggle CSV: ``"(24) "``

    Returns a numeric Series with NaN for values that could not be parsed.
    """
    numeric = pd.to_numeric(series, errors="coerce")

    # Attempt the parenthesised format for values that direct conversion missed.
    paren_mask = numeric.isna() & series.notna()
    if paren_mask.any():

        def _try_paren(val: object) -> float | None:
            m = _PAREN_INT_RE.match(str(val).strip())
            return float(m.group(1)) if m else None

        alt = series[paren_mask].apply(_try_paren)
        numeric = numeric.copy()
        numeric[paren_mask] = alt

    return numeric


def check_delivery_time(df: pd.DataFrame) -> list[Violation]:
    """
    ERROR if delivery time values cannot be parsed or are negative.

    Both ``"24"`` and ``"(24) "`` are accepted. Anything else is an error.
    """
    if DELIVERY_TIME_COLUMN not in df.columns:
        return []

    violations: list[Violation] = []
    raw = df[DELIVERY_TIME_COLUMN]
    numeric = _parse_delivery_time_series(raw)

    unparseable = int((numeric.isna() & raw.notna()).sum())
    if unparseable:
        violations.append(
            Violation(
                check="delivery_time_parseable",
                column=DELIVERY_TIME_COLUMN,
                detail=(
                    f"{unparseable} value(s) in '{DELIVERY_TIME_COLUMN}' cannot be "
                    "parsed as a number. Expected plain integers or '(24) ' format."
                ),
                severity=Severity.ERROR,
            )
        )

    negative_count = int((numeric < 0).sum())
    if negative_count:
        violations.append(
            Violation(
                check="delivery_time_non_negative",
                column=DELIVERY_TIME_COLUMN,
                detail=(
                    f"{negative_count} value(s) in '{DELIVERY_TIME_COLUMN}' are "
                    "negative, which is not a valid delivery duration."
                ),
                severity=Severity.ERROR,
            )
        )
    return violations


def check_date_fields(df: pd.DataFrame) -> list[Violation]:
    """ERROR if date columns contain values that cannot be parsed as a date."""
    violations: list[Violation] = []
    for col in DATE_COLUMNS:
        if col not in df.columns:
            continue
        parsed = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
        unparseable = int((parsed.isna() & df[col].notna()).sum())
        if unparseable:
            violations.append(
                Violation(
                    check="date_parseable",
                    column=col,
                    detail=(f"{unparseable} value(s) in '{col}' cannot be parsed as a date."),
                    severity=Severity.ERROR,
                )
            )
    return violations


def check_time_fields(df: pd.DataFrame) -> list[Violation]:
    """WARNING if time columns contain values that do not match HH:MM or HH:MM:SS."""
    violations: list[Violation] = []
    time_pattern = re.compile(r"^\d{1,2}:\d{2}(:\d{2})?$")
    for col in TIME_COLUMNS:
        if col not in df.columns:
            continue
        non_null = df[col].dropna().astype(str).str.strip()
        invalid_count = int((~non_null.str.match(time_pattern)).sum())
        if invalid_count:
            violations.append(
                Violation(
                    check="time_parseable",
                    column=col,
                    detail=(
                        f"{invalid_count} value(s) in '{col}' do not match the "
                        "expected time format (HH:MM or HH:MM:SS)."
                    ),
                    severity=Severity.WARNING,
                )
            )
    return violations


def check_categorical_domains(df: pd.DataFrame) -> list[Violation]:
    """WARNING if categorical columns contain values outside the known domain."""
    violations: list[Violation] = []
    for col, valid_values in CATEGORICAL_DOMAINS.items():
        if col not in df.columns:
            continue
        non_null = df[col].dropna().astype(str).str.strip()
        unexpected = non_null[~non_null.isin(valid_values)]
        if not unexpected.empty:
            sample = sorted(unexpected.unique().tolist()[:5])
            violations.append(
                Violation(
                    check="categorical_domain",
                    column=col,
                    detail=(
                        f"{len(unexpected)} value(s) in '{col}' are outside the "
                        f"known domain. Sample unexpected values: {sample}."
                    ),
                    severity=Severity.WARNING,
                )
            )
    return violations


# ── Public entry point ────────────────────────────────────────────────────────


def validate(df: pd.DataFrame) -> ValidationResult:
    """
    Run all validation checks against the delivery dataset.

    Column-presence checks run first so that per-column checks can
    safely assume the column exists before inspecting its values.

    Args:
        df: Raw delivery DataFrame loaded from the source CSV.

    Returns:
        A ``ValidationResult`` containing all findings.
    """
    violations: list[Violation] = []
    violations += check_required_columns(df)
    violations += check_primary_identifier(df)
    violations += check_coordinates(df)
    violations += check_delivery_time(df)
    violations += check_date_fields(df)
    violations += check_time_fields(df)
    violations += check_categorical_domains(df)
    return ValidationResult(violations=violations)
