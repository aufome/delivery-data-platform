"""
Unit tests for ingestion.manifest.
"""

import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from ingestion.manifest import IngestionManifest, build_manifest, compute_md5
from validation.result import Severity, ValidationResult, Violation

# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_temp_file(content: bytes = b"col1,col2\nval1,val2\n") -> Path:
    """Write content to a temp file and return its Path."""
    tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
    tmp.write(content)
    tmp.close()
    return Path(tmp.name)


FIXED_TS = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)


def _build(
    *,
    local_file: Path,
    validation_result: ValidationResult | None = None,
) -> IngestionManifest:
    return build_manifest(
        local_file=local_file,
        s3_key="raw/delivery_orders/source=zomato/ingestion_date=2024-01-15/delivery_data.csv",
        s3_manifest_key="raw/delivery_orders/source=zomato/ingestion_date=2024-01-15/manifest.json",
        row_count=100,
        column_count=20,
        validation_result=validation_result or ValidationResult(),
        ingestion_timestamp=FIXED_TS,
    )


# ── compute_md5 ───────────────────────────────────────────────────────────────


class TestComputeMd5:
    def test_known_content_matches_expected_hash(self) -> None:
        """MD5 of b'hello' is well-known."""
        import hashlib

        content = b"hello"
        path = _make_temp_file(content)
        try:
            assert compute_md5(path) == hashlib.md5(content).hexdigest()
        finally:
            path.unlink(missing_ok=True)

    def test_different_content_produces_different_hash(self) -> None:
        p1 = _make_temp_file(b"aaa")
        p2 = _make_temp_file(b"bbb")
        try:
            assert compute_md5(p1) != compute_md5(p2)
        finally:
            p1.unlink(missing_ok=True)
            p2.unlink(missing_ok=True)

    def test_same_content_produces_same_hash(self) -> None:
        p1 = _make_temp_file(b"abc")
        p2 = _make_temp_file(b"abc")
        try:
            assert compute_md5(p1) == compute_md5(p2)
        finally:
            p1.unlink(missing_ok=True)
            p2.unlink(missing_ok=True)


# ── build_manifest ────────────────────────────────────────────────────────────


class TestBuildManifest:
    def setup_method(self) -> None:
        self.tmp = _make_temp_file()

    def teardown_method(self) -> None:
        self.tmp.unlink(missing_ok=True)

    def test_source_file_name_set(self) -> None:
        m = _build(local_file=self.tmp)
        assert m.source_file == self.tmp.name

    def test_ingestion_timestamp_iso_format(self) -> None:
        m = _build(local_file=self.tmp)
        assert m.ingestion_timestamp == "2024-01-15T10:30:00Z"

    def test_ingestion_date_matches_timestamp(self) -> None:
        m = _build(local_file=self.tmp)
        assert m.ingestion_date == "2024-01-15"

    def test_row_column_counts(self) -> None:
        m = _build(local_file=self.tmp)
        assert m.row_count == 100
        assert m.column_count == 20

    def test_file_size_bytes(self) -> None:
        m = _build(local_file=self.tmp)
        assert m.file_size_bytes == self.tmp.stat().st_size

    def test_md5_checksum_is_hex_string(self) -> None:
        m = _build(local_file=self.tmp)
        assert len(m.md5_checksum) == 32
        assert all(c in "0123456789abcdef" for c in m.md5_checksum)

    def test_s3_keys_stored(self) -> None:
        m = _build(local_file=self.tmp)
        assert "delivery_data.csv" in m.s3_key
        assert "manifest.json" in m.s3_manifest_key

    def test_validation_passed_true_when_no_errors(self) -> None:
        result = ValidationResult()
        m = _build(local_file=self.tmp, validation_result=result)
        assert m.validation_passed is True
        assert m.validation_error_count == 0
        assert m.validation_warning_count == 0

    def test_validation_passed_false_when_errors(self) -> None:
        result = ValidationResult(
            violations=[
                Violation(
                    check="required_columns",
                    column="ID",
                    detail="Missing column.",
                    severity=Severity.ERROR,
                )
            ]
        )
        m = _build(local_file=self.tmp, validation_result=result)
        assert m.validation_passed is False
        assert m.validation_error_count == 1

    def test_violations_serialised_to_list_of_dicts(self) -> None:
        result = ValidationResult(
            violations=[
                Violation(
                    check="coordinate_range",
                    column="Restaurant_latitude",
                    detail="Out of range.",
                    severity=Severity.WARNING,
                )
            ]
        )
        m = _build(local_file=self.tmp, validation_result=result)
        assert isinstance(m.validation_violations, list)
        assert m.validation_violations[0]["check"] == "coordinate_range"


# ── IngestionManifest serialisation ───────────────────────────────────────────


class TestIngestionManifestSerialisation:
    def setup_method(self) -> None:
        self.tmp = _make_temp_file()
        self.manifest = _build(local_file=self.tmp)

    def teardown_method(self) -> None:
        self.tmp.unlink(missing_ok=True)

    def test_to_dict_returns_dict(self) -> None:
        d = self.manifest.to_dict()
        assert isinstance(d, dict)
        assert "source_name" in d
        assert "ingestion_timestamp" in d

    def test_to_json_is_valid_json(self) -> None:
        raw = self.manifest.to_json()
        parsed = json.loads(raw)
        assert parsed["ingestion_date"] == "2024-01-15"

    def test_to_json_round_trips(self) -> None:
        d1 = self.manifest.to_dict()
        d2 = json.loads(self.manifest.to_json())
        assert d1 == d2
