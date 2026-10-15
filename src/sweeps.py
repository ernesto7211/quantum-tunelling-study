"""Compare analytic and numeric transmission over a fixed parameter grid.

Run from the project root:  python -m src.sweeps
Writes results/comparison.csv and prints summary statistics.

The grid is fixed in advance (not tuned). Electron mass is used throughout.
"""

import csv
import itertools
import os
import sys

# Allow `python -m src.sweeps`: the sibling modules use flat imports
# (e.g. `from constants import ...`), so put this directory on sys.path.
_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

import numpy as np  # noqa: E402

from analytic import kappa_si, transmission_analytic  # noqa: E402
from constants import ev_to_joule, nm_to_m  # noqa: E402
from numeric import transmission_numeric  # noqa: E402

ENERGIES_EV = [0.1, 0.5, 1.0, 2.0, 4.0]
BARRIER_HEIGHTS_EV = [4.5, 5.0, 6.0, 8.0, 10.0]  # all > max(ENERGIES_EV)
WIDTHS_NM = [0.05, 0.2, 1.0, 3.0, 6.0]

COLUMNS = [
    "E_eV", "V0_eV", "width_nm", "kappa_a",
    "T_analytic", "T_numeric", "abs_error", "rel_error",
]

PROJECT_ROOT = os.path.dirname(_SRC_DIR)
DEFAULT_OUTPUT = os.path.join(PROJECT_ROOT, "results", "comparison.csv")


def run_sweep(output_path=DEFAULT_OUTPUT):
    """Run the full grid, write the CSV, and return the rows as dicts."""
    rows = []
    for E, V0, w in itertools.product(ENERGIES_EV, BARRIER_HEIGHTS_EV, WIDTHS_NM):
        kappa_a = float(kappa_si(ev_to_joule(E), ev_to_joule(V0)) * nm_to_m(w))
        Ta = transmission_analytic(E, V0, w)
        Tn, _R = transmission_numeric(E, V0, w)
        abs_err = abs(Tn - Ta)
        rel_err = abs_err / Ta if Ta > 0.0 else float("nan")
        rows.append({
            "E_eV": E, "V0_eV": V0, "width_nm": w, "kappa_a": kappa_a,
            "T_analytic": Ta, "T_numeric": Tn,
            "abs_error": abs_err, "rel_error": rel_err,
        })

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: repr(v) for k, v in row.items()})
    return rows


def summarize(rows):
    abs_e = np.array([r["abs_error"] for r in rows])
    rel_e = np.array([r["rel_error"] for r in rows])
    worst = rows[int(np.nanargmax(rel_e))]
    return {
        "n": len(rows),
        "max_abs": float(abs_e.max()), "mean_abs": float(abs_e.mean()),
        "max_rel": float(np.nanmax(rel_e)), "mean_rel": float(np.nanmean(rel_e)),
        "max_kappa_a": max(r["kappa_a"] for r in rows),
        "worst_rel_row": worst,
    }


def main():
    rows = run_sweep()
    s = summarize(rows)
    w = s["worst_rel_row"]
    print(f"Combinations:        {s['n']}")
    print(f"Max abs error:       {s['max_abs']:.3e}")
    print(f"Mean abs error:      {s['mean_abs']:.3e}")
    print(f"Max rel error:       {s['max_rel']:.3e}")
    print(f"Mean rel error:      {s['mean_rel']:.3e}")
    print(f"Largest kappa*a:     {s['max_kappa_a']:.3f}")
    print(f"Worst rel error at:  E={w['E_eV']} eV, V0={w['V0_eV']} eV, "
          f"width={w['width_nm']} nm, kappa*a={w['kappa_a']:.3f}, "
          f"T_analytic={w['T_analytic']:.3e}, T_numeric={w['T_numeric']:.3e}")
    n_bad = sum(1 for r in rows if r["rel_error"] > 1e-6)
    print(f"Rows with rel error > 1e-6: {n_bad}")
    print(f"Wrote {DEFAULT_OUTPUT}")


if __name__ == "__main__":
    main()
