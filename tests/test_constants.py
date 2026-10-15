import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import constants as c  # noqa: E402


def test_hbar_is_h_over_2pi():
    assert c.HBAR == pytest.approx(c.PLANCK_CONSTANT / (2 * math.pi), rel=1e-15)


def test_hbar_matches_codata_value():
    # CODATA hbar = 1.054571817...e-34 J s
    assert c.HBAR == pytest.approx(1.054571817e-34, rel=1e-9)


def test_electron_mass_and_charge():
    assert c.ELECTRON_MASS == pytest.approx(9.109e-31, rel=1e-3)
    assert c.ELEMENTARY_CHARGE == 1.602176634e-19


def test_one_ev_in_joules():
    assert c.ev_to_joule(1.0) == 1.602176634e-19


def test_one_nm_in_meters():
    assert c.nm_to_m(1.0) == pytest.approx(1e-9, rel=1e-15)


def test_energy_roundtrip():
    for x in (0.0, 1e-3, 1.0, 5.5, 1e3):
        assert c.joule_to_ev(c.ev_to_joule(x)) == pytest.approx(x, rel=1e-14, abs=0)


def test_length_roundtrip():
    for x in (0.0, 0.1, 1.0, 25.0):
        assert c.m_to_nm(c.nm_to_m(x)) == pytest.approx(x, rel=1e-14, abs=0)


def test_array_input():
    np = pytest.importorskip("numpy")
    out = c.nm_to_m(np.array([1.0, 2.0]))
    assert out == pytest.approx([1e-9, 2e-9])


def test_known_scale_electron_1ev_decay_length():
    # Sanity check of constant combination: kappa = sqrt(2 m (1 eV)) / hbar
    # for an electron is ~5.123e9 1/m (about 5.12 per nm).
    kappa = math.sqrt(2 * c.ELECTRON_MASS * c.ev_to_joule(1.0)) / c.HBAR
    assert kappa * 1e-9 == pytest.approx(5.1231, rel=1e-3)
