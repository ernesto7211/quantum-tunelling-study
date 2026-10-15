import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from analytic import transmission_analytic  # noqa: E402  (allowed in tests only)
from numeric import transmission_numeric  # noqa: E402

# (E_eV, V0_eV, width_nm): 12 varied parameter sets, thin to thick.
SAMPLES = [
    (1.0, 5.0, 0.1),
    (1.0, 5.0, 0.5),
    (1.0, 5.0, 1.0),
    (1.0, 5.0, 2.0),
    (0.5, 1.0, 0.3),
    (0.9, 1.0, 1.0),
    (0.01, 1.0, 0.5),
    (2.0, 10.0, 0.25),
    (4.9, 5.0, 3.0),
    (0.1, 0.3, 5.0),
    (3.0, 4.0, 0.05),
    (1.0, 5.0, 4.0),
]


def test_thin_barrier_T_near_one():
    T, R = transmission_numeric(1.0, 5.0, 1e-6)
    assert 1.0 - T < 1e-6
    assert R < 1e-6


def test_zero_width_is_fully_transmitting():
    T, R = transmission_numeric(1.0, 5.0, 0.0)
    assert T == pytest.approx(1.0, abs=1e-12)
    assert R == pytest.approx(0.0, abs=1e-12)


def test_T_decreases_with_width():
    widths = np.linspace(0.0, 3.0, 61)
    T = np.array([transmission_numeric(1.0, 5.0, w)[0] for w in widths])
    assert np.all(np.diff(T) < 0.0)


@pytest.mark.parametrize("E, V0, w", SAMPLES)
def test_bounds(E, V0, w):
    T, R = transmission_numeric(E, V0, w)
    assert 0.0 <= T <= 1.0
    assert 0.0 <= R <= 1.0


@pytest.mark.parametrize("E, V0, w", SAMPLES)
def test_probability_conservation(E, V0, w):
    T, R = transmission_numeric(E, V0, w)
    assert abs(R + T - 1.0) < 1e-10


def test_agrees_with_analytic_and_report_max_difference():
    abs_diffs, rel_diffs = [], []
    for E, V0, w in SAMPLES:
        Tn, _ = transmission_numeric(E, V0, w)
        Ta = transmission_analytic(E, V0, w)
        abs_diffs.append(abs(Tn - Ta))
        rel_diffs.append(abs(Tn - Ta) / Ta)
    print(
        f"\n[numeric vs analytic] {len(SAMPLES)} sets: "
        f"max abs diff = {max(abs_diffs):.3e}, max rel diff = {max(rel_diffs):.3e}"
    )
    assert len(SAMPLES) >= 10
    assert max(abs_diffs) < 1e-10
    assert max(rel_diffs) < 1e-8


@pytest.mark.parametrize(
    "E, V0, w",
    [(0.0, 5.0, 1.0), (5.0, 5.0, 1.0), (6.0, 5.0, 1.0), (1.0, 5.0, -1.0),
     (float("nan"), 5.0, 1.0)],
)
def test_invalid_inputs_raise(E, V0, w):
    with pytest.raises(ValueError):
        transmission_numeric(E, V0, w)
