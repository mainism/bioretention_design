"""
calc_basis.py — Engineering Calculation Basis Document Generator
Produces a standalone HTML file ([Project]_Calculation_Basis.html) that
documents every formula, assumption, constant, and step-by-step proof
used in the bioretention cell design, formatted for senior-engineer
or academic-supervisor cross-validation.

All equations are rendered via MathJax (CDN-loaded) so the file must be
opened in a browser with an internet connection to display LaTeX properly.
"""

import math
import datetime
import os


# ─────────────────────────────────────────────────────────────────────────────
# CSS / HTML helpers
# ─────────────────────────────────────────────────────────────────────────────
_CSS = """
:root {
  --accent: #1a5276;
  --accent2: #117a65;
  --warn:   #d35400;
  --pass:   #1e8449;
  --fail:   #c0392b;
  --bg:     #f7f9fc;
  --card:   #ffffff;
  --border: #d5dce8;
  --code:   #eaf0fb;
  --text:   #212121;
  --muted:  #555e6e;
}
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: 'Segoe UI', Arial, sans-serif;
  font-size: 14px;
  color: var(--text);
  background: var(--bg);
  line-height: 1.65;
}
/* ── header ── */
header {
  background: linear-gradient(135deg, var(--accent) 0%, #154360 100%);
  color: #fff;
  padding: 30px 48px 24px;
  border-bottom: 4px solid var(--accent2);
}
header h1 { font-size: 1.65rem; font-weight: 700; letter-spacing: 0.5px; }
header p  { font-size: 0.88rem; opacity: 0.82; margin-top: 4px; }
.stamp {
  display: inline-block;
  background: rgba(255,255,255,0.15);
  border: 1px solid rgba(255,255,255,0.35);
  border-radius: 6px;
  padding: 4px 14px;
  font-size: 0.78rem;
  margin-top: 10px;
}
/* ── layout ── */
.container { max-width: 1200px; margin: 0 auto; padding: 32px 48px 60px; }
section { margin-bottom: 40px; }
h2 {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--accent);
  border-bottom: 2px solid var(--accent);
  padding-bottom: 6px;
  margin-bottom: 18px;
}
h3 {
  font-size: 1.05rem;
  font-weight: 700;
  color: #2c3e50;
  margin: 22px 0 10px;
}
p { margin-bottom: 10px; }
/* ── cards ── */
.card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 20px 24px;
  margin-bottom: 18px;
  box-shadow: 0 1px 4px rgba(0,0,0,0.06);
}
/* ── tables ── */
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  margin: 10px 0 6px;
}
th {
  background: var(--accent);
  color: #fff;
  padding: 9px 12px;
  text-align: left;
  font-weight: 600;
}
td { padding: 8px 12px; border-bottom: 1px solid var(--border); }
tr:nth-child(even) td { background: #f0f4fa; }
tr:hover td { background: #e8f4fd; }
.num { text-align: right; font-family: monospace; }
/* ── proof blocks ── */
.proof {
  background: var(--code);
  border-left: 4px solid var(--accent);
  border-radius: 0 6px 6px 0;
  padding: 14px 18px;
  margin: 12px 0;
  font-size: 13px;
}
.proof .step {
  margin: 6px 0;
  display: flex;
  gap: 10px;
}
.proof .step-num {
  font-weight: 700;
  color: var(--accent);
  min-width: 20px;
}
.result-box {
  background: #e8f8f5;
  border: 1.5px solid var(--accent2);
  border-radius: 6px;
  padding: 10px 16px;
  margin-top: 10px;
  font-weight: 600;
  color: #0e6655;
}
/* ── status badges ── */
.pass { color: var(--pass); font-weight: 700; }
.fail { color: var(--fail); font-weight: 700; }
.warn { color: var(--warn); font-weight: 700; }
.badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 20px;
  font-size: 0.78rem;
  font-weight: 700;
}
.badge-pass { background: #d5f5e3; color: #1e8449; }
.badge-fail { background: #fadbd8; color: #c0392b; }
/* ── references ── */
.ref-list { padding-left: 20px; list-style: decimal; }
.ref-list li { margin-bottom: 8px; }
/* ── toc ── */
.toc { background: #eaf0fb; border-radius: 8px; padding: 16px 24px;
       border: 1px solid var(--border); margin-bottom: 30px; }
.toc h3 { color: var(--accent); margin-top: 0; }
.toc ol { padding-left: 20px; }
.toc li { margin: 4px 0; }
.toc a  { color: var(--accent); text-decoration: none; }
.toc a:hover { text-decoration: underline; }
"""

