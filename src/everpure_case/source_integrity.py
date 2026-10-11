"""Explicit authoritative-source gate for an approved Phase 1 baseline."""

import argparse
import csv
import hashlib
import json
from decimal import Decimal, InvalidOperation
from pathlib import Path

from everpure_case.config import SOURCE_COLUMNS, SOURCE_RELATIVE_PATH

EXPECTED_SHA256 = "6863ea0014f050355bf9e0c5166e2284edfe8521ea3d87a2a2fa168177a229bc"
EXPECTED_ROWS = 2000
EXPECTED_RECORDED_SPEND_USD = Decimal("2541024291")


class SourceIntegrityError(ValueError):
    """The supplied source does not match the approved baseline."""


def verify_authoritative_source(repo_root: str | Path) -> dict[str, str | int]:
    """Check source bytes, row count, and exact decimal spend independently of the pipeline."""
    path = Path(repo_root).resolve() / SOURCE_RELATIVE_PATH
    actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
    rows = 0
    spend = Decimal(0)
    with path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        if tuple(reader.fieldnames or ()) != SOURCE_COLUMNS:
            raise SourceIntegrityError("Authoritative source column contract changed")
        for rows, row in enumerate(reader, start=1):
            try:
                value = Decimal(row["historical_spend_usd"])
            except (InvalidOperation, TypeError) as exc:
                raise SourceIntegrityError(
                    f"Invalid recorded spend at source data row {rows}"
                ) from exc
            if not value.is_finite():
                raise SourceIntegrityError(f"Non-finite recorded spend at source data row {rows}")
            spend += value

    mismatches = []
    if actual_hash != EXPECTED_SHA256:
        mismatches.append(f"SHA-256 expected {EXPECTED_SHA256}, observed {actual_hash}")
    if rows != EXPECTED_ROWS:
        mismatches.append(f"rows expected {EXPECTED_ROWS}, observed {rows}")
    if spend != EXPECTED_RECORDED_SPEND_USD:
        mismatches.append(
            f"recorded spend expected {EXPECTED_RECORDED_SPEND_USD}, observed {spend}"
        )
    if mismatches:
        raise SourceIntegrityError(
            "Authoritative source integrity failed: " + "; ".join(mismatches)
        )
    return {
        "source_sha256": actual_hash,
        "source_rows": rows,
        "raw_recorded_spend_usd": str(spend),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify the approved Everpure source CSV")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    args = parser.parse_args()
    print(json.dumps(verify_authoritative_source(args.repo_root), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
