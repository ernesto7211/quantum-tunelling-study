"""Analytic transmission through a rectangular barrier (0 < E < V0).

T = [1 + V0^2 sinh^2(kappa a) / (4 E (V0 - E))]^-1,
kappa = sqrt(2 m (V0 - E)) / hbar.

User-facing inputs are eV and nm; the computation is done in SI.
"""

import numpy as np

from constants import ELECTRON_MASS, HBAR, ev_to_joule, nm_to_m


def kappa_si(E_J, V0_J, mass=ELECTRON_MASS):
    """Decay constant inside the barrier, in 1/m (SI inputs)."""
    return np.sqrt(2.0 * mass * (V0_J - E_J)) / HBAR


def transmission_analytic(E_eV, V0_eV, width_nm):
    """Exact transmission probability for a rectangular barrier, 0 < E < V0.

    Parameters are in eV and nm; scalars or numpy arrays (broadcast together).
    Returns a float for scalar input, otherwise an ndarray.

    Raises ValueError if E is not strictly between 0 and V0, or if the
    width is negative (or any input is non-finite).
    """
    E_eV = np.asarray(E_eV, dtype=float)
    V0_eV = np.asarray(V0_eV, dtype=float)
    width_nm = np.asarray(width_nm, dtype=float)

    if not (np.all(np.isfinite(E_eV)) and np.all(np.isfinite(V0_eV))
            and np.all(np.isfinite(width_nm))):
        raise ValueError("E_eV, V0_eV and width_nm must be finite.")
    if not np.all((E_eV > 0.0) & (E_eV < V0_eV)):
        raise ValueError("Require 0 < E < V0.")
    if np.any(width_nm < 0.0):
        raise ValueError("Barrier width must be non-negative.")

    E = ev_to_joule(E_eV)
    V0 = ev_to_joule(V0_eV)
    a = nm_to_m(width_nm)

    x = kappa_si(E, V0) * a  # dimensionless kappa * a, >= 0

    # sinh^2(x) * V0^2 / (4E(V0-E)) = A * exp(2x) * (1 - exp(-2x))^2,
    # with A = V0^2 / (16 E (V0-E)). Work with the logarithm of this term
    # so exp(2x) is never formed.
    log_A = np.log(V0 * V0 / (16.0 * E * (V0 - E)))
    x_pos = np.where(x > 0.0, x, 1.0)  # dummy value avoids log(0) at x == 0
    with np.errstate(divide="ignore"):
        # log(1 - exp(-2x)) = log(-expm1(-2x)), accurate for small x too.
        log_term = log_A + 2.0 * x_pos + 2.0 * np.log(-np.expm1(-2.0 * x_pos))
    log_term = np.where(x > 0.0, log_term, -np.inf)

    T = np.exp(-np.logaddexp(0.0, log_term))
    T = np.clip(T, 0.0, 1.0)
    return float(T) if T.ndim == 0 else T