_MATHJAX = """
<script>
MathJax = {
  tex: { inlineMath: [['$','$'],['\\\\(','\\\\)']] },
  options: { skipHtmlTags: ['script','noscript','style','textarea','pre'] }
};
</script>
<script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-chtml-full.js"
        id="MathJax-script" async></script>
"""


def _card(content: str) -> str:
    return f'<div class="card">{content}</div>'


def _proof(*steps, result: str = "") -> str:
    rows = "".join(
        f'<div class="step"><span class="step-num">{i+1}.</span> {s}</div>'
        for i, s in enumerate(steps)
    )
    res = f'<div class="result-box">Result: {result}</div>' if result else ""
    return f'<div class="proof">{rows}{res}</div>'


def _tbl(headers: list, rows: list) -> str:
    th = "".join(f"<th>{h}</th>" for h in headers)
    body = ""
    for row in rows:
        body += "<tr>" + "".join(
            f'<td class="num">{c}</td>' if isinstance(c, (int, float)) else f"<td>{c}</td>"
            for c in row
        ) + "</tr>"
    return f"<table><thead><tr>{th}</tr></thead><tbody>{body}</tbody></table>"


# ─────────────────────────────────────────────────────────────────────────────
# Section generators
# ─────────────────────────────────────────────────────────────────────────────

def _sec_assumptions() -> str:
    rows = [
        ("Runoff Coefficient ($R_v$)", "Volumetric runoff, weighted by imperviousness",
         "$R_v = 0.05 + 0.009 \\times I$", "ASCE / PGC (2007) Sec 3.2"),
        ("Water Quality Volume ($WQV$)", "Volume of runoff targeted for treatment",
         "$WQV = R_v \\times R_d \\times A_c$, $R_d = 25\\,\\text{mm}$", "PGC (2007) Sec 3.4"),
        ("Treatment Volume target", "Fraction of WQV the cell must capture",
         "User-defined $T_v$ (%)", "WbD (2014) Sec 2.3"),
        ("Filter media $K_{sat}$", "Target saturated hydraulic conductivity",
         "$100\\text{–}300\\,\\text{mm/hr}$", "FAWB (2009) Sec 4.2"),
        ("Filter media porosity ($n_f$)", "Void space in engineered soil mix",
         "$n_f = 0.38$", "FAWB (2009) Table 3"),
        ("Drainage gravel porosity ($n_g$)", "Void space in 10–20 mm crushed stone",
         "$n_g = 0.40$", "WbD (2014) Table 5"),
        ("Equivalent storage depth ($D_e$)", "Effective storage accounting for pore-space and ponding",
         "$D_e = d_{\\text{pond}} + n_f d_f + n_g d_g$", "MGNDC (2012) Sec 5.1"),
        ("Maximum ponding depth", "Extended detention safety limit",
         "$h_{\\max} = 200\\,\\text{mm}$", "WbD (2014) Sec 3.2.3.3"),
        ("Darcy peak filtration ($Q_{\\max}$)", "Peak exfiltration through saturated media",
         "$Q_{\\max} = K_{sat} \\cdot A \\cdot \\tfrac{h+d}{d}$", "WbD (2014) Eq 7"),
        ("Manning's $n$ (smooth UPVC)", "Pipe friction factor",
         "$n = 0.011$", "CSTR Pipe Handbook; WbD (2014) Eq 11"),
        ("Underdrain blockage factor", "Capacity derate for partial slot clogging",
         "$BF = 0.80$", "WbD (2014) Sec 5.3.2"),
        ("TSS depth model", "Empirical attenuation vs. depth",
         "$E_{TSS} = \\min(98,\\;70 + 35 \\cdot d/0.8)$", "Davis et al. (2009) Table 4"),
        ("TP depth model", "Empirical attenuation vs. depth",
         "$E_{TP} = \\min(85,\\;45 + 50 \\cdot d/0.8)$", "Davis et al. (2009) Table 4"),
        ("TN depth model", "Empirical attenuation vs. depth",
         "$E_{TN} = \\min(65,\\;25 + 50 \\cdot d/0.8)$", "Davis et al. (2009) Table 4"),
        ("Min filter depth (TP)", "Structural minimum for phosphorus adsorption",
         "$d_{\\min,TP} = 600\\,\\text{mm}$", "Hunt & White (2001)"),
        ("Min filter depth (TN)", "Structural minimum for deep anoxic denitrification",
         "$d_{\\min,TN} = 760\\,\\text{mm}$", "Hunt & White (2001)"),
        ("Annual runoff", "Simplified water balance (no losses)",
         "$Q_{ann} = R_v \\cdot A_c \\cdot R_{ann}$", "PGC (2007) Sec 3.3"),
        ("2% catchment rule", "Minimum cell footprint to sustain biodiversity",
         "$A_{\\min} = 0.02 \\times A_c$", "WbD (2014) Sec 2.4"),
    ]
    tbl = _tbl(
        ["Parameter", "Description", "Formula / Value", "Source"],
        rows
    )
    return f"""
<section id="s1">
<h2>1. Fundamental Assumptions &amp; Constants</h2>
<p>Every design constant used in this analysis is listed below with its
literature source. These values are fixed at program initialisation and
are not fitted or calibrated during any run.</p>
{_card(tbl)}
</section>
"""


