import math
import os
import sys
import warnings

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import constants as c  # noqa: E402
from analytic import kappa_si, transmission_analytic  # noqa: E402

E, V0 = 1.0, 5.0  # eV


def kappa_a(E_eV, V0_eV, width_nm):
    k = kappa_si(c.ev_to_joule(E_eV), c.ev_to_joule(V0_eV))
    return k * c.nm_to_m(width_nm)


def test_zero_width_gives_one():
    assert transmission_analytic(E, V0, 0.0) == 1.0


def test_T_approaches_one_as_width_to_zero():
    prev = None
    for w in (1e-2, 1e-4, 1e-6, 1e-8):
        T = transmission_analytic(E, V0, w)
        assert 0.0 < T <= 1.0
        if prev is not None:
            assert T >= prev
        prev = T
    assert 1.0 - transmission_analytic(E, V0, 1e-8) < 1e-12


def test_matches_naive_formula_at_moderate_width():
    w = 0.5
    x = kappa_a(E, V0, w)
    naive = 1.0 / (1.0 + V0**2 * math.sinh(x) ** 2 / (4 * E * (V0 - E)))
    assert transmission_analytic(E, V0, w) == pytest.approx(naive, rel=1e-12)


def test_monotonic_decrease_with_width():
    widths = np.linspace(0.0, 3.0, 301)
    T = transmission_analytic(E, V0, widths)
    assert np.all(np.diff(T) < 0.0)


def test_bounds_over_grid():
    Es = np.linspace(0.01, 4.99, 50)[:, None]
    ws = np.logspace(-6, 3, 60)[None, :]
    T = transmission_analytic(Es, V0, ws)
    assert T.shape == (50, 60)
    assert np.all(T >= 0.0) and np.all(T <= 1.0)
    assert np.all(np.isfinite(T))


@pytest.mark.parametrize("width", [2.0, 3.0, 5.0])
def test_thick_barrier_approximation(width):
    x = kappa_a(E, V0, width)
    assert x > 10  # genuinely thick
    approx = 16 * E * (V0 - E) / V0**2 * math.exp(-2 * x)
    assert transmission_analytic(E, V0, width) == pytest.approx(approx, rel=1e-6)


def test_no_overflow_for_huge_kappa_a():
    # kappa*a ~ 5000 here: naive sinh would overflow (limit ~710).
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        T = transmission_analytic(E, V0, 1000.0)
        arr = transmission_analytic(E, V0, np.array([10.0, 100.0, 1e3, 1e5]))
    assert T == 0.0  # true value ~exp(-10000) underflows double precision
    assert np.all(np.isfinite(arr)) and np.all(arr >= 0.0) and np.all(arr <= 1.0)


def test_log_space_matches_asymptote_where_naive_overflows():
    # kappa*a ~ 400: sinh overflows past ~710 in x, exp(2x) past ~354 here,
    # yet the asymptote exp(-2x) ~ 1e-348 underflows; pick x ~ 150 instead.
    width = 150 / kappa_a(E, V0, 1.0)  # nm giving kappa*a = 150
    x = kappa_a(E, V0, width)
    assert x == pytest.approx(150.0)
    T = transmission_analytic(E, V0, width)
    expected_log = math.log(16 * E * (V0 - E) / V0**2) - 2 * x
    assert math.log(T) == pytest.approx(expected_log, rel=1e-9)


@pytest.mark.parametrize(
    "E_, V_, w",
    [
        (0.0, 5.0, 1.0),
        (-1.0, 5.0, 1.0),
        (5.0, 5.0, 1.0),
        (6.0, 5.0, 1.0),
        (1.0, 5.0, -0.1),
        (float("nan"), 5.0, 1.0),
        (1.0, 5.0, float("nan")),
    ],
)
def test_invalid_inputs_raise(E_, V_, w):
    with pytest.raises(ValueError):
        transmission_analytic(E_, V_, w)


def test_scalar_returns_float():
    assert isinstance(transmission_analytic(E, V0, 1.0), float)
