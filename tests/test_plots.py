import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from plots import FIGURE_NAMES, make_all  # noqa: E402
from sweeps import run_sweep  # noqa: E402


def test_all_six_figures_created_and_nonempty(tmp_path):
    csv_path = tmp_path / "comparison.csv"
    run_sweep(str(csv_path))
    outdir = tmp_path / "figures"
    make_all(str(outdir), str(csv_path))

    assert len(FIGURE_NAMES) == 6
    for name in FIGURE_NAMES:
        p = outdir / name
        assert p.exists(), name
        assert p.stat().st_size > 0, name
        with open(p, "rb") as f:
            assert f.read(8) == b"\x89PNG\r\n\x1a\n", name
