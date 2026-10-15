"""Generate the six project figures.

Run from the project root:  python -m src.plots
Figures are saved to results/figures/ at dpi 200. Curves come from
analytic.py; numeric.py is overlaid as markers on a sparse subset of points;
figures 5 and 6 read results/comparison.csv (created via sweeps.run_sweep if
it does not exist). Nothing is hard-coded or fabricated.
"""

import csv
import os
import sys

_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from analytic import transmission_analytic  # noqa: E402
from numeric import transmission_numeric  # noqa: E402
from sweeps import DEFAULT_OUTPUT as DEFAULT_CSV, run_sweep  # noqa: E402

PROJECT_ROOT = os.path.dirname(_SRC_DIR)
DEFAULT_FIG_DIR = os.path.join(PROJECT_ROOT, "results", "figures")
DPI = 200

FIGURE_NAMES = [
    "fig1_T_vs_width.png",
    "fig2_T_vs_barrier_height.png",
    "fig3_T_vs_energy.png",
    "fig4_heatmap_log10T.png",
    "fig5_numeric_vs_analytic.png",
    "fig6_numerical_error.png",
]


def _save(fig, outdir, name):
    path = os.path.join(outdir, name)
    fig.tight_layout()
    fig.savefig(path, dpi=DPI)
    plt.close(fig)
    return path


def _numeric_T(E, V0, w):
    return transmission_numeric(E, V0, w)[0]


def fig1_T_vs_width(outdir):
    # Physics: T falls roughly exponentially with width (a straight line on a
    # log axis once kappa*a is large, slope -2*kappa); higher E means smaller
    # kappa, hence slower decay. T -> 1 as width -> 0.
    V0 = 5.0
    w = np.linspace(0.0, 3.0, 400)
    w_pts = np.linspace(0.0, 3.0, 13)
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    for E, color in zip((0.5, 1.0, 2.0), ("C0", "C1", "C2")):
        ax.plot(w, transmission_analytic(E, V0, w), color=color,
                label=f"analytic, E = {E} eV")
        ax.plot(w_pts, [_numeric_T(E, V0, x) for x in w_pts], "o", ms=4,
                mfc="none", color=color)
    ax.plot([], [], "o", mfc="none", color="k", label="numeric (markers)")
    ax.set_yscale("log")
    ax.set_xlabel("Barrier width a (nm)")
    ax.set_ylabel("Transmission probability T (dimensionless)")
    ax.set_title("Tunneling vs barrier width (V0 = 5 eV, electron)")
    ax.legend()
    ax.grid(True, which="both", alpha=0.3)
    return _save(fig, outdir, FIGURE_NAMES[0])


def fig2_T_vs_height(outdir):
    # Physics: a taller barrier increases kappa = sqrt(2m(V0-E))/hbar, so the
    # wavefunction decays faster inside and T drops steeply.
    E, w = 1.0, 1.0
    V0 = np.linspace(1.1, 10.0, 400)
    V0_pts = np.linspace(1.1, 10.0, 15)
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    ax.plot(V0, transmission_analytic(E, V0, w), label="analytic")
    ax.plot(V0_pts, [_numeric_T(E, v, w) for v in V0_pts], "o", ms=4,
            mfc="none", label="numeric (markers)")
    ax.set_yscale("log")
    ax.set_xlabel("Barrier height V0 (eV)")
    ax.set_ylabel("Transmission probability T (dimensionless)")
    ax.set_title("Tunneling vs barrier height (E = 1 eV, a = 1 nm)")
    ax.legend()
    ax.grid(True, which="both", alpha=0.3)
    return _save(fig, outdir, FIGURE_NAMES[1])


def fig3_T_vs_energy(outdir):
    # Physics: higher particle energy shrinks V0-E, so kappa falls and T rises
    # toward 1 as E approaches the barrier top (below-barrier regime only).
    V0, w = 5.0, 1.0
    E = np.linspace(0.05, 4.95, 400)
    E_pts = np.linspace(0.05, 4.95, 15)
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    ax.plot(E, transmission_analytic(E, V0, w), label="analytic")
    ax.plot(E_pts, [_numeric_T(e, V0, w) for e in E_pts], "o", ms=4,
            mfc="none", label="numeric (markers)")
    ax.set_yscale("log")
    ax.set_xlabel("Particle energy E (eV)")
    ax.set_ylabel("Transmission probability T (dimensionless)")
    ax.set_title("Tunneling vs particle energy (V0 = 5 eV, a = 1 nm)")
    ax.legend()
    ax.grid(True, which="both", alpha=0.3)
    return _save(fig, outdir, FIGURE_NAMES[2])


