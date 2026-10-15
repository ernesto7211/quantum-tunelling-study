"""Physical constants (SI) and unit conversions for the tunneling study.

Values are CODATA 2022. Internally everything is SI (J, m, kg);
eV and nm are only used at the user-facing boundary.
"""

import math

# Exact by definition of the SI (2019 redefinition).
PLANCK_CONSTANT = 6.62607015e-34  # J s
ELEMENTARY_CHARGE = 1.602176634e-19  # C  (also J per eV)

# Derived.
HBAR = PLANCK_CONSTANT / (2.0 * math.pi)  # J s

# Measured (CODATA 2022), relative standard uncertainty ~3e-10.
ELECTRON_MASS = 9.1093837139e-31  # kg

# Conversion factors.
JOULES_PER_EV = ELEMENTARY_CHARGE
METERS_PER_NM = 1.0e-9


def ev_to_joule(energy_ev):
    """Convert energy from eV to J. Works on floats or numpy arrays."""
    return energy_ev * JOULES_PER_EV


def joule_to_ev(energy_j):
    """Convert energy from J to eV. Works on floats or numpy arrays."""
    return energy_j / JOULES_PER_EV


def nm_to_m(length_nm):
    """Convert length from nm to m. Works on floats or numpy arrays."""
    return length_nm * METERS_PER_NM


def m_to_nm(length_m):
    """Convert length from m to nm. Works on floats or numpy arrays."""
    return length_m / METERS_PER_NM
