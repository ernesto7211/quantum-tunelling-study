"""Build the technical report as an editable Word document.

Run from the project root:  python -m src.make_report
Output: report/quantum_tunneling_report.docx

Every number quoted in the report is computed here from results/comparison.csv,
from the project's analytic/numeric functions, from src/constants.py, or from
running pytest. Nothing is typed in by hand. Each value is recorded with its
source and a provenance list is printed at the end.

Only the parameter choices for the illustrative cases (TREND_* and THICK_CASES
below) are set by hand; they are inputs, not results.
"""

import csv
import math
import os
import re
import subprocess
import sys

_SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if _SRC_DIR not in sys.path:
    sys.path.insert(0, _SRC_DIR)

import datetime  # noqa: E402

import numpy as np  # noqa: E402
from docx import Document  # noqa: E402
from docx.enum.table import WD_TABLE_ALIGNMENT  # noqa: E402
from docx.enum.text import WD_ALIGN_PARAGRAPH  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402
from docx.shared import Inches, Pt, RGBColor  # noqa: E402

import constants as C  # noqa: E402
import sweeps  # noqa: E402
from analytic import kappa_si, transmission_analytic  # noqa: E402
from numeric import transmission_numeric  # noqa: E402

PROJECT_ROOT = os.path.dirname(_SRC_DIR)
CSV_PATH = os.path.join(PROJECT_ROOT, "results", "comparison.csv")
FIG_DIR = os.path.join(PROJECT_ROOT, "results", "figures")
OUT_PATH = os.path.join(PROJECT_ROOT, "report", "quantum_tunneling_report.docx")

TITLE = "Computational Investigation of Quantum Tunneling Through Finite Potential Barriers"

# Hand-chosen illustrative cases (inputs, not results).
TREND_V0_WIDTH = 5.0
TREND_ENERGIES = (0.5, 1.0, 2.0)
TREND_WIDTHS = (0.5, 1.0, 2.0, 3.0)
TREND_HEIGHT = {"E": 1.0, "w": 1.0, "V0": (1.1, 2.0, 5.0, 10.0)}
TREND_ENERGY = {"V0": 5.0, "w": 1.0, "E": (0.05, 1.0, 2.5, 4.95)}
THICK_CASES = [(1.0, 5.0, 2.0), (1.0, 5.0, 1.0), (1.0, 5.0, 0.5), (1.0, 5.0, 0.2)]

FIGURES = [
    ("fig1_T_vs_width.png", 4.4),
    ("fig2_T_vs_barrier_height.png", 4.4),
    ("fig3_T_vs_energy.png", 4.4),
    ("fig4_heatmap_log10T.png", 4.6),
    ("fig5_numeric_vs_analytic.png", 3.6),
    ("fig6_numerical_error.png", 3.4),
]

# ----------------------------------------------------------------------------
# Provenance recording
# ----------------------------------------------------------------------------
PROVENANCE = []  # (description, plain value, source)
_seen = set()


def _record(desc, plain, source):
    if desc not in _seen:
        _seen.add(desc)
        PROVENANCE.append((desc, plain, source))


def _sci_markup(x, digits=3):
    """Scientific notation as 'm×10^{e}' markup (for the document)."""
    if x == 0:
        return "0"
    m, e = f"{x:.{digits - 1}e}".split("e")
    return f"{m}×10^{{{int(e)}}}".replace("-", "−")


def fact(desc, value, source, kind="sci", digits=3):
    """Format a value for the document and record it with its source."""
    if kind == "sci":
        out = _sci_markup(value, digits)
        plain = f"{value:.{digits - 1}e}"
    elif kind == "int":
        out = f"{int(value)}"
        plain = out
    elif kind == "fix":
        out = f"{value:.{digits}f}".replace("-", "−")
        plain = f"{value:.{digits}f}"
    elif kind == "pctsci":
        out = _sci_markup(value, digits) + "%"
        plain = f"{value:.{digits - 1}e}%"
    elif kind == "pct":
        out = f"{value:.{digits}f}".replace("-", "−") + "%"
        plain = f"{value:.{digits}f}%"
    elif kind == "g":
        out = f"{value:.{digits}g}".replace("-", "−")
        plain = f"{value:.{digits}g}"
    else:
        raise ValueError(kind)
    _record(desc, plain, source)
    return out


# ----------------------------------------------------------------------------
# Data and computed facts
# ----------------------------------------------------------------------------
def read_comparison():
    with open(CSV_PATH, newline="") as f:
        rows = list(csv.DictReader(f))
    return {k: np.array([float(r[k]) for r in rows]) for k in rows[0]}


def Ta(E, V0, w):
    return transmission_analytic(E, V0, w)


def kappa_nm(E, V0):
    return float(kappa_si(C.ev_to_joule(E), C.ev_to_joule(V0))) * 1e-9


def thick_approx(E, V0, w):
    return 16 * E * (V0 - E) / V0**2 * math.exp(-2 * kappa_nm(E, V0) * w)


def thick_pct_decimal(E, V0, w):
    """(approx - exact)/exact * 100 in 60-digit decimal arithmetic.

    In double precision this difference is below round-off once kappa*a is
    above ~10, so it is evaluated with the decimal module. kappa*a is taken
    from the double-precision calculation; E and V0 are exact decimals.
    """
    from decimal import Decimal, getcontext

    getcontext().prec = 60
    x = Decimal(kappa_nm(E, V0) * w)
    Ed, Vd = Decimal(str(E)), Decimal(str(V0))
    sinh = (x.exp() - (-x).exp()) / 2
    exact = 1 / (1 + Vd * Vd * sinh * sinh / (4 * Ed * (Vd - Ed)))
    approx = 16 * Ed * (Vd - Ed) / (Vd * Vd) * (-2 * x).exp()
    return float((approx - exact) / exact * 100)


def count_tests():
    """Collect and run pytest; return (per-file counts, total collected, summary line)."""
    env = dict(os.environ)
    col = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=PROJECT_ROOT, capture_output=True, text=True, env=env)
    per_file = {}
    for line in col.stdout.splitlines():
        if "::" in line:
            fname = line.split("::")[0].replace("\\", "/")
            per_file[fname] = per_file.get(fname, 0) + 1
    run = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"],
        cwd=PROJECT_ROOT, capture_output=True, text=True, env=env)
    summary = [ln for ln in run.stdout.splitlines() if re.search(r"\d+ (passed|failed)", ln)]
    summary = summary[-1].strip("= ").strip() if summary else "pytest summary not found"
    return per_file, sum(per_file.values()), summary