def fig4_heatmap(outdir):
    # Physics: map of log10(T) over energy and width. Contours of constant T
    # follow constant kappa*a: thick barriers and low energies are darkest.
    V0 = 5.0
    E = np.linspace(0.05, 4.95, 200)
    w = np.linspace(0.0, 3.0, 200)
    EE, WW = np.meshgrid(E, w)
    log10T = np.log10(transmission_analytic(EE, V0, WW))
    fig, ax = plt.subplots(figsize=(7, 4.8))
    mesh = ax.pcolormesh(E, w, log10T, shading="auto", cmap="viridis")
    cbar = fig.colorbar(mesh, ax=ax)
    cbar.set_label("log10(T)  (T dimensionless)")
    ax.set_xlabel("Particle energy E (eV)")
    ax.set_ylabel("Barrier width a (nm)")
    ax.set_title("log10 of transmission (V0 = 5 eV, electron)")
    return _save(fig, outdir, FIGURE_NAMES[3])


def _read_comparison(csv_path):
    if not os.path.exists(csv_path):
        run_sweep(csv_path)
    with open(csv_path, newline="") as f:
        rows = list(csv.DictReader(f))
    cols = {k: np.array([float(r[k]) for r in rows]) for k in rows[0]}
    return cols


def fig5_numeric_vs_analytic(outdir, csv_path):
    # Physics/validation: if both methods agree, every point lies on y = x,
    # across ~84 decades of T. Points on the line mean agreement, nothing more
    # (both methods solve the same boundary-value problem).
    d = _read_comparison(csv_path)
    Ta, Tn = d["T_analytic"], d["T_numeric"]
    fig, ax = plt.subplots(figsize=(5.8, 5.4))
    ax.loglog(Ta, Tn, "o", ms=4, alpha=0.7, label="parameter sets")
    lo, hi = min(Ta.min(), Tn.min()), max(Ta.max(), Tn.max())
    ax.loglog([lo, hi], [lo, hi], "k--", lw=1, label="y = x")
    ax.set_xlabel("Analytic transmission T (dimensionless)")
    ax.set_ylabel("Numeric transmission T (dimensionless)")
    ax.set_title(f"Numeric vs analytic transmission ({len(Ta)} cases)")
    ax.legend()
    ax.grid(True, which="both", alpha=0.3)
    return _save(fig, outdir, FIGURE_NAMES[4])


def fig6_error(outdir, csv_path):
    # Physics/numerics: how the numeric-vs-analytic discrepancy depends on
    # barrier opacity kappa*a. Absolute error is bounded by T itself, so it
    # shrinks as T -> 0; relative error shows floating-point round-off.
    # Exact zeros cannot be drawn on a log axis and are omitted (counted in
    # the legend text).
    d = _read_comparison(csv_path)
    ka = d["kappa_a"]
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(6.5, 7), sharex=True)
    for ax, key, label in (
        (ax1, "abs_error", "Absolute error |T_numeric - T_analytic| (dimensionless)"),
        (ax2, "rel_error", "Relative error |T_num - T_ana| / T_ana (dimensionless)"),
    ):
        y = d[key]
        pos = y > 0
        n_zero = int((~pos).sum())
        ax.semilogy(ka[pos], y[pos], "o", ms=4, alpha=0.7,
                    label=f"{int(pos.sum())} nonzero ({n_zero} exact zeros omitted)")
        ax.set_ylabel(label, fontsize=8)
        ax.legend(fontsize=8)
        ax.grid(True, which="both", alpha=0.3)
    ax1.set_title("Numerical error vs barrier opacity")
    ax2.set_xlabel("kappa * a (dimensionless)")
    return _save(fig, outdir, FIGURE_NAMES[5])


def make_all(outdir=DEFAULT_FIG_DIR, csv_path=DEFAULT_CSV):
    os.makedirs(outdir, exist_ok=True)
    return [
        fig1_T_vs_width(outdir),
        fig2_T_vs_height(outdir),
        fig3_T_vs_energy(outdir),
        fig4_heatmap(outdir),
        fig5_numeric_vs_analytic(outdir, csv_path),
        fig6_error(outdir, csv_path),
    ]


def main():
    for p in make_all():
        print("Wrote", p)


if __name__ == "__main__":
    main()
