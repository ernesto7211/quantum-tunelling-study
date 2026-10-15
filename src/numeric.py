"""Numerical transmission through a rectangular barrier via boundary matching.

Wavefunctions:
    I   (x < 0):      exp(i k x) + r exp(-i k x)
    II  (0 < x < a):  A exp(kappa x) + B exp(-kappa x)
    III (x > a):      t exp(i k x)

psi and psi' are matched at x = 0 and x = a, giving a 4x4 complex linear
system solved with numpy.linalg.solve. This module is deliberately
independent of analytic.py.

To keep the matrix well conditioned for thick barriers, the unknown A is
rescaled as A' = A exp(kappa a) (the amplitude of the growing term at x = a),
so only exp(-kappa a) <= 1 appears in the matrix.
"""

import numpy as np

from constants import ELECTRON_MASS, HBAR, ev_to_joule, nm_to_m


def _solve_coefficients(E_eV, V0_eV, width_nm):
    """Solve the matching system; return (r, A_scaled, B, t, k, kappa, a) in SI.

    A_scaled = A * exp(kappa a). Raises ValueError for invalid inputs.
    """
    E_eV = float(E_eV)
    V0_eV = float(V0_eV)
    width_nm = float(width_nm)

    if not (np.isfinite(E_eV) and np.isfinite(V0_eV) and np.isfinite(width_nm)):
        raise ValueError("E_eV, V0_eV and width_nm must be finite.")
    if not (0.0 < E_eV < V0_eV):
        raise ValueError("Require 0 < E < V0.")
    if width_nm < 0.0:
        raise ValueError("Barrier width must be non-negative.")

    E = ev_to_joule(E_eV)
    V0 = ev_to_joule(V0_eV)
    a = nm_to_m(width_nm)

    k = np.sqrt(2.0 * ELECTRON_MASS * E) / HBAR
    kappa = np.sqrt(2.0 * ELECTRON_MASS * (V0 - E)) / HBAR

    em = np.exp(-kappa * a)  # exp(-kappa a), in (0, 1]
    eika = np.exp(1j * k * a)

    # Unknown vector: [r, A', B, t], with A = A' exp(-kappa a).
    M = np.array(
        [
            # x=0, psi:   r - A - B = -1
            [1.0, -em, -1.0, 0.0],
            # x=0, psi':  -ik r - kappa A + kappa B = -ik
            [-1j * k, -kappa * em, kappa, 0.0],
            # x=a, psi:   A' + B exp(-kappa a) - t exp(ika) = 0
            [0.0, 1.0, em, -eika],
            # x=a, psi':  kappa A' - kappa B exp(-kappa a) - ik t exp(ika) = 0
            [0.0, kappa, -kappa * em, -1j * k * eika],
        ],
        dtype=complex,
    )
    rhs = np.array([-1.0, -1j * k, 0.0, 0.0], dtype=complex)

    r, A_scaled, B, t = np.linalg.solve(M, rhs)
    return r, A_scaled, B, t, k, kappa, a


def transmission_numeric(E_eV, V0_eV, width_nm):
    """Return (T, R) for a rectangular barrier with 0 < E < V0.

    Inputs are scalars in eV and nm. T = |t|^2 and R = |r|^2.
    Raises ValueError unless 0 < E < V0 and width >= 0 (all finite).
    """
    r, _, _, t, _, _, _ = _solve_coefficients(E_eV, V0_eV, width_nm)
    return float(abs(t) ** 2), float(abs(r) ** 2)


def wavefunction_numeric(E_eV, V0_eV, width_nm, x_nm):
    """Complex wavefunction psi(x) (incident amplitude 1) at positions x_nm.

    Uses the same matched coefficients as transmission_numeric. Region II is
    evaluated as A' exp(kappa (x - a)) + B exp(-kappa x) so exp(kappa x) is
    never formed for thick barriers.
    """
    r, A_s, B, t, k, kappa, a = _solve_coefficients(E_eV, V0_eV, width_nm)
    x = nm_to_m(np.asarray(x_nm, dtype=float))
    psi = np.empty(x.shape, dtype=complex)

    left = x < 0.0
    mid = (x >= 0.0) & (x <= a)
    right = x > a
    psi[left] = np.exp(1j * k * x[left]) + r * np.exp(-1j * k * x[left])
    psi[mid] = A_s * np.exp(kappa * (x[mid] - a)) + B * np.exp(-kappa * x[mid])
    psi[right] = t * np.exp(1j * k * x[right])
    return psi