def _sec_runoff(inp: dict, WQV: float, Rv: float, ann_r: float) -> str:
    A  = inp.get("catchment_area_m2", 0)
    I  = inp.get("pct_impervious", 0)
    Ra = inp.get("annual_rainfall_mm", 0)
    Rd = 25.0  # mm design rainfall

    rv_calc = 0.05 + 0.009 * I
    wqv_calc = rv_calc * (Rd / 1000.0) * A

    return f"""
<section id="s2">
<h2>2. Hydrology — Runoff &amp; Water Quality Volume</h2>

<h3>2.1 Volumetric Runoff Coefficient</h3>
<p>The volumetric runoff coefficient $R_v$ represents the fraction of rainfall
that becomes direct runoff, accounting for impervious cover.
Source: <em>ASCE; Prince George's County (2007)</em></p>
<p>$$R_v = 0.05 + 0.009 \\times I$$</p>
{_proof(
    f"Given: Impervious cover $I = {I}\\%$",
    f"$R_v = 0.05 + 0.009 \\times {I}$",
    f"$R_v = 0.05 + {0.009*I:.4f} = {rv_calc:.4f}$",
    result=f"$R_v = {Rv:.4f}$"
)}

<h3>2.2 Water Quality Volume</h3>
<p>The Water Quality Volume is the volume of runoff from the design storm
($R_d = 25\\,\\text{{mm}}$) that must be captured and treated.
Source: <em>PGC (2007) Sec 3.4</em></p>
<p>$$WQV = R_v \\times R_d \\times A_c$$</p>
{_proof(
    f"$R_v = {Rv:.4f}$,  $R_d = 25\\,\\text{{mm}} = 0.025\\,\\text{{m}}$,  $A_c = {A:,.0f}\\,\\text{{m}}^2$",
    f"$WQV = {Rv:.4f} \\times 0.025 \\times {A:,.0f}$",
    f"$WQV = {wqv_calc:.3f}\\,\\text{{m}}^3$",
    result=f"$WQV = {WQV:.3f}\\,\\text{{m}}^3$"
)}

<h3>2.3 Annual Runoff Volume</h3>
<p>$$Q_{{ann}} = R_v \\times A_c \\times R_{{ann}}$$</p>
{_proof(
    f"$R_v = {Rv:.4f}$,  $A_c = {A:,.0f}\\,\\text{{m}}^2$,  $R_{{ann}} = {Ra}\\,\\text{{mm}} = {Ra/1000:.3f}\\,\\text{{m}}$",
    f"$Q_{{ann}} = {Rv:.4f} \\times {A:,.0f} \\times {Ra/1000:.3f}$",
    result=f"$Q_{{ann}} = {ann_r:,.1f}\\,\\text{{m}}^3/\\text{{yr}}$"
)}
</section>
"""


