"""Streamlit app: quantum tunneling through a rectangular barrier.

Run:  python -m streamlit run app.py --server.port 8765
All results come from src/analytic.py and src/numeric.py.
"""

import io
import os
import sys
import threading

_ROOT = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.join(_ROOT, "src")
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

import matplotlib  # noqa: E402

matplotlib.use("Agg")
from matplotlib.figure import Figure  # noqa: E402
import numpy as np  # noqa: E402

from analytic import transmission_analytic  # noqa: E402
from constants import ELECTRON_MASS, HBAR, ev_to_joule  # noqa: E402
from numeric import transmission_numeric, wavefunction_numeric  # noqa: E402

DEFAULTS = {"E_eV": 1.0, "V0_eV": 5.0, "width_nm": 1.0}

# Matplotlib's mathtext parser (used for log-axis tick labels) is not
# thread-safe, and Streamlit may run overlapping script reruns in different
# threads. Hold this lock while building AND rendering any figure. It is
# re-entrant so a builder can be called from inside a locked render.
_MPL_LOCK = threading.RLock()


def render_figure(st_module, builder, *args, **kwargs):
    """Build a figure and render it with st.pyplot under the lock, then free it."""
    with _MPL_LOCK:
        fig = builder(*args, **kwargs)
        try:
            st_module.pyplot(fig)
        finally:
            fig.clear()


def figure_to_png_bytes(builder, *args, **kwargs):
    """Build a figure and draw it to PNG bytes under the lock (used by tests)."""
    with _MPL_LOCK:
        fig = builder(*args, **kwargs)
        try:
            buf = io.BytesIO()
            fig.savefig(buf, format="png")
            return buf.getvalue()
        finally:
            fig.clear()


def validate(E_eV, V0_eV, width_nm):
    """Return an error message string, or None if the inputs are valid."""
    if not E_eV < V0_eV:
        return (f"Energy E = {E_eV:g} eV must be strictly below barrier height "
                f"V0 = {V0_eV:g} eV. This app only models tunneling (0 < E < V0).")
    if E_eV <= 0 or width_nm < 0:
        return "Require E > 0 and width >= 0."
    return None


def compute_results(E_eV, V0_eV, width_nm):
    """Return a dict of displayed quantities (raises ValueError if invalid)."""
    T_a = transmission_analytic(E_eV, V0_eV, width_nm)
    T_n, R = transmission_numeric(E_eV, V0_eV, width_nm)
    kappa_per_m = np.sqrt(2 * ELECTRON_MASS * (ev_to_joule(V0_eV) - ev_to_joule(E_eV))) / HBAR
    kappa_nm = float(kappa_per_m * 1e-9)  # 1/m -> 1/nm
    return {
        "T_analytic": T_a,
        "T_numeric": T_n,
        "abs_diff": abs(T_a - T_n),
        "R": R,
        "kappa_per_nm": kappa_nm,
        "kappa_a": kappa_nm * width_nm,
    }


def width_curve_figure(E_eV, V0_eV, width_nm, w_max=5.0):
    """T vs width (analytic curve) with a marker at the current width."""
    w = np.linspace(0.0, max(w_max, width_nm), 500)
    T = transmission_analytic(E_eV, V0_eV, w)
    T = np.where(T > 0.0, T, np.nan)  # underflowed zeros cannot be drawn on log axis
    fig = Figure(figsize=(6, 4))
    ax = fig.subplots()
    ax.plot(w, T, label="analytic T(a)")
    T_here = transmission_analytic(E_eV, V0_eV, width_nm)
    if T_here > 0.0:
        ax.plot([width_nm], [T_here], "ro", label=f"current a = {width_nm:g} nm")
    ax.set_yscale("log")
    ax.set_xlabel("Barrier width a (nm)")
    ax.set_ylabel("Transmission probability T (dimensionless)")
    ax.set_title(f"T vs width (E = {E_eV:g} eV, V0 = {V0_eV:g} eV)")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend()
    fig.tight_layout()
    return fig


