"""
Validation result types.

These are shared across all validation checks and used by the ingestion
manifest to record what was found.
"""

from dataclasses import dataclass, field
from enum import StrEnum


class Severity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class Violation:
    """A single validation finding."""

    check: str
    detail: str
    severity: Severity
    column: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "check": self.check,
            "column": self.column,
            "detail": self.detail,
            "severity": self.severity.value,
        }


@dataclass
class ValidationResult:
    """Aggregated outcome of all validation checks run against a dataset."""

    violations: list[Violation] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """True when no ERROR-severity violations were found."""
        return not any(v.severity == Severity.ERROR for v in self.violations)

    @property
    def errors(self) -> list[Violation]:
        return [v for v in self.violations if v.severity == Severity.ERROR]

    @property
    def warnings(self) -> list[Violation]:
        return [v for v in self.violations if v.severity == Severity.WARNING]

    def summary(self) -> str:
        if not self.violations:
            return "All checks passed."
        parts = []
        if self.errors:
            parts.append(f"{len(self.errors)} error(s)")
        if self.warnings:
            parts.append(f"{len(self.warnings)} warning(s)")
        return f"Validation completed with {', '.join(parts)}."