def compute_facts():
    F = {}
    d = read_comparison()
    src = "results/comparison.csv"
    n = len(d["E_eV"])
    F["n"] = fact("number of sweep combinations", n, src, "int")
    for key, col, label in (("E", "E_eV", "E (eV)"), ("V0", "V0_eV", "V0 (eV)"),
                            ("w", "width_nm", "width (nm)")):
        F[f"{key}_min"] = fact(f"min {label}", d[col].min(), src, "g", 3)
        F[f"{key}_max"] = fact(f"max {label}", d[col].max(), src, "g", 3)
    F["ka_min"] = fact("min kappa*a", d["kappa_a"].min(), src, "fix", 3)
    F["ka_max"] = fact("max kappa*a", d["kappa_a"].max(), src, "fix", 2)
    F["rel_min"] = fact("min nonzero relative error", d["rel_error"][d["rel_error"] > 0].min(), src)
    F["ratio_max"] = fact("max E/V0 in sweep", (d["E_eV"] / d["V0_eV"]).max(), src + " (computed)", "fix", 2)
    F["T_min"] = fact("min T_analytic in sweep", d["T_analytic"].min(), src)
    F["T_max"] = fact("max T_analytic in sweep", d["T_analytic"].max(), src)
    F["T_decades"] = fact("decades of T spanned by sweep (log10 max/min)",
                          math.log10(d["T_analytic"].max() / d["T_analytic"].min()),
                          src + " (computed)", "fix", 1)
    ab, rel = d["abs_error"], d["rel_error"]
    F["abs_max"] = fact("max absolute error", ab.max(), src)
    F["abs_mean"] = fact("mean absolute error", ab.mean(), src)
    F["rel_max"] = fact("max relative error", rel.max(), src)
    F["rel_mean"] = fact("mean relative error", rel.mean(), src)
    F["n_zero"] = fact("rows with exactly zero absolute error", int((ab == 0).sum()), src, "int")
    i = int(np.argmax(rel))
    F["w_E"] = fact("worst-case row: E (eV)", d["E_eV"][i], src, "g")
    F["w_V0"] = fact("worst-case row: V0 (eV)", d["V0_eV"][i], src, "g")
    F["w_w"] = fact("worst-case row: width (nm)", d["width_nm"][i], src, "g")
    F["w_ka"] = fact("worst-case row: kappa*a", d["kappa_a"][i], src, "fix", 2)
    F["w_Ta"] = fact("worst-case row: T_analytic", d["T_analytic"][i], src, "sci", 4)
    F["w_Tn"] = fact("worst-case row: T_numeric", d["T_numeric"][i], src, "sci", 4)
    F["w_rel"] = fact("worst-case row: relative error", rel[i], src)
    F["w_abs"] = fact("worst-case row: absolute error", ab[i], src)

    ka = d["kappa_a"]
    bins = [("lt10", ka < 10, "kappa*a < 10"),
            ("mid", (ka >= 10) & (ka < 50), "10 <= kappa*a < 50"),
            ("ge50", ka >= 50, "kappa*a >= 50")]
    for key, mask, label in bins:
        F[f"bin_{key}_n"] = fact(f"rows with {label}", int(mask.sum()), src, "int")
        F[f"bin_{key}_med"] = fact(f"median relative error, {label}", np.median(rel[mask]), src)
        F[f"bin_{key}_max"] = fact(f"max relative error, {label}", rel[mask].max(), src)

    # R + T = 1 for the numeric solver on the sweep grid
    dev = 0.0
    for E, V0, w in zip(d["E_eV"], d["V0_eV"], d["width_nm"]):
        T, R = transmission_numeric(E, V0, w)
        dev = max(dev, abs(T + R - 1.0))
    F["RT_dev"] = fact("max |R+T-1| (numeric, over the 125 sweep rows)", dev,
                       "transmission_numeric on rows of comparison.csv")

    # Constants
    F["hbar"] = fact("hbar (J s)", C.HBAR, "src/constants.py", "sci", 9)
    F["me"] = fact("electron mass (kg)", C.ELECTRON_MASS, "src/constants.py", "sci", 11)
    F["e"] = fact("elementary charge (C)", C.ELEMENTARY_CHARGE, "src/constants.py", "sci", 10)
    F["h"] = fact("Planck constant (J s)", C.PLANCK_CONSTANT, "src/constants.py", "sci", 9)

    # Trend: T vs width
    V0 = TREND_V0_WIDTH
    src_a = "src/analytic.py:transmission_analytic"
    for E in TREND_ENERGIES:
        k = kappa_nm(E, V0)
        F[f"kap_E{E}"] = fact(f"kappa (1/nm), E={E} eV, V0={V0} eV", k, "src/constants.py + formula", "fix", 3)
        for w in TREND_WIDTHS:
            F[f"Tw_E{E}_w{w}"] = fact(f"T at E={E} eV, V0={V0} eV, a={w} nm", Ta(E, V0, w), src_a)
        slope = math.log(Ta(E, V0, 2.0)) - math.log(Ta(E, V0, 1.0))  # per 1 nm
        F[f"slope_E{E}"] = fact(f"d lnT/da between 1 and 2 nm (1/nm), E={E} eV", slope, src_a + " (computed)", "fix", 2)
        F[f"m2k_E{E}"] = fact(f"-2*kappa (1/nm), E={E} eV", -2 * k, "formula", "fix", 2)
        F[f"dec_E{E}"] = fact(f"decades of T lost per nm between 1 and 2 nm, E={E} eV",
                              -slope / math.log(10), src_a + " (computed)", "fix", 2)
    wgrid = np.linspace(0.0, 3.0, 301)
    mono = all(np.all(np.diff(Ta(E, V0, wgrid)) < 0) for E in TREND_ENERGIES)
    F["mono_w"] = "strictly decreasing" if mono else "NOT monotonic"
    _record("T strictly decreasing with width on 301-point grid (all 3 energies)", str(mono), src_a)

    # Trend: T vs height
    h = TREND_HEIGHT
    for v in h["V0"]:
        F[f"Th_{v}"] = fact(f"T at V0={v} eV (E={h['E']} eV, a={h['w']} nm)", Ta(h["E"], v, h["w"]), src_a)
    F["h_decades"] = fact("decades of T lost from V0=1.1 to 10 eV",
                          math.log10(Ta(h["E"], 1.1, h["w"]) / Ta(h["E"], 10.0, h["w"])),
                          src_a + " (computed)", "fix", 1)
    for v in (1.5, 8.0):
        dl = (math.log10(Ta(h["E"], v + 0.05, h["w"])) - math.log10(Ta(h["E"], v - 0.05, h["w"]))) / 0.1
        F[f"hs_{v}"] = fact(f"d log10 T / dV0 at V0={v} eV (per eV)", dl, src_a + " (central difference)", "fix", 2)
    vgrid = np.linspace(1.1, 10.0, 400)
    F["mono_h"] = "strictly decreasing" if np.all(np.diff(Ta(h["E"], vgrid, h["w"])) < 0) else "NOT monotonic"
    _record("T strictly decreasing with V0 on 400-point grid", F["mono_h"], src_a)

    # Trend: T vs energy
    en = TREND_ENERGY
    for e_ in en["E"]:
        F[f"Te_{e_}"] = fact(f"T at E={e_} eV (V0={en['V0']} eV, a={en['w']} nm)", Ta(e_, en["V0"], en["w"]), src_a)
    F["e_decades"] = fact("decades of T gained from E=0.05 to 4.95 eV",
                          math.log10(Ta(4.95, en["V0"], en["w"]) / Ta(0.05, en["V0"], en["w"])),
                          src_a + " (computed)", "fix", 1)
    for e_, step in ((0.1, 0.01), (2.5, 0.05), (4.9, 0.01)):
        dl = (math.log10(Ta(e_ + step, en["V0"], en["w"])) - math.log10(Ta(e_ - step, en["V0"], en["w"]))) / (2 * step)
        F[f"es_{e_}"] = fact(f"d log10 T / dE at E={e_} eV (per eV)", dl, src_a + " (central difference)", "fix", 2)
    egrid = np.linspace(0.05, 4.95, 400)
    F["mono_e"] = "strictly increasing" if np.all(np.diff(Ta(egrid, en["V0"], en["w"])) > 0) else "NOT monotonic"
    _record("T strictly increasing with E on 400-point grid", F["mono_e"], src_a)

    # Heatmap
    E_h = np.linspace(0.05, 4.95, 200)
    w_h = np.linspace(0.0, 3.0, 200)
    EE, WW = np.meshgrid(E_h, w_h)
    L = np.log10(Ta(EE, 5.0, WW))
    j = np.unravel_index(np.argmin(L), L.shape)
    F["hm_min"] = fact("min log10(T) on heatmap grid", L.min(), src_a + " (200x200 grid as in plots.py)", "fix", 1)
    F["hm_min_E"] = fact("heatmap minimum at E (eV)", E_h[j[1]], "computed", "fix", 2)
    F["hm_min_w"] = fact("heatmap minimum at width (nm)", w_h[j[0]], "computed", "fix", 2)
    F["hm_max"] = fact("max log10(T) on heatmap grid", L.max(), src_a, "fix", 1)
    F["hm_Ehi_w3"] = fact("log10 T at E=4.95 eV, a=3 nm, V0=5 eV", math.log10(Ta(4.95, 5.0, 3.0)), src_a, "fix", 1)
    F["hm_Elo_w3"] = fact("log10 T at E=0.05 eV, a=3 nm, V0=5 eV", math.log10(Ta(0.05, 5.0, 3.0)), src_a, "fix", 1)

    # Thick-barrier approximation
    thick = []
    for E, V0_, w in THICK_CASES:
        ka_ = kappa_nm(E, V0_) * w
        ex, ap = Ta(E, V0_, w), thick_approx(E, V0_, w)
        tag = f"E={E}, V0={V0_}, a={w}"
        thick.append({
            "tag": tag,
            "ka": fact(f"kappa*a ({tag})", ka_, "computed", "fix", 2),
            "exact": fact(f"T exact ({tag})", ex, src_a, "sci", 4),
            "approx": fact(f"T thick approx ({tag})", ap, "16E(V0-E)/V0^2 exp(-2ka)", "sci", 4),
            "pct": fact(f"percent difference approx vs exact ({tag})",
                        thick_pct_decimal(E, V0_, w),
                        "computed in 60-digit decimal arithmetic", "pctsci", 3),
        })
    F["thick"] = thick
    raw = [thick_pct_decimal(E, V0_, w) for E, V0_, w in THICK_CASES]
    assert all(x > 0 for x in raw), "thick approx does not overestimate in every case; fix report text"
    assert all(raw[i] < raw[i + 1] for i in range(len(raw) - 1)), \
        "difference not monotonic in kappa*a; fix report text"
    assert "NOT" not in F["mono_w"] + F["mono_h"] + F["mono_e"], \
        "monotonicity claim fails; fix report text"
    F["ovf"] = fact("kappa*a at which sinh^2 overflows in double precision",
                    0.5 * (math.log(4.0) + math.log(sys.float_info.max)),
                    "sys.float_info.max (computed)", "fix", 0)

    # Underflow limit
    k = kappa_nm(1.0, 5.0)
    lo, hi = 300 / k, 400 / k
    for _ in range(100):
        mid = (lo + hi) / 2
        if Ta(1.0, 5.0, mid) > 0:
            lo = mid
        else:
            hi = mid
    F["uf_w"] = fact("narrowest width where T_analytic == 0 (E=1, V0=5), nm", hi, "bisection on transmission_analytic", "fix", 1)
    F["uf_ka"] = fact("kappa*a at that width", hi * k, "computed", "fix", 0)
    F["uf_T_just"] = fact("smallest nonzero T_analytic just below it", Ta(1.0, 5.0, lo), src_a, "sci", 3)
    for x in (300.0, 360.0):
        w = x / k
        a_, n_ = Ta(1.0, 5.0, w), transmission_numeric(1.0, 5.0, w)[0]
        F[f"uf_a_{int(x)}"] = fact(f"T_analytic at kappa*a={int(x)} (E=1,V0=5)", a_, src_a, "sci", 5)
        F[f"uf_n_{int(x)}"] = fact(f"T_numeric at kappa*a={int(x)} (E=1,V0=5)", n_, "src/numeric.py", "sci", 5)
    wbig = 400.0 / k
    F["uf_n_400"] = fact("T_numeric at kappa*a=400 (E=1,V0=5)", transmission_numeric(1.0, 5.0, wbig)[0], "src/numeric.py", "sci", 3)
    F["uf_a_400"] = fact("T_analytic at kappa*a=400 (E=1,V0=5)", Ta(1.0, 5.0, wbig), src_a, "sci", 3)

    # Tests
    per_file, total, summary = count_tests()
    F["tests_total"] = fact("tests collected by pytest", total, "pytest --collect-only", "int")
    F["tests_files"] = per_file
    F["tests_summary"] = summary
    _record("pytest run summary", summary, "pytest -q")
    for fname, c in sorted(per_file.items()):
        _record(f"tests in {fname}", str(c), "pytest --collect-only")
    return F