def wavefunction_figure(E_eV, V0_eV, width_nm, log_scale=False, n_points=4000):
    """|psi|^2 across the three regions (incident amplitude 1), barrier shaded."""
    k_nm = np.sqrt(2 * ELECTRON_MASS * ev_to_joule(E_eV)) / HBAR * 1e-9
    wavelength = 2 * np.pi / k_nm
    margin = 2.0 * wavelength
    x = np.linspace(-margin, width_nm + margin, n_points)
    density = np.abs(wavefunction_numeric(E_eV, V0_eV, width_nm, x)) ** 2
    if log_scale:
        density = np.where(density > 0.0, density, np.nan)

    fig = Figure(figsize=(7, 4))
    ax = fig.subplots()
    ax.axvspan(0.0, width_nm, color="orange", alpha=0.25,
               label=f"barrier (V0 = {V0_eV:g} eV, a = {width_nm:g} nm)")
    ax.plot(x, density, color="C0", label=r"$|\psi|^2$")
    ax.axvline(0.0, color="gray", lw=0.8)
    ax.axvline(width_nm, color="gray", lw=0.8)
    if log_scale:
        ax.set_yscale("log")
    ax.set_xlabel("Position x (nm)")
    ax.set_ylabel(r"Probability density $|\psi|^2$ (incident amplitude = 1)")
    ax.set_title(f"Wavefunction density (E = {E_eV:g} eV)")
    ax.legend(loc="upper right", fontsize=8)
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    return fig


PHYSICS_TEXT = """
**Setup.** A particle of mass *m* (here: an electron) and energy *E* approaches a
rectangular barrier of height *V0* and width *a*. With *E < V0* a classical
particle would always bounce back.

**Quantum picture.** Outside the barrier the wavefunction oscillates with
wavenumber *k = sqrt(2mE)/hbar*. Inside it decays as *exp(-kappa x)* with
*kappa = sqrt(2m(V0 - E))/hbar*. Matching the wavefunction and its derivative at
both edges gives the reflection amplitude *r* and transmission amplitude *t*;
then *T = |t|^2* and *R = |r|^2*, with *R + T = 1*.

**Two methods.** *Analytic*: the closed form
*T = [1 + V0^2 sinh^2(kappa a) / (4E(V0 - E))]^-1*, evaluated in log space to avoid
overflow. *Numeric*: the 4x4 boundary-matching linear system solved directly. They
solve the same model, so their agreement checks the algebra and code, not the model.

**Assumptions.** Non-relativistic, one-dimensional, single particle, electron mass,
sharp rectangular barrier, plane-wave incidence from the left, and only the
below-barrier case 0 < E < V0. The density plot uses incident amplitude 1; the
plotted region is a finite window around the barrier. For very thick barriers T may
be below what double precision can represent (it then displays as 0).
"""


def main():
    import streamlit as st

    st.set_page_config(page_title="Quantum tunneling", layout="wide")
    st.title("Quantum tunneling through a rectangular barrier")

    st.sidebar.header("Parameters")
    E = st.sidebar.slider("Particle energy E (eV)", 0.05, 10.0,
                          DEFAULTS["E_eV"], step=0.05)
    V0 = st.sidebar.slider("Barrier height V0 (eV)", 0.1, 10.0,
                           DEFAULTS["V0_eV"], step=0.05)
    width = st.sidebar.slider("Barrier width a (nm)", 0.05, 5.0,
                              DEFAULTS["width_nm"], step=0.05)
    log_density = st.sidebar.checkbox("Log scale for |psi|^2 plot", value=False)

    with st.expander("Physics and assumptions"):
        st.markdown(PHYSICS_TEXT)

    msg = validate(E, V0, width)
    if msg:
        st.warning(msg)
        st.stop()

    res = compute_results(E, V0, width)

    c1, c2, c3 = st.columns(3)
    c1.metric("T (analytic)", f"{res['T_analytic']:.6e}")
    c2.metric("T (numeric)", f"{res['T_numeric']:.6e}")
    c3.metric("|T_analytic - T_numeric|", f"{res['abs_diff']:.3e}")

    c4, c5, c6 = st.columns(3)
    c4.metric("Reflection R", f"{res['R']:.6e}")
    c5.metric("kappa (1/nm)", f"{res['kappa_per_nm']:.4f}")
    c6.metric("kappa * a", f"{res['kappa_a']:.4f}")

    left, right = st.columns(2)
    with left:
        render_figure(st, width_curve_figure, E, V0, width)
    with right:
        render_figure(st, wavefunction_figure, E, V0, width, log_scale=log_density)


if __name__ == "__main__":
    main()