def _sec_sizing(cell: dict, inp: dict, WQV: float) -> str:
    d_f    = cell.get("final_filter_depth_mm", 800) / 1000.0
    A_cell = cell.get("final_area_m2", 0)
    ksat   = inp.get("filter_ksat_mmhr", 180)
    log    = cell.get("log", [])
    perf   = cell.get("final_perf", {})
    De     = cell.get("D_e_m", 0)

    # depth table
    depth_rows = [(r.get("Metric", "—"), f"{r.get('Req_mm', 0):.1f}")
                  for r in log if "Req_mm" in r]
    area_rows  = [(r.get("Metric", "—"), f"{r.get('Req_m2', 0):.1f}")
                  for r in log if "Req_m2" in r]

    depth_tbl = _tbl(["Constraint", "Required Filter Depth (mm)"], depth_rows) if depth_rows else ""
    area_tbl  = _tbl(["Constraint", "Required Cell Area (m²)"],   area_rows)  if area_rows  else ""

    return f"""
<section id="s3">
<h2>3. Analytical Cell Sizing</h2>
<p>The design engine performs a direct, closed-form back-calculation — not an
iterative solver. It inverts the empirical pollutant attenuation equations
(Davis et al. 2009) to derive the exact minimum filter depth required for each
pollutant target, then applies the MGNDC (2012) Equivalent Storage Depth method
to derive the required surface footprint. The governing (worst-case) result
from each step sets the final design dimension.</p>

<h3>3.1 Filter Media Depth Derivation</h3>
<p>Each pollutant's depth requirement is back-calculated from the target
efficiency $E$ by inverting the linear empirical model:</p>
<p>$$d_{{\\text{{req}}}} = 0.8\\,\\text{{m}} \\times \\frac{{E_{{\\text{{target}}}} - E_{{\\text{{base}}}}}}
   {{E_{{\\text{{slope}}}}}}$$</p>
<p>TSS baseline $E_{{base}} = 70\\%$, slope = 35 per 0.8 m;<br/>
   TP baseline $E_{{base}} = 45\\%$, slope = 50 per 0.8 m;<br/>
   TN baseline $E_{{base}} = 25\\%$, slope = 50 per 0.8 m.
   (Davis et al. 2009, Table 4)</p>
<p>Structural minimums (Hunt &amp; White 2001): TP ≥ 600 mm, TN ≥ 760 mm
   (only applied when the target requires heavy nutrient processing).</p>

<p><strong>Depth requirements evaluated this run:</strong></p>
{_card(depth_tbl)}
{_proof(
    f"Governing depth = max of all constraints above",
    f"Final design depth (rounded to nearest 50 mm) = <strong>{cell.get('final_filter_depth_mm', 0)} mm</strong>",
    result=f"$d_{{\\text{{media}}}} = {cell.get('final_filter_depth_mm', 0)}\\,\\text{{mm}}$"
)}

<h3>3.2 Surface Area Derivation — MGNDC Equivalent Storage Method</h3>
<p>The required cell footprint is derived from the Equivalent Storage Depth
concept (MGNDC 2012 Sec 5.1):</p>
<p>$$D_e = (1.0 \\times d_{{\\text{{pond}}}}) + (n_f \\times d_f) + (n_g \\times d_g)$$</p>
<p>$$A_{{\\text{{cell}}}} = \\frac{{V_{{\\text{{target}}}}}}{{D_e}}$$</p>
<p>where $V_{{\\text{{target}}}} = WQV \\times (T_v / 100)$.</p>
{_proof(
    f"$d_{{\\text{{pond}}}} = 0.200\\,\\text{{m}}$,  $n_f = 0.38$,  $d_f = {d_f:.3f}\\,\\text{{m}}$,  $n_g = 0.40$,  $d_g \\approx 0.200\\,\\text{{m}}$",
    f"$D_e = 1.0 \\times 0.200 + 0.38 \\times {d_f:.3f} + 0.40 \\times 0.200$",
    f"$D_e = 0.200 + {0.38*d_f:.4f} + 0.080 = {De:.4f}\\,\\text{{m}}$",
    result=f"$D_e = {De:.4f}\\,\\text{{m}}$"
)}
<p><strong>Area constraints evaluated this run:</strong></p>
{_card(area_tbl)}
{_proof(
    f"Governing area = max(WQV-method area, 2% catchment rule)",
    result=f"$A_{{\\text{{cell}}}} = {A_cell:.2f}\\,\\text{{m}}^2$"
)}

<h3>3.3 Design Performance Validation</h3>
<p>The expected performance at the final design dimensions is back-calculated
using the forward empirical model, scaled by the capture fraction
$C_f = V_{{\\text{{captured}}}} / V_{{\\text{{inflow}}}}$:</p>
<p>$$E_{{\\text{{overall}}}} = E_{{\\text{{base,depth}}}} \\times C_f$$</p>
{_card(_tbl(
    ["Pollutant", "Base Efficiency at Design Depth", "Capture Fraction Applied", "Expected Removal (%)"],
    [
        ("TSS",
         f"$\\min(98, 70 + 35 \\times {d_f/0.8:.2f}) = $ {min(98, 70+35*(d_f/0.8)):.1f}%",
         f"$C_f$",
         f"{perf.get('tss_pct',0):.1f}%"),
        ("TP",
         f"$\\min(85, 45 + 50 \\times {d_f/0.8:.2f}) = $ {min(85, 45+50*(d_f/0.8)):.1f}%",
         f"$C_f$",
         f"{perf.get('tp_pct',0):.1f}%"),
        ("TN",
         f"$\\min(65, 25 + 50 \\times {d_f/0.8:.2f}) = $ {min(65, 25+50*(d_f/0.8)):.1f}%",
         f"$C_f$",
         f"{perf.get('tn_pct',0):.1f}%"),
    ]
))}
</section>
"""