# ----------------------------------------------------------------------------
# Word helpers
# ----------------------------------------------------------------------------
_TOKEN = re.compile(r"(\^\{[^}]*\}|_\{[^}]*\})")
FONT = "Times New Roman"


def add_rich(par, text, size=None, bold=False, italic=False):
    """Add text to a paragraph; supports ^{sup} and _{sub} markup."""
    for tok in _TOKEN.split(text):
        if not tok:
            continue
        sup = tok.startswith("^{")
        sub = tok.startswith("_{")
        body = tok[2:-1] if (sup or sub) else tok
        run = par.add_run(body)
        run.bold = bold
        run.italic = italic
        run.font.superscript = sup
        run.font.subscript = sub
        if size:
            run.font.size = Pt(size)
    return par


def setup_document():
    doc = Document()
    sec = doc.sections[0]
    sec.page_width, sec.page_height = Inches(8.5), Inches(11)
    for side in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, side, Inches(1))
    normal = doc.styles["Normal"]
    normal.font.name = FONT
    normal.font.size = Pt(11)
    normal.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.space_before = Pt(0)
    normal.paragraph_format.line_spacing = 1.0
    for name, size in (("Heading 1", 13), ("Heading 2", 11)):
        st = doc.styles[name]
        st.font.name = FONT
        st.font.size = Pt(size)
        st.font.bold = True
        st.font.color.rgb = RGBColor(0, 0, 0)
        st.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
        st.element.rPr.rFonts.set(qn("w:ascii"), FONT)
        st.element.rPr.rFonts.set(qn("w:hAnsi"), FONT)
        st.paragraph_format.space_before = Pt(10)
        st.paragraph_format.space_after = Pt(4)
        st.paragraph_format.keep_with_next = True
    return doc


