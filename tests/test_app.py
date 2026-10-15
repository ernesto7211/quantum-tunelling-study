import math
import os
import sys

import matplotlib
import pytest

matplotlib.use("Agg")

_ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "src"))

import app  # noqa: E402  (importing must not launch the UI)
from numeric import wavefunction_numeric  # noqa: E402

D = app.DEFAULTS


def test_defaults_validate():
    assert app.validate(D["E_eV"], D["V0_eV"], D["width_nm"]) is None


@pytest.mark.parametrize("E, V0", [(5.0, 5.0), (6.0, 5.0)])
def test_E_ge_V0_gives_warning_message_not_exception(E, V0):
    msg = app.validate(E, V0, 1.0)
    assert isinstance(msg, str) and "below" in msg


def test_compute_results_defaults():
    res = app.compute_results(D["E_eV"], D["V0_eV"], D["width_nm"])
    assert all(math.isfinite(v) for v in res.values())
    assert res["abs_diff"] < 1e-10
    assert res["R"] + res["T_numeric"] == pytest.approx(1.0, abs=1e-10)
    # kappa for 1 eV electron below a 5 eV top: sqrt(2m*4eV)/hbar ~ 10.25 /nm
    assert res["kappa_per_nm"] == pytest.approx(10.246, rel=1e-3)
    assert res["kappa_a"] == pytest.approx(res["kappa_per_nm"] * D["width_nm"])


def test_figures_build_for_defaults():
    import matplotlib.pyplot as plt

    f1 = app.width_curve_figure(D["E_eV"], D["V0_eV"], D["width_nm"])
    f2 = app.wavefunction_figure(D["E_eV"], D["V0_eV"], D["width_nm"])
    f3 = app.wavefunction_figure(D["E_eV"], D["V0_eV"], D["width_nm"], log_scale=True)
    assert f1 is not None and f2 is not None and f3 is not None
    plt.close("all")


def test_wavefunction_continuous_at_edges_and_density_matches_T():
    E, V0, w = D["E_eV"], D["V0_eV"], D["width_nm"]
    eps = 1e-9
    for edge in (0.0, w):
        lo, hi = wavefunction_numeric(E, V0, w, [edge - eps, edge + eps])
        assert abs(lo - hi) < 1e-5
    far = wavefunction_numeric(E, V0, w, [w + 2.0])[0]
    T = app.compute_results(E, V0, w)["T_numeric"]
    assert abs(far) ** 2 == pytest.approx(T, rel=1e-9)


def test_extreme_slider_corners_do_not_crash():
    for E, V0, w in [(0.05, 10.0, 5.0), (9.95, 10.0, 0.05), (0.05, 0.1, 5.0)]:
        assert app.validate(E, V0, w) is None
        app.compute_results(E, V0, w)
        app.width_curve_figure(E, V0, w)
        app.wavefunction_figure(E, V0, w)


def test_figures_from_many_threads_no_exception():
    import threading

    errors = []
    barrier = threading.Barrier(6)

    def worker(i):
        try:
            barrier.wait()
            for j in range(2):
                E = 0.5 + 0.3 * ((i + j) % 6)
                w = 0.2 + 0.4 * ((i * j) % 7)
                png1 = app.figure_to_png_bytes(app.width_curve_figure, E, 5.0, w)
                png2 = app.figure_to_png_bytes(
                    app.wavefunction_figure, E, 5.0, w, log_scale=bool((i + j) % 2))
                assert png1.startswith(b"\x89PNG") and png2.startswith(b"\x89PNG")
        except BaseException as exc:  # noqa: BLE001
            errors.append(repr(exc))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []


def test_app_figures_do_not_use_pyplot_global_state():
    import matplotlib.pyplot as plt

    before = set(plt.get_fignums())
    app.figure_to_png_bytes(app.width_curve_figure, 1.0, 5.0, 1.0)
    app.figure_to_png_bytes(app.wavefunction_figure, 1.0, 5.0, 1.0)
    assert set(plt.get_fignums()) == before
