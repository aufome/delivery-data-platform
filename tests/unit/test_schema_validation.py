"""
Unit tests for validation.rules.

All tests build a minimal valid DataFrame and then introduce a single
defect per test. This keeps each test focused on one rule.
"""

import numpy as np
import pandas as pd

from validation.result import Severity
from validation.rules import (
    check_categorical_domains,
    check_coordinates,
    check_date_fields,
    check_delivery_time,
    check_primary_identifier,
    check_required_columns,
    check_time_fields,
    validate,
)
from validation.schema import EXPECTED_COLUMNS

# ── Helpers ───────────────────────────────────────────────────────────────────


def make_valid_df(rows: int = 5) -> pd.DataFrame:
    """
    Return a minimal DataFrame that passes all validation checks.

    All values are stored as Python objects (strings) so that individual
    tests can introduce a single defect via ``df.loc[0, col] = "bad_value"``
    without pandas raising a TypeError when the column has a float dtype.
    This matches the raw CSV representation (everything is read as strings
    or mixed types with ``low_memory=False``).
    """
    data: dict[str, list[object]] = {
        "ID": [f"RES{i:05d}DEL01" for i in range(rows)],
        "Delivery_person_ID": [f"DEL{i:05d}" for i in range(rows)],
        "Delivery_person_Age": ["25"] * rows,
        "Delivery_person_Ratings": ["4.5"] * rows,
        "Restaurant_latitude": ["12.9716"] * rows,
        "Restaurant_longitude": ["77.5946"] * rows,
        "Delivery_location_latitude": ["12.9816"] * rows,
        "Delivery_location_longitude": ["77.6046"] * rows,
        "Order_Date": ["15-03-2022"] * rows,
        "Time_Orderd": ["10:30"] * rows,
        "Time_Order_picked": ["10:45"] * rows,
        "Weather_conditions": ["Sunny"] * rows,
        "Road_traffic_density": ["Medium"] * rows,
        "Vehicle_condition": ["0"] * rows,
        "Type_of_order": ["Meal"] * rows,
        "Type_of_vehicle": ["motorcycle"] * rows,
        "multiple_deliveries": ["0"] * rows,
        "Festival": ["No"] * rows,
        "City": ["Urban"] * rows,
        "Time_taken (min)": ["(25) "] * rows,
    }
    # Use dtype=object so any test can set a cell to an arbitrary string.
    return pd.DataFrame(data).astype(object)


# ── check_required_columns ────────────────────────────────────────────────────


class TestCheckRequiredColumns:
    def test_valid_df_no_violations(self) -> None:
        df = make_valid_df()
        assert check_required_columns(df) == []

    def test_missing_column_produces_error(self) -> None:
        df = make_valid_df().drop(columns=["Weather_conditions"])
        violations = check_required_columns(df)
        assert len(violations) == 1
        assert violations[0].column == "Weather_conditions"
        assert violations[0].severity == Severity.ERROR

    def test_multiple_missing_columns(self) -> None:
        df = make_valid_df().drop(columns=["Festival", "City"])
        violations = check_required_columns(df)
        missing_cols = {v.column for v in violations}
        assert missing_cols == {"Festival", "City"}

    def test_all_expected_columns_covered(self) -> None:
        """Smoke test: valid df must have all expected columns."""
        df = make_valid_df()
        assert set(EXPECTED_COLUMNS).issubset(set(df.columns))


# ── check_primary_identifier ──────────────────────────────────────────────────


class TestCheckPrimaryIdentifier:
    def test_valid_df_no_violations(self) -> None:
        df = make_valid_df()
        assert check_primary_identifier(df) == []

    def test_null_id_produces_error(self) -> None:
        df = make_valid_df()
        df.loc[0, "ID"] = None
        violations = check_primary_identifier(df)
        assert len(violations) == 1
        assert violations[0].check == "primary_identifier"
        assert violations[0].severity == Severity.ERROR
        assert "1 row(s)" in violations[0].detail

    def test_missing_id_column_returns_empty(self) -> None:
        """Column absence is already caught by check_required_columns."""
        df = make_valid_df().drop(columns=["ID"])
        assert check_primary_identifier(df) == []


# ── check_coordinates ─────────────────────────────────────────────────────────


class TestCheckCoordinates:
    def test_valid_coordinates_no_violations(self) -> None:
        df = make_valid_df()
        assert check_coordinates(df) == []

    def test_latitude_out_of_range_produces_error(self) -> None:
        df = make_valid_df()
        df.loc[0, "Restaurant_latitude"] = 95.0  # > 90
        violations = check_coordinates(df)
        checks = {v.check for v in violations}
        assert "coordinate_range" in checks

    def test_longitude_out_of_range_produces_error(self) -> None:
        df = make_valid_df()
        df.loc[0, "Delivery_location_longitude"] = -190.0  # < -180
        violations = check_coordinates(df)
        checks = {v.check for v in violations}
        assert "coordinate_range" in checks

    def test_non_numeric_coordinate_produces_error(self) -> None:
        df = make_valid_df()
        df.loc[0, "Restaurant_latitude"] = "not_a_number"
        violations = check_coordinates(df)
        checks = {v.check for v in violations}
        assert "coordinate_type" in checks

    def test_missing_column_skipped_silently(self) -> None:
        df = make_valid_df().drop(columns=["Restaurant_latitude"])
        violations = check_coordinates(df)
        cols = {v.column for v in violations}
        assert "Restaurant_latitude" not in cols