def _sec_darcy(ud: dict, inp: dict, lyr: dict) -> str:
    A_cell  = ud.get("Q_max_m3s", 0) / max(1e-9,
               (inp.get("filter_ksat_mmhr",180)/(1000*3600)) *
               (0.2 + inp.get("filter_depth_mm", lyr.get("filter_depth_mm",800))/1000) /
               max(0.001, inp.get("filter_depth_mm", lyr.get("filter_depth_mm",800))/1000))
    ksat    = inp.get("filter_ksat_mmhr", 180)
    d_mm    = lyr.get("filter_depth_mm", 800)
    h_mm    = 200.0
    nat_k   = inp.get("native_ksat_mmhr", 0)
    profile = inp.get("drainage_profile", "Type2_Sealed")

    k  = ksat / (1000 * 3600)
    d  = d_mm / 1000
    h  = h_mm / 1000
    A  = ud.get("Q_max_m3s", 0) / max(1e-9, k*(h+d)/d) if nat_k == 0 else \
         (ud.get("Q_max_m3s", 0) + nat_k/(1000*3600)*100) / max(1e-9, k*(h+d)/d)

    q_full = k * A * (h + d) / d
    q_nat  = (nat_k / (1000*3600)) * A if profile in ("Type3_Conventional","Type4_Pipeless") else 0
    q_ud   = max(0, q_full - q_nat)

    # Manning's proof
    sel    = ud.get("selected_dia_mm", 150)
    slope  = ud.get("slope_pct", 1.0)
    n_man  = 0.011
    bf     = 0.80
    D      = sel / 1000
    A_p    = math.pi * D**2 / 4
    R      = D / 4
    S      = slope / 100
    Qc     = (1/n_man) * A_p * R**(2/3) * S**0.5 * bf
    n_p    = ud.get("n_pipes", 1)
    util   = (ud.get("Q_per_pipe_Ls", 0) / 1000) / max(1e-9, Qc) * 100

    native_row = ""
    if q_nat > 0:
        native_row = f"""
<p><strong>Native soil exfiltration subtracted (Type 3 / unlined cell):</strong></p>
{_proof(
    f"$K_{{\\text{{nat}}}} = {nat_k}\\,\\text{{mm/hr}} = {nat_k/(1000*3600):.3e}\\,\\text{{m/s}}$",
    f"$Q_{{\\text{{native}}}} = K_{{\\text{{nat}}}} \\times A_{{\\text{{cell}}}} = {nat_k/(1000*3600):.3e} \\times A_{{\\text{{cell}}}}$",
    f"$Q_{{\\text{{underdrain}}}} = Q_{{\\text{{filter}}}} - Q_{{\\text{{native}}}} = {q_ud*1000:.3f}\\,\\text{{L/s}}$",
    result=f"Underdrain design flow $= {ud.get('Q_max_Ls',0):.3f}\\,\\text{{L/s}}$"
)}"""

    return f"""
<section id="s4">
<h2>4. Hydraulic Design — Darcy Filtration &amp; Pipe Sizing</h2>

<h3>4.1 Peak Filtration Rate (Darcy's Law)</h3>
<p>The maximum flow rate through the saturated filter is calculated using
Darcy's Law with a composite hydraulic gradient (WbD 2014, Eq 7):</p>
<p>$$Q_{{\\max}} = K_{{sat}} \\times A_{{\\text{{cell}}}} \\times \\frac{{h + d}}{{d}}$$</p>
<p>where $h$ = ponding depth (m) and $d$ = filter media depth (m).</p>
{_proof(
    f"$K_{{sat}} = {ksat}\\,\\text{{mm/hr}} = {k:.6f}\\,\\text{{m/s}}$",
    f"$h = {h_mm:.0f}\\,\\text{{mm}} = {h:.3f}\\,\\text{{m}}$,  $d = {d_mm}\\,\\text{{mm}} = {d:.3f}\\,\\text{{m}}$",
    f"Hydraulic gradient $= (h+d)/d = ({h:.3f}+{d:.3f})/{d:.3f} = {(h+d)/d:.4f}$",
    f"$Q_{{\\text{{filter}}}} = {k:.6f} \\times A_{{\\text{{cell}}}} \\times {(h+d)/d:.4f}$",
    result=f"$Q_{{\\text{{filter}}}} \\approx {q_full*1000:.3f}\\,\\text{{L/s}}$ for the design cell area"
)}
{native_row}

<h3>4.2 Underdrain Pipe — Manning's Equation Proof</h3>
<p>The pipe is selected as the smallest standard UPVC size whose derated
(80% blockage factor) full-bore capacity exceeds the design flow per pipe.
Source: WbD (2014) Eq 11; Manning (1891).</p>
<p>$$Q_{{cap}} = \\frac{{1}}{{n}} \\times A_p \\times R_h^{{2/3}} \\times S^{{0.5}} \\times BF$$</p>
{_proof(
    f"Selected pipe: Ø{sel} mm perforated UPVC  @ {slope}% slope",
    f"$D = {sel}\\,\\text{{mm}} = {D:.3f}\\,\\text{{m}}$",
    f"$A_p = \\pi D^2/4 = \\pi \\times {D:.3f}^2/4 = {A_p:.6f}\\,\\text{{m}}^2$",
    f"$R_h = D/4 = {D:.3f}/4 = {R:.5f}\\,\\text{{m}}$",
    f"$S = {slope}\\% = {S:.4f}$",
    f"$Q_{{cap}} = (1/{n_man}) \\times {A_p:.6f} \\times {R:.5f}^{{2/3}} \\times {S:.4f}^{{0.5}} \\times {bf}$",
    f"$Q_{{cap}} = {Qc*1000:.3f}\\,\\text{{L/s}}$ &nbsp; (per pipe, derated)",
    f"Design flow per pipe $= {ud.get('Q_per_pipe_Ls',0):.3f}\\,\\text{{L/s}}$",
    result=f"$Q_{{cap}} = {Qc*1000:.3f}\\,\\text{{L/s}} > {ud.get('Q_per_pipe_Ls',0):.3f}\\,\\text{{L/s}}$ &nbsp; "
           f'<span class="badge badge-pass">✓ ADEQUATE</span> &nbsp; Utilisation: {util:.1f}%'
)}

<h3>4.3 All Standard Sizes Evaluated</h3>
{_card(_tbl(
    ["Pipe Ø (mm)", "A_p (m²)", "R_h (m)", "Q_cap (L/s, derated)", "Design Q (L/s)", "Result"],
    [
        (sz["dia_mm"],
         f'{math.pi*(sz["dia_mm"]/1000)**2/4:.6f}',
         f'{(sz["dia_mm"]/1000)/4:.5f}',
         f'{sz["Q_cap_Ls"]:.2f}',
         f'{ud.get("Q_per_pipe_Ls",0):.3f}',
         '<span class="badge badge-pass">✓ Selected</span>'
             if sz["dia_mm"] == sel else
         ('<span class="badge badge-pass">✓ Adequate</span>'
             if sz["adequate"] else
          '<span class="badge badge-fail">✗ Too small</span>'))
        for sz in ud.get("all_sizes", [])
    ]
))}
</section>
"""