def H1(doc, text):
    return doc.add_heading(text, level=1)


def H2(doc, text):
    return doc.add_heading(text, level=2)


def P(doc, text, **kw):
    par = doc.add_paragraph()
    add_rich(par, text, **kw)
    par.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    return par


def EQ(doc, text, num):
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    par.paragraph_format.space_after = Pt(4)
    add_rich(par, text + f"        ({num})")
    return par


def BULLET(doc, text):
    par = doc.add_paragraph(style="List Bullet")
    par.paragraph_format.space_after = Pt(2)
    add_rich(par, text)
    return par


def FIGURE(doc, filename, width_in, number, caption):
    path = os.path.join(FIG_DIR, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"{path} missing; run `python -m src.plots` first")
    par = doc.add_paragraph()
    par.alignment = WD_ALIGN_PARAGRAPH.CENTER
    par.paragraph_format.keep_with_next = True
    par.paragraph_format.space_after = Pt(2)
    par.add_run().add_picture(path, width=Inches(width_in))
    cap = doc.add_paragraph()
    cap.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    add_rich(cap, f"Figure {number}. ", size=10, bold=True)
    add_rich(cap, caption, size=10)
    return cap


def FIGURE_PAIR(doc, items, width_in=3.1):
    """Two figures side by side in a borderless table, each with a numbered caption.

    items: [(figure_index, number, caption), (figure_index, number, caption)]
    """
    table = doc.add_table(rows=1, cols=len(items))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for cell, (idx, number, caption) in zip(table.rows[0].cells, items):
        path = os.path.join(FIG_DIR, FIGURES[idx][0])
        if not os.path.exists(path):
            raise FileNotFoundError(f"{path} missing; run `python -m src.plots` first")
        cell.width = Inches(3.25)
        pic = cell.paragraphs[0]
        pic.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pic.paragraph_format.space_after = Pt(2)
        pic.add_run().add_picture(path, width=Inches(width_in))
        cap = cell.add_paragraph()
        cap.paragraph_format.space_after = Pt(0)
        add_rich(cap, f"Figure {number}. ", size=9, bold=True)
        add_rich(cap, caption, size=9)
    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_after = Pt(0)
    return table


def TABLE(doc, number, caption, header, rows, widths=None):
    cap = doc.add_paragraph()
    cap.paragraph_format.keep_with_next = True
    cap.paragraph_format.space_after = Pt(2)
    add_rich(cap, f"Table {number}. ", size=10, bold=True)
    add_rich(cap, caption, size=10)
    table = doc.add_table(rows=1, cols=len(header))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    for i, h in enumerate(header):
        cell = table.rows[0].cells[i]
        cell.text = ""
        add_rich(cell.paragraphs[0], h, size=10, bold=True)
    for row in rows:
        cells = table.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            add_rich(cells[i].paragraphs[0], str(v), size=10)
    for row in table.rows:
        for i, cell in enumerate(row.cells):
            for p_ in cell.paragraphs:
                p_.paragraph_format.space_after = Pt(0)
            if widths:
                cell.width = Inches(widths[i])
    doc.add_paragraph().paragraph_format.space_after = Pt(2)
    return table


