import csv
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from sweeps import COLUMNS, run_sweep  # noqa: E402


def _read(path):
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        return reader.fieldnames, list(reader)


def test_csv_has_enough_rows_columns_and_no_nan(tmp_path):
    out = tmp_path / "comparison.csv"
    run_sweep(str(out))
    fields, rows = _read(out)

    assert fields == COLUMNS
    assert len(rows) >= 100
    for row in rows:
        for col in COLUMNS:
            val = float(row[col])
            assert not math.isnan(val), f"NaN in {col}"
            assert math.isfinite(val), f"non-finite in {col}"


def test_grid_respects_physical_constraints(tmp_path):
    out = tmp_path / "comparison.csv"
    run_sweep(str(out))
    _, rows = _read(out)
    for row in rows:
        assert 0.0 < float(row["E_eV"]) < float(row["V0_eV"])
        assert float(row["width_nm"]) > 0.0
        assert 0.0 <= float(row["T_analytic"]) <= 1.0
        assert 0.0 <= float(row["T_numeric"]) <= 1.0