# ── check_delivery_time ───────────────────────────────────────────────────────


class TestCheckDeliveryTime:
    def test_paren_format_accepted(self) -> None:
        """'(24) ' format must not produce an error."""
        df = make_valid_df()
        assert check_delivery_time(df) == []

    def test_plain_integer_accepted(self) -> None:
        df = make_valid_df()
        df["Time_taken (min)"] = "24"
        assert check_delivery_time(df) == []

    def test_plain_float_accepted(self) -> None:
        df = make_valid_df()
        df["Time_taken (min)"] = "24.5"
        assert check_delivery_time(df) == []

    def test_unparseable_value_produces_error(self) -> None:
        df = make_valid_df()
        df.loc[0, "Time_taken (min)"] = "bad_value"
        violations = check_delivery_time(df)
        assert any(v.check == "delivery_time_parseable" for v in violations)
        assert all(v.severity == Severity.ERROR for v in violations)

    def test_negative_value_produces_error(self) -> None:
        df = make_valid_df()
        df.loc[0, "Time_taken (min)"] = "-5"
        violations = check_delivery_time(df)
        assert any(v.check == "delivery_time_non_negative" for v in violations)

    def test_missing_column_returns_empty(self) -> None:
        df = make_valid_df().drop(columns=["Time_taken (min)"])
        assert check_delivery_time(df) == []

    def test_nan_values_allowed(self) -> None:
        """NaN delivery times should not be flagged as unparseable."""
        df = make_valid_df()
        df.loc[0, "Time_taken (min)"] = np.nan
        violations = check_delivery_time(df)
        assert not any(v.check == "delivery_time_parseable" for v in violations)


# ── check_date_fields ─────────────────────────────────────────────────────────


class TestCheckDateFields:
    def test_valid_date_no_violations(self) -> None:
        df = make_valid_df()
        assert check_date_fields(df) == []

    def test_unparseable_date_produces_error(self) -> None:
        df = make_valid_df()
        df.loc[0, "Order_Date"] = "not-a-date"
        violations = check_date_fields(df)
        assert len(violations) == 1
        assert violations[0].check == "date_parseable"
        assert violations[0].severity == Severity.ERROR

    def test_nan_date_allowed(self) -> None:
        df = make_valid_df()
        df.loc[0, "Order_Date"] = np.nan
        assert check_date_fields(df) == []


# ── check_time_fields ─────────────────────────────────────────────────────────


class TestCheckTimeFields:
    def test_valid_times_no_violations(self) -> None:
        df = make_valid_df()
        assert check_time_fields(df) == []

    def test_hh_mm_ss_format_accepted(self) -> None:
        df = make_valid_df()
        df["Time_Orderd"] = "10:30:00"
        assert check_time_fields(df) == []

    def test_invalid_time_produces_warning(self) -> None:
        df = make_valid_df()
        df.loc[0, "Time_Orderd"] = "not_a_time"
        violations = check_time_fields(df)
        assert len(violations) == 1
        assert violations[0].severity == Severity.WARNING

    def test_nan_time_allowed(self) -> None:
        df = make_valid_df()
        df.loc[0, "Time_Orderd"] = np.nan
        assert check_time_fields(df) == []


# ── check_categorical_domains ─────────────────────────────────────────────────


class TestCheckCategoricalDomains:
    def test_valid_categories_no_violations(self) -> None:
        df = make_valid_df()
        assert check_categorical_domains(df) == []

    def test_unexpected_weather_produces_warning(self) -> None:
        df = make_valid_df()
        df.loc[0, "Weather_conditions"] = "Hail"
        violations = check_categorical_domains(df)
        assert any(v.column == "Weather_conditions" for v in violations)
        assert all(v.severity == Severity.WARNING for v in violations)

    def test_nan_values_not_flagged(self) -> None:
        df = make_valid_df()
        df.loc[0, "Weather_conditions"] = np.nan
        assert check_categorical_domains(df) == []


# ── validate (full pipeline) ──────────────────────────────────────────────────


class TestValidate:
    def test_valid_df_passes(self) -> None:
        result = validate(make_valid_df())
        assert result.passed
        assert result.errors == []

    def test_result_summary_clean(self) -> None:
        result = validate(make_valid_df())
        assert result.summary() == "All checks passed."

    def test_summary_with_violations(self) -> None:
        df = make_valid_df()
        df.loc[0, "ID"] = None  # triggers error
        df.loc[1, "Weather_conditions"] = "Hail"  # triggers warning
        result = validate(df)
        assert not result.passed
        assert "1 error(s)" in result.summary()
        assert "1 warning(s)" in result.summary()

    def test_errors_and_warnings_separated(self) -> None:
        df = make_valid_df().drop(columns=["City"])  # error
        df.loc[0, "Weather_conditions"] = "Hail"  # warning
        result = validate(df)
        assert len(result.errors) >= 1
        assert len(result.warnings) >= 1