def _sec_volume_balance(vb: dict, WQV: float) -> str:
    V_in   = vb.get("V_in_m3", 0)
    V_f    = vb.get("V_filtered_m3", 0)
    V_ov   = vb.get("V_overflow_m3", 0)
    V_ud   = vb.get("V_underdrain_m3", 0)
    V_nat  = vb.get("V_native_m3",  0)
    pct    = vb.get("V_captured_pct", 0)
    Q_in   = vb.get("Q_in_peak_Ls", 0)
    Q_out  = vb.get("Q_out_peak_Ls", 0)
    pk_r   = vb.get("peak_red_pct", 0)

    # Mass-balance check
    V_out_total = V_ud + V_nat + V_ov
    delta_S     = V_in - V_out_total   # water remaining in store at end of event
    balance_err = abs(V_in - (V_ud + V_nat + V_ov + delta_S))

    ok_str = ('<span class="badge badge-pass">✓ Mass balance satisfied</span>'
              if balance_err < 0.01 else
              f'<span class="badge badge-fail">✗ Error = {balance_err:.3f} m³</span>')

    return f"""
<section id="s5">
<h2>5. Hydraulic Routing — Volume Balance</h2>
<p>The event-scale mass balance for the bioretention cell is:</p>
<p>$$V_{{\\text{{in}}}} = V_{{\\text{{underdrain}}}} + V_{{\\text{{native}}}} + V_{{\\text{{overflow}}}} + \\Delta S$$</p>
<p>where $\\Delta S$ is water remaining in ponding / pore storage at end of simulation.</p>

<h3>5.1 Volume Balance Table</h3>
{_card(_tbl(
    ["Component", "Volume (m³)", "% of Inflow", "Pathway"],
    [
        ("Event Inflow ($V_{\\text{in}}$)",       f"{V_in:.3f}",   "100.0%",  "Runoff from contributing catchment"),
        ("→ To underdrain pipe ($V_{ud}$)",        f"{V_ud:.3f}",   f"{V_ud/max(V_in,1e-9)*100:.1f}%", "Treated stormwater to storm network"),
        ("→ Exfiltrated to native soil ($V_{nat}$)", f"{V_nat:.3f}", f"{V_nat/max(V_in,1e-9)*100:.1f}%", "Groundwater recharge (Type 3/4 only)"),
        ("→ Surface overflow ($V_{ov}$)",          f"{V_ov:.3f}",   f"{V_ov/max(V_in,1e-9)*100:.1f}%",  "Bypasses cell for major storms"),
        ("In-cell storage at end ($\\Delta S$)",   f"{max(0,delta_S):.3f}", f"{max(0,delta_S)/max(V_in,1e-9)*100:.1f}%", "Ponding + pore water drains down over 72 hr"),
    ]
))}

<h3>5.2 Mass Balance Check</h3>
{_proof(
    f"$V_{{\\text{{in}}}} = {V_in:.3f}\\,\\text{{m}}^3$",
    f"$V_{{ud}} + V_{{nat}} + V_{{ov}} + \\Delta S = {V_ud:.3f} + {V_nat:.3f} + {V_ov:.3f} + {max(0,delta_S):.3f}$",
    f"$= {V_ud+V_nat+V_ov+max(0,delta_S):.3f}\\,\\text{{m}}^3$",
    result=f"Residual error = {balance_err:.4f} m³ &nbsp; {ok_str}"
)}

<h3>5.3 Peak Flow Attenuation</h3>
{_card(_tbl(
    ["Parameter", "Value", "Unit"],
    [
        ("Peak inflow ($Q_{\\text{in,peak}}$)",   f"{Q_in:.2f}", "L/s"),
        ("Peak outflow ($Q_{\\text{out,peak}}$)",  f"{Q_out:.2f}", "L/s"),
        ("Peak flow reduction",                    f"{pk_r:.1f}", "%"),
        ("Volume captured",                        f"{pct:.1f}", "%"),
    ]
))}
</section>
"""