# ----------------------------------------------------------------------------
# Report content
# ----------------------------------------------------------------------------
def build_document(F):
    doc = setup_document()

    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_rich(t, TITLE, size=16, bold=True)
    s = doc.add_paragraph()
    s.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_rich(s, "An independent computational investigation", size=11, italic=True)
    a = doc.add_paragraph()
    a.alignment = WD_ALIGN_PARAGRAPH.CENTER
    add_rich(a, f"[Author name]  |  Generated {datetime.date.today().isoformat()} from the project repository",
             size=10)

    # ---- Abstract
    H1(doc, "Abstract")
    P(doc,
      "This report describes an independent computational investigation of quantum tunneling of a single "
      "electron through a one-dimensional finite rectangular potential barrier with 0 < E < V_{0}. The "
      "transmission probability T is computed in two separate ways: from the closed-form expression "
      "T = [1 + V_{0}^{2} sinh^{2}(κa) / (4E(V_{0} − E))]^{−1}, and by directly solving the four "
      "boundary-matching conditions as a 4×4 complex linear system. The two implementations were compared on "
      f"a fixed grid of {F['n']} parameter combinations spanning κa from {F['ka_min']} to {F['ka_max']}. "
      f"The largest absolute difference in T was {F['abs_max']} and the largest relative difference was "
      f"{F['rel_max']}, at the level of double-precision round-off. For fixed V_{{0}} = 5 eV, T decreases "
      "monotonically with barrier width and with barrier height, and increases with particle energy, as the "
      "closed-form expression requires. Because both methods solve the same equations, their agreement "
      "validates the implementation and the algebra; it does not test whether the rectangular-barrier model "
      "describes any physical system. No experimental data are used and no novel result is claimed.")

    # ---- 1 Introduction
    H1(doc, "1  Introduction")
    P(doc,
      "A classical particle with energy E below a potential barrier of height V_{0} cannot cross it. A quantum "
      "particle can: its wavefunction decays inside the barrier but does not vanish, so there is a nonzero "
      "probability of finding the particle on the far side. The finite rectangular barrier is the standard "
      "textbook example of this effect [1] and has an exact solution.")
    P(doc,
      "The question investigated here is: how does the tunneling probability change with barrier width, barrier "
      "height and particle energy, and do an analytic formula and a direct numerical solution of the boundary "
      "conditions agree across barriers from thin to very thick? The aim is a reproducible, tested "
      "implementation with honestly reported numerical behaviour. This is a re-derivation and numerical "
      "verification of well-known results; it is not a novel discovery.")
    P(doc,
      "Section 2 gives the theory. Section 3 describes the units, the two implementations, the parameter sweep "
      "and the automated tests. Section 4 reports results, Section 5 states limitations, and Section 6 "
      "concludes. The Appendix describes the repository so that the report can be rebuilt.")

    # ---- 2 Theory
    H1(doc, "2  Theory")
    H2(doc, "2.1  Schrödinger equation in one dimension")
    P(doc,
      "A particle of mass m moves in the potential V(x) = 0 for x < 0, V(x) = V_{0} for 0 < x < a, and V(x) = 0 "
      "for x > a. The time-independent Schrödinger equation is")
    EQ(doc, "−(ħ^{2} / 2m) ψ″(x) + V(x) ψ(x) = E ψ(x)", 1)
    P(doc,
      "with ħ the reduced Planck constant. The model is non-relativistic, one-dimensional, and describes a "
      "single particle (here an electron) incident from the left with energy 0 < E < V_{0}.")
    H2(doc, "2.2  Wavefunctions in the three regions")
    P(doc, "Define the wavenumber outside the barrier and the decay constant inside it:")
    EQ(doc, "k = √(2mE) / ħ,        κ = √(2m(V_{0} − E)) / ħ", 2)
    P(doc, "The general solution in each region, with unit incident amplitude, is")
    EQ(doc, "ψ_{I}(x) = e^{ikx} + r e^{−ikx}     (x < 0)", 3)
    EQ(doc, "ψ_{II}(x) = A e^{κx} + B e^{−κx}     (0 < x < a)", 4)
    EQ(doc, "ψ_{III}(x) = t e^{ikx}     (x > a)", 5)
    P(doc,
      "Region III contains only a transmitted, right-moving wave. The transmission and reflection "
      "probabilities are T = |t|^{2} and R = |r|^{2}. Because the particle has the same wavenumber on both "
      "sides, no velocity factor is needed, and probability conservation requires R + T = 1.")
    H2(doc, "2.3  Boundary conditions")
    P(doc, "ψ and ψ′ must be continuous at x = 0 and x = a, which gives four linear equations for r, A, B and t:")
    EQ(doc, "1 + r = A + B", 6)
    EQ(doc, "ik(1 − r) = κ(A − B)", 7)
    EQ(doc, "A e^{κa} + B e^{−κa} = t e^{ika}", 8)
    EQ(doc, "κ(A e^{κa} − B e^{−κa}) = ik t e^{ika}", 9)
    H2(doc, "2.4  Algebra leading to the transmission probability")
    P(doc,
      "Equations (8) and (9) give A and B in terms of t. Adding and subtracting them,")
    EQ(doc, "A e^{κa} = (t e^{ika} / 2)(1 + ik/κ),        B e^{−κa} = (t e^{ika} / 2)(1 − ik/κ)", 10)
    P(doc,
      "Adding (6) to (7) divided by ik eliminates r: 2 = A(1 − iκ/k) + B(1 + iκ/k). Substituting (10), and using "
      "(1 + ik/κ)(1 − iκ/k) = 2 − i(κ^{2} − k^{2})/(kκ) together with its complex conjugate, gives")
    EQ(doc, "t e^{ika} = 1 / [cosh(κa) + i ((κ^{2} − k^{2}) / (2kκ)) sinh(κa)]", 11)
    P(doc,
      "Taking the squared modulus and using cosh^{2} = 1 + sinh^{2},")
    EQ(doc, "T = |t|^{2} = 1 / [1 + ((κ^{2} + k^{2})^{2} / (4k^{2}κ^{2})) sinh^{2}(κa)]", 12)
    P(doc,
      "Finally, k^{2} = 2mE/ħ^{2} and κ^{2} = 2m(V_{0} − E)/ħ^{2} give κ^{2} + k^{2} = 2mV_{0}/ħ^{2} and "
      "k^{2}κ^{2} = (2m/ħ^{2})^{2} E(V_{0} − E), so")
    EQ(doc, "T = [ 1 + V_{0}^{2} sinh^{2}(κa) / (4E(V_{0} − E)) ]^{−1}", 13)
    H2(doc, "2.5  Limiting cases")
    BULLET(doc,
           "Thin barrier, a → 0: sinh(κa) → 0, so T → 1. A barrier of vanishing width does not reflect.")
    BULLET(doc,
           "Thick barrier, κa ≫ 1: sinh^{2}(κa) ≈ e^{2κa}/4, and the leading 1 in the denominator is negligible, so "
           "T ≈ [16E(V_{0} − E)/V_{0}^{2}] e^{−2κa}. T then falls exponentially with width, with log-slope −2κ.")

    # ---- 3 Methods
    H1(doc, "3  Methods")
    H2(doc, "3.1  Units and constants")
    P(doc,
      "User-facing inputs are energies in eV and lengths in nm. Internally every calculation is done in SI units "
      "(J, m, kg); the conversions live in src/constants.py (ev_to_joule, joule_to_ev, nm_to_m, m_to_nm). The "
      "constants follow CODATA 2022 [2]. The Planck constant "
      f"h = {F['h']} J s and the elementary charge e = {F['e']} C are exact by the SI definition, and "
      f"ħ = h/2π = {F['hbar']} J s is computed rather than typed in. The electron mass is "
      f"m_{{e}} = {F['me']} kg. All values in this paragraph are read from src/constants.py when the report is built.")
    H2(doc, "3.2  Analytic implementation")
    P(doc,
      "src/analytic.py implements Eq. (13) as transmission_analytic(E_eV, V0_eV, width_nm). It raises ValueError "
      "unless 0 < E < V_{0} and the width is non-negative. "
      f"A direct evaluation of sinh^{{2}}(κa) overflows in double precision for κa above roughly {F['ovf']}, "
      "so the function works in logarithms. Writing "
      "x = κa and A_{0} = V_{0}^{2}/(16E(V_{0} − E)), the term in the denominator is "
      "A_{0} e^{2x}(1 − e^{−2x})^{2}; its logarithm is formed as ln A_{0} + 2x + 2 ln(−expm1(−2x)), and "
      "T = exp(−logaddexp(0, that logarithm)). The exponential e^{2x} is never formed, and T underflows "
      "smoothly to 0 for very thick barriers.")
    H2(doc, "3.3  Independent numerical implementation")
    P(doc,
      "src/numeric.py does not import src/analytic.py. It builds the four equations (6)–(9) as a 4×4 complex "
      "matrix in the unknowns (r, A′, B, t) and solves it with numpy.linalg.solve. The function returns "
      "T = |t|^{2} and R = |r|^{2}. To keep the matrix well conditioned for thick barriers, the unknown A is "
      "rescaled as A′ = A e^{κa}, the amplitude of the growing exponential at x = a. Every matrix entry then "
      "contains only e^{−κa} ≤ 1, never e^{+κa}. This is a change of variables, not an approximation.")
    H2(doc, "3.4  Parameter sweep")
    P(doc,
      "src/sweeps.py evaluates both methods on a grid fixed in advance and writes results/comparison.csv. "
      f"The grid is {len(sweeps.ENERGIES_EV)} energies × {len(sweeps.BARRIER_HEIGHTS_EV)} barrier heights × "
      f"{len(sweeps.WIDTHS_NM)} widths = {F['n']} combinations: E ∈ {{{', '.join(f'{x:g}' for x in sweeps.ENERGIES_EV)}}} eV, "
      f"V_{{0}} ∈ {{{', '.join(f'{x:g}' for x in sweeps.BARRIER_HEIGHTS_EV)}}} eV, and width ∈ "
      f"{{{', '.join(f'{x:g}' for x in sweeps.WIDTHS_NM)}}} nm. Every combination satisfies 0 < E < V_{{0}}. The "
      "electron mass is used throughout. The grid was not adjusted after seeing the results. The CSV columns "
      "are E_eV, V0_eV, width_nm, kappa_a, T_analytic, T_numeric, abs_error and rel_error, with "
      "rel_error = |T_numeric − T_analytic| / T_analytic.")
    H2(doc, "3.5  Automated tests")
    pf = F["tests_files"]
    P(doc,
      f"The repository contains {F['tests_total']} pytest tests (collected with pytest --collect-only). A full "
      f"run at report-build time gave: {F['tests_summary']}. Table 1 gives the count per file.")
    desc = {
        "tests/test_constants.py": "constants and unit conversions, round trips",
        "tests/test_analytic.py": "T→1 as a→0, monotonic in width, 0≤T≤1, thick-barrier limit, no overflow, ValueError cases",
        "tests/test_numeric.py": "R+T=1 within 1e-10, bounds, monotonicity, agreement with analytic on 12 sets",
        "tests/test_sweeps.py": "CSV has ≥100 rows, expected columns, no NaN",
        "tests/test_plots.py": "all six figure files are created and non-empty",
        "tests/test_app.py": "app helper functions, E≥V0 warning path, multithreaded figure building",
    }
    rows = [[fn, str(c), desc.get(fn, "")] for fn, c in sorted(pf.items())]
    rows.append(["Total", str(F["tests_total"]), ""])
    TABLE(doc, 1, "Automated tests collected by pytest.", ["File", "Tests", "What is checked"], rows,
          widths=[1.8, 0.6, 4.1])

    # ---- 4 Results
    H1(doc, "4  Results")
    V0w = TREND_V0_WIDTH
    H2(doc, "4.1  Dependence on barrier width")
    P(doc,
      f"Figure 1 shows T against width for E = 0.5, 1 and 2 eV with V_{{0}} = {V0w:g} eV on a logarithmic axis. All "
      "three curves start at T = 1 at zero width and, beyond about 0.5 nm, appear as nearly straight lines on the "
      "log axis, i.e. T falls roughly exponentially with width. The lower the energy, the lower the curve at "
      "a given width. For E = 1 eV, the analytic function gives "
      f"T = {F['Tw_E1.0_w0.5']} at 0.5 nm, {F['Tw_E1.0_w1.0']} at 1 nm, {F['Tw_E1.0_w2.0']} at 2 nm and "
      f"{F['Tw_E1.0_w3.0']} at 3 nm. Between 1 and 2 nm the log-slope of T for E = 1 eV is "
      f"d ln T/da = {F['slope_E1.0']} nm^{{−1}} (about {F['dec_E1.0']} decades per nm), compared with "
      f"−2κ = {F['m2k_E1.0']} nm^{{−1}} from the thick-barrier form, where κ = {F['kap_E1.0']} nm^{{−1}}. "
      f"For E = 0.5 eV the corresponding slope is {F['slope_E0.5']} nm^{{−1}} (−2κ = {F['m2k_E0.5']} nm^{{−1}}), and "
      f"for E = 2 eV it is {F['slope_E2.0']} nm^{{−1}} (−2κ = {F['m2k_E2.0']} nm^{{−1}}). On the 301-point width "
      f"grid used in the check, T is {F['mono_w']} for all three energies.")
    H2(doc, "4.2  Dependence on barrier height")
    P(doc,
      "Figure 2 shows T against V_{0} for E = 1 eV and a = 1 nm. T decreases monotonically as the barrier "
      f"gets taller (the check on a 400-point grid found T {F['mono_h']}): "
      f"T = {F['Th_1.1']} at V_{{0}} = 1.1 eV, {F['Th_2.0']} at 2 eV, {F['Th_5.0']} at 5 eV and {F['Th_10.0']} "
      f"at 10 eV, a drop of {F['h_decades']} decades over this range. The curve is steeper at small V_{{0}} and "
      f"flatter at large V_{{0}}: d log_{{10}}T/dV_{{0}} is {F['hs_1.5']} eV^{{−1}} at V_{{0}} = 1.5 eV but "
      f"{F['hs_8.0']} eV^{{−1}} at 8 eV. This is consistent with κ ∝ √(V_{{0}} − E), which grows "
      "fastest when V_{0} − E is small.")
    FIGURE_PAIR(doc, [
        (0, 1, "T versus barrier width for E = 0.5, 1 and 2 eV with V_{0} = 5 eV (log y-axis). "
               "Lines: src/analytic.py. Hollow markers: src/numeric.py at selected widths."),
        (1, 2, "T versus barrier height V_{0} for E = 1 eV and a = 1 nm (log y-axis). "
               "Line: analytic. Markers: numeric."),
    ])
    H2(doc, "4.3  Dependence on particle energy")
    P(doc,
      "Figure 3 shows T against E for V_{0} = 5 eV and a = 1 nm. T increases monotonically with E "
      f"(on a 400-point grid, T is {F['mono_e']}): T = {F['Te_0.05']} at E = 0.05 eV, {F['Te_1.0']} at 1 eV, "
      f"{F['Te_2.5']} at 2.5 eV and {F['Te_4.95']} at 4.95 eV, a gain of {F['e_decades']} decades. The curve is "
      f"steep at both ends and gentler in the middle: d log_{{10}}T/dE is {F['es_0.1']} eV^{{−1}} at E = 0.1 eV, "
      f"{F['es_2.5']} eV^{{−1}} at 2.5 eV and {F['es_4.9']} eV^{{−1}} at 4.9 eV. Only energies below the barrier "
      "top are computed; the curve is not extended to E ≥ V_{0}.")
    P(doc,
      "Figure 4 combines the width and energy dependence for V_{0} = 5 eV. On the plotted grid "
      f"(E from 0.05 to 4.95 eV, width from 0 to 3 nm) log_{{10}}T ranges from {F['hm_max']} to {F['hm_min']}. The "
      f"smallest value is at E = {F['hm_min_E']} eV and a = {F['hm_min_w']} nm. At a = 3 nm, log_{{10}}T is "
      f"{F['hm_Ehi_w3']} at E = 4.95 eV and {F['hm_Elo_w3']} at E = 0.05 eV. The bands of constant colour rise "
      "toward the upper-right of the plot: at higher energy, a wider barrier is needed to reach the same T.")
    FIGURE_PAIR(doc, [
        (2, 3, "T versus particle energy E for V_{0} = 5 eV and a = 1 nm (log y-axis). "
               "Line: analytic. Markers: numeric."),
        (3, 4, "log_{10}(T) versus particle energy and barrier width for V_{0} = 5 eV (analytic)."),
    ])

    H2(doc, "4.4  Thick-barrier approximation")
    P(doc,
      "Table 2 compares the exact value from Eq. (13) with the thick-barrier form "
      "16E(V_{0} − E)/V_{0}^{2} · e^{−2κa} for four widths at E = 1 eV and V_{0} = 5 eV. The percent difference is "
      "(approximate − exact)/exact × 100, evaluated in 60-digit decimal arithmetic because for κa above about "
      "10 it is below double-precision round-off. The approximation overestimates T in every case, and the "
      "difference shrinks rapidly as κa grows, as expected from dropping the leading 1 and the e^{−2κa} term "
      "in sinh^{2}(κa). Already at κa ≈ 2 the difference is of order one percent.")
    rows = [[c["tag"].replace("E=", "E = ").replace(", V0=", " eV, V_{0} = ").replace(", a=", " eV, a = ")
             + " nm", c["ka"], c["exact"], c["approx"], c["pct"]] for c in F["thick"]]
    TABLE(doc, 2, "Exact versus thick-barrier transmission.",
          ["Case", "κa", "T exact", "T approx.", "Difference"], rows, widths=[2.3, 0.7, 1.2, 1.2, 1.1])

    H2(doc, "4.5  Agreement between the numeric and analytic methods")
    P(doc,
      f"Table 3 summarises the {F['n']}-combination sweep. Energies range from {F['E_min']} to {F['E_max']} eV, "
      f"barrier heights from {F['V0_min']} to {F['V0_max']} eV, widths from {F['w_min']} to {F['w_max']} nm, and "
      f"κa from {F['ka_min']} to {F['ka_max']}. The analytic transmission spans from {F['T_min']} to {F['T_max']} "
      f"({F['T_decades']} decades). On the same grid the numeric solver satisfies |R + T − 1| ≤ {F['RT_dev']}.")
    TABLE(doc, 3, "Numeric versus analytic transmission over the sweep (results/comparison.csv).",
          ["Quantity", "Value"],
          [["Combinations", F["n"]],
           ["Max absolute error", F["abs_max"]],
           ["Mean absolute error", F["abs_mean"]],
           ["Max relative error", F["rel_max"]],
           ["Mean relative error", F["rel_mean"]],
           ["Rows with exactly zero absolute error", F["n_zero"]],
           ["Largest κa", F["ka_max"]]],
          widths=[3.5, 1.5])
    P(doc,
      "Figure 5 plots T_numeric against T_analytic for all combinations on log-log axes. The points lie on the "
      "y = x line over the whole range of T. The worst relative error occurs at "
      f"E = {F['w_E']} eV, V_{{0}} = {F['w_V0']} eV, a = {F['w_w']} nm (κa = {F['w_ka']}), where "
      f"T_analytic = {F['w_Ta']} and T_numeric = {F['w_Tn']}; the relative error is {F['w_rel']} and the absolute "
      f"error {F['w_abs']}.")
    P(doc,
      "Figure 6 shows the absolute and relative errors against κa. The absolute error falls steadily as κa "
      "grows, because T itself shrinks over many orders of magnitude. The relative error does not fall. Its "
      f"median is {F['bin_lt10_med']} for κa < 10 ({F['bin_lt10_n']} rows, maximum {F['bin_lt10_max']}), "
      f"{F['bin_mid_med']} for 10 ≤ κa < 50 ({F['bin_mid_n']} rows, maximum {F['bin_mid_max']}), and "
      f"{F['bin_ge50_med']} for κa ≥ 50 ({F['bin_ge50_n']} rows, maximum {F['bin_ge50_max']}). "
      "So there is a mild increase in relative error with κa, but it stays near double-precision round-off "
      f"(smallest nonzero {F['rel_min']}, largest {F['rel_max']}). The {F['n_zero']} rows with exactly zero "
      "absolute error cannot be drawn on a logarithmic axis and are omitted from the figure.")
    FIGURE_PAIR(doc, [
        (4, 5, f"Numeric versus analytic T for the {F['n']} sweep combinations (log-log axes). "
               "The dashed line is y = x."),
        (5, 6, "Absolute (top) and relative (bottom) difference between numeric and analytic T versus κa. "
               "Exact zeros are omitted (log y-axes)."),
    ])

    # ---- 5 Limitations
    H1(doc, "5  Limitations")
    BULLET(doc,
           "Agreement validates the implementation, not the physics. The numeric and analytic methods solve the "
           "same equations (6)–(9) for the same model. Their agreement shows that the algebra in Section 2.4 and "
           "both codes are consistent. It does not show that the rectangular-barrier model describes any real "
           "system.")
    BULLET(doc,
           "Model scope. The model is one-dimensional, non-relativistic, uses a sharp rectangular barrier, a single "
           "electron and plane-wave incidence, and covers only 0 < E < V_{0}. The cases E = V_{0} and E > V_{0} use "
           "different expressions and are rejected with ValueError.")
    BULLET(doc,
           "No experimental comparison. No measured data were used. The results are properties of the model only.")
    BULLET(doc,
           f"Floating-point limits for very thick barriers. For E = 1 eV and V_{{0}} = 5 eV, κ = {F['kap_E1.0']} "
           f"nm^{{−1}}. T_analytic first returns exactly 0 at a width of about {F['uf_w']} nm (κa ≈ {F['uf_ka']}). "
           f"The smallest nonzero value just below that is {F['uf_T_just']}, in the subnormal range where double "
           f"precision has lost significant digits. At κa = 300 the two methods give {F['uf_a_300']} and "
           f"{F['uf_n_300']}; at κa = 360 they give {F['uf_a_360']} and {F['uf_n_360']}; at κa = 400 they give "
           f"{F['uf_a_400']} and {F['uf_n_400']}. The sweep itself reaches only κa = {F['ka_max']}.")
    BULLET(doc,
           f"Sweep coverage. The grid is a fixed {len(sweeps.ENERGIES_EV)}×{len(sweeps.BARRIER_HEIGHTS_EV)}×"
           f"{len(sweeps.WIDTHS_NM)} set with E/V_{{0}} ≤ {F['ratio_max']}. It does not probe E very close to "
           "V_{0}, and it contains no variation of the particle mass.")
    BULLET(doc,
           "Known issue in the Streamlit app. Dragging the sliders quickly can start overlapping script reruns in "
           "different threads. Matplotlib's mathtext parser is not thread-safe, which previously printed transient "
           "ParseFatalException / ParseException errors in the terminal. The app now builds and renders each figure "
           "under a lock, and a multithreaded test covers this, but a long interactive session has not been used to "
           "confirm that the messages never reappear.")

    # ---- 6 Conclusion
    H1(doc, "6  Conclusion")
    P(doc,
      "For a single electron and a 1D rectangular barrier with 0 < E < V_{0}, the closed-form transmission "
      "probability was derived and implemented, and independently reproduced by a direct 4×4 boundary-matching "
      f"solve. Over {F['n']} fixed parameter combinations the two agree to a maximum relative difference of "
      f"{F['rel_max']}. For V_{{0}} = 5 eV the computed T decreases with width and with barrier height, and "
      "increases with energy, with an approximately exponential dependence on width for thick barriers. "
      "These are expected consequences of the closed-form result, and the work should be read as a verified "
      "reimplementation of textbook physics. Extensions that would test the physics rather than the "
      "implementation include comparison with experimental data, a different numerical method (for example a "
      "time-dependent or finite-difference solution), and more realistic barrier shapes.")

    # ---- 7 References
    H1(doc, "7  References")
    P(doc,
      "[1]  D. J. Griffiths and D. F. Schroeter, Introduction to Quantum Mechanics, 3rd ed. "
      "(Cambridge University Press, 2018).")
    P(doc,
      "[2]  E. Tiesinga, P. J. Mohr, D. B. Newell and B. N. Taylor, CODATA recommended values of the "
      "fundamental physical constants: 2022 (National Institute of Standards and Technology; "
      "https://physics.nist.gov/cuu/Constants/).")

    # ---- Appendix
    H1(doc, "Appendix  Repository description")
    P(doc,
      "The report, the results and the figures can all be rebuilt from the repository. Files that existed when "
      "this report was generated are listed in Table 4.")
    files = [
        ("app.py", "Streamlit app: sliders, T/R metrics, T-versus-width plot, |ψ|^{2} plot"),
        ("requirements.txt", "Pinned Python dependencies"),
        ("src/constants.py", "ħ, h, m_{e}, e; eV↔J and nm↔m conversions"),
        ("src/analytic.py", "transmission_analytic: closed form evaluated in log space"),
        ("src/numeric.py", "transmission_numeric (T, R) and wavefunction_numeric: 4×4 boundary-matching solver"),
        ("src/sweeps.py", f"{F['n']}-combination comparison; writes results/comparison.csv"),
        ("src/plots.py", f"{len(FIGURES)} figures to results/figures/"),
        ("src/make_report.py", "Generates this Word document"),
        ("tests/", "pytest suite (Table 1)"),
        ("results/comparison.csv", "Sweep output used in Section 4.5"),
        ("results/figures/", f"fig1 … fig{len(FIGURES)} (PNG)"),
        ("report/quantum_tunneling_report.docx", "This report"),
    ]
    rows = []
    for path, text in files:
        full = os.path.join(PROJECT_ROOT, path.replace("/", os.sep))
        if not os.path.exists(full) and path != "report/quantum_tunneling_report.docx":
            raise FileNotFoundError(path)
        rows.append([path, text])
    TABLE(doc, 4, "Repository contents.", ["Path", "Purpose"], rows, widths=[2.3, 4.2])
    P(doc, "To rebuild everything from the project root with the project's virtual environment active:")
    for cmd in ("python -m pytest", "python -m src.sweeps", "python -m src.plots", "python -m src.make_report",
                "python -m streamlit run app.py --server.port 8765"):
        par = doc.add_paragraph()
        par.paragraph_format.left_indent = Inches(0.4)
        par.paragraph_format.space_after = Pt(0)
        r = par.add_run(cmd)
        r.font.name = "Consolas"
        r.font.size = Pt(10)
    doc.add_paragraph()
    H2(doc, "Authorship and AI assistance")
    P(doc, "[ERNIE: describe what you wrote yourself and where AI assisted]")
    return doc