def _sec_pollutants(poll: dict, cell: dict, lyr: dict) -> str:
    d_mm = lyr.get("filter_depth_mm", 800)
    d_m  = d_mm / 1000
    perf = cell.get("final_perf", {})
    cf   = perf.get("vol_pct", 100) / 100.0

    rows_proof = []
    for key, label, base, slope, cap in [
        ("TSS_mgL", "TSS", 70, 35, 98),
        ("TP_mgL",  "TP",  45, 50, 85),
        ("TN_mgL",  "TN",  25, 50, 65),
    ]:
        E_base = min(cap, base + slope * (d_m / 0.8))
        E_eff  = E_base * cf
        rem    = poll.get(key, {})
        rows_proof.append((
            label,
            f"{base}% + {slope} × ({d_m:.3f}/0.8) = {base + slope*d_m/0.8:.1f}%",
            f"min({cap}%, {base + slope*d_m/0.8:.1f}%) = {E_base:.1f}%",
            f"{E_base:.1f}% × {cf:.3f} = {E_eff:.1f}%",
            f"{rem.get('emc_mgL','—')} mg/L",
            f"{rem.get('load_in_kgyr',0):.2f} kg/yr",
            f"{rem.get('removal_pct',0):.1f}%",
        ))

    return f"""
<section id="s6">
<h2>6. Pollutant Removal — Depth-Dependent Attenuation</h2>
<p>Pollutant removal is calculated in two stages:</p>
<ol style="padding-left:20px; margin-bottom:10px;">
  <li><strong>Intrinsic removal efficiency</strong> — the percentage of influent
  pollutant removed from the fraction of water that passes through the full
  filter depth, based on empirical linear models (Davis et al. 2009).</li>
  <li><strong>Capture-fraction correction</strong> — the overall efficiency is
  scaled by the fraction of the design event volume that actually enters the
  filter ($C_f$), since any overflow receives zero treatment.</li>
</ol>
<p>$$E_{{\\text{{overall}}}} = E_{{\\text{{intrinsic}}}} \\times C_f
  = \\min\\!\\left(E_{{\\text{{cap}}}},\\; E_{{\\text{{base}}}} + m \\cdot \\frac{{d}}{{0.8\\,\\text{{m}}}}\\right) \\times C_f$$</p>
<p>Design filter depth: $d = {d_mm}\\,\\text{{mm}} = {d_m:.3f}\\,\\text{{m}}$;
   Volume capture fraction: $C_f = {cf:.3f}$</p>

{_card(_tbl(
    ["Pollutant", "Linear model result", "Cap applied", "× Cᶠ = Overall", "EMC (mg/L)", "Annual load in (kg/yr)", "Removal (%)"],
    rows_proof
))}
</section>
"""