# ----------------------------------------------------------------------------
# Page count
# ----------------------------------------------------------------------------
def page_count(path):
    """Exact page count via Microsoft Word if available, else None."""
    ps = (
        "$w=New-Object -ComObject Word.Application; $w.Visible=$false; "
        f"$d=$w.Documents.Open('{path}',$false,$true); "
        "$n=$d.ComputeStatistics(2); $d.Close($false); $w.Quit(); $n"
    )
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                             capture_output=True, text=True, timeout=120)
        return int(out.stdout.strip().splitlines()[-1])
    except Exception:  # noqa: BLE001
        return None


def estimate_pages(doc):
    words = sum(len(p.text.split()) for p in doc.paragraphs)
    for t in doc.tables:
        for row in t.rows:
            for c in row.cells:
                words += len(c.text.split())
    from PIL import Image

    def height_at(idx, width_in):
        with Image.open(os.path.join(FIG_DIR, FIGURES[idx][0])) as im:
            return width_in * im.height / im.width

    # Figures are placed in three side-by-side pairs; a pair is as tall as its taller image
    # (3.1 in wide) plus about 0.6 in for captions and spacing.
    fig_inches = sum(max(height_at(i, 3.1), height_at(j, 3.1)) + 0.6 for i, j in ((0, 1), (2, 3), (4, 5)))
    return words / 520.0 + fig_inches / 9.0, words


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    F = compute_facts()
    doc = build_document(F)
    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    doc.save(OUT_PATH)
    print(f"Wrote {OUT_PATH}")

    est, words = estimate_pages(doc)
    exact = page_count(OUT_PATH)
    print(f"Word count (body + tables): {words}")
    print(f"Page estimate from word count and figure sizes: {est:.1f}")
    print("Page count from Microsoft Word: "
          + (str(exact) if exact is not None else "unavailable (Word not found)"))

    print("\nNumbers in the report and where each came from")
    print("(illustrative case parameters are set in src/make_report.py: TREND_* and THICK_CASES)\n")
    width = max(len(d) for d, _, _ in PROVENANCE)
    for desc, val, source in PROVENANCE:
        print(f"{desc.ljust(width)}  {val.ljust(14)}  <- {source}")


if __name__ == "__main__":
    main()