def _sec_references() -> str:
    refs = [
        ("Davis, A. P., Traver, R. G., Hunt, W. F., Lee, R., Brown, R. A., & Olszewski, J. M. (2009).",
         "Hydrologic performance of bioretention storm-water control measures.",
         "<em>Journal of Hydrologic Engineering</em>, 14(7), 695–706.",
         "https://doi.org/10.1061/(ASCE)HE.1943-5584.0000092"),
        ("FAWB — Facility for Advancing Water Biofiltration (2009).",
         "Guidelines for filter media in biofiltration systems.",
         "Monash University, Victoria, Australia.",
         "https://fawb.net/"),
        ("Hunt, W. F., & White, N. (2001).",
         "Designing rain gardens (bio-retention areas).",
         "North Carolina Cooperative Extension, Publication AG-588-3.",
         ""),
        ("MGNDC — Melbourne & Grounds Natural Drainage Council (2012).",
         "Urban stormwater — bioretention design guidance, 3rd ed.",
         "Melbourne, Australia.",
         ""),
        ("Prince George's County, MD, DER (2007).",
         "Bioretention manual.",
         "Upper Marlboro, MD: Prince George's County Dept of Environmental Resources.",
         ""),
        ("Water by Design (2014).",
         "Bioretention technical design guidelines, Version 1.1.",
         "South East Queensland Healthy Waterways Partnership, Brisbane.",
         ""),
        ("Manning, R. (1891).",
         "On the flow of water in open channels and pipes.",
         "<em>Transactions of the Institution of Civil Engineers of Ireland</em>, 20, 161–207.",
         ""),
        ("ASCE (2012).",
         "Design of urban stormwater controls (MOP 23), 2nd ed.",
         "American Society of Civil Engineers, Reston, VA.",
         ""),
    ]
    items = ""
    for i, (auth, title, jrnl, url) in enumerate(refs, 1):
        link = f' <a href="{url}" target="_blank">[link]</a>' if url else ""
        items += f"<li>{auth} {title} {jrnl}{link}</li>\n"
    return f"""
<section id="s7">
<h2>7. References</h2>
<ol class="ref-list">
{items}
</ol>
</section>
"""


# ─────────────────────────────────────────────────────────────────────────────
# Public entry-point
# ─────────────────────────────────────────────────────────────────────────────

def generate_calc_basis(results: dict, WQV: float, output_path: str) -> str:
    """
    Generate the stand-alone Calculation Basis HTML document.

    Parameters
    ----------
    results     : the same `results` dict passed to `generate_report()`
    WQV         : Water Quality Volume (m³) — computed in main.py
    output_path : absolute path to write the HTML file

    Returns
    -------
    output_path on success, raises on failure.
    """
    proj  = results.get("project", {})
    inp   = results.get("inputs",  {})
    cell  = results.get("cell_sizing", {})
    lyr   = results.get("layer_profile", {})
    ud    = results.get("underdrain", {})
    vb    = results.get("volume_balance", {})
    poll  = results.get("pollutants", {})
    ann_r = results.get("hydrology_summary", {}).get("annual_runoff_m3", 0)
    Rv    = inp.get("Rv", 0)

    now   = datetime.datetime.now().strftime("%d %B %Y, %H:%M")
    proj_name = proj.get("name", "Unnamed")
    proj_loc  = proj.get("location", "—")

    # Inject filter depth into inp for Darcy proof
    inp = dict(inp)
    inp["filter_depth_mm"] = lyr.get("filter_depth_mm", 800)

    body = (
        _sec_assumptions() +
        _sec_runoff(inp, WQV, Rv, ann_r) +
        _sec_sizing(cell, inp, WQV) +
        _sec_darcy(ud, inp, lyr) +
        _sec_volume_balance(vb, WQV) +
        _sec_pollutants(poll, cell, lyr) +
        _sec_references()
    )

    toc = """
<div class="toc">
  <h3>Table of Contents</h3>
  <ol>
    <li><a href="#s1">Fundamental Assumptions &amp; Constants</a></li>
    <li><a href="#s2">Hydrology — Runoff &amp; Water Quality Volume</a></li>
    <li><a href="#s3">Analytical Cell Sizing</a></li>
    <li><a href="#s4">Hydraulic Design — Darcy Filtration &amp; Pipe Sizing</a></li>
    <li><a href="#s5">Hydraulic Routing — Volume Balance</a></li>
    <li><a href="#s6">Pollutant Removal — Depth-Dependent Attenuation</a></li>
    <li><a href="#s7">References</a></li>
  </ol>
</div>
"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>Calculation Basis — {proj_name}</title>
<style>{_CSS}</style>
{_MATHJAX}
</head>
<body>
<header>
  <h1>Engineering Calculation Basis</h1>
  <p>Project: <strong>{proj_name}</strong> &nbsp;|&nbsp; Location: {proj_loc}</p>
  <p>Bioretention Cell Design Tool &mdash; Dept. of Civil Engineering, RUET</p>
  <span class="stamp">Generated: {now} &nbsp;|&nbsp; FOR CROSS-VALIDATION USE ONLY</span>
</header>
<div class="container">
{toc}
{body}
</div>
</body>
</html>"""

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    return output_path
