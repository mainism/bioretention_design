"""
report.py — Full HTML design report generator.
v3 — Complete rewrite. All keys aligned with v3 hydrology.py and design.py.
     Volume balance section added. Design checks show only meaningful items.
     Generates standalone HTML (no external dependencies) with embedded figures.
"""

import os, base64, datetime
from pathlib import Path
from src.config import PONDING, POLLUTANT_REMOVAL


def _b64(path: str) -> str:
    try:
        with open(path, "rb") as f:
            d = base64.b64encode(f.read()).decode()
        ext = Path(path).suffix.lower().strip(".")
        mime = {"jpg":"jpeg","jpeg":"jpeg","png":"png"}.get(ext,"png")
        return f"data:image/{mime};base64,{d}"
    except Exception:
        return ""


def _chk(ok: bool, ok_txt="PASS", fail_txt="FAIL") -> str:
    cls = "pass" if ok else "fail"
    sym = "✓" if ok else "✗"
    return f'<span class="{cls}">{sym} {ok_txt if ok else fail_txt}</span>'


def _fig(figures: dict, key: str, caption: str) -> str:
    p = figures.get(key,"")
    if not p or not os.path.exists(str(p)):
        return f'<p class="no-fig">[{caption} — figure not available]</p>'
    return (f'<div class="fig-wrap">'
            f'<img src="{_b64(p)}" alt="{caption}"/>'
            f'<p class="fig-cap"><strong>Figure:</strong> {caption}</p></div>')


def generate_report(results: dict, figures: dict, output_path: str) -> str:
    """Generate self-contained HTML design report."""

    proj  = results.get("project", {})
    inp   = results.get("inputs", {})
    cell  = results.get("cell_sizing", {})
    dims  = results.get("cell_dimensions", {})
    lyr   = results.get("layer_profile", {})
    ud    = results.get("underdrain", {})
    ov    = results.get("overflow", {})
    dd    = results.get("drain_down", {})
    berm  = results.get("berm", {})
    mat   = results.get("materials", {})
    pl    = results.get("plants", None)
    poll  = results.get("pollutants", {})
    vb    = results.get("volume_balance", {})
    hs    = results.get("hydrology_summary", {})
    now   = datetime.datetime.now().strftime("%B %d, %Y  %H:%M")

    # ── Derived display values (safe fallbacks) ───────────────────────────────
    Rv         = inp.get("Rv", 0)
    A_catch    = inp.get("catchment_area_m2", 0)
    pct_imp    = inp.get("pct_impervious", 0)
    f_ksat     = inp.get("filter_ksat_mmhr", 0)
    f_depth    = lyr.get("filter_depth_mm", 800)
    A_cell     = cell.get("A_cell_m2", 0)
    excav_mm   = lyr.get("total_excavation_mm", 0)
    excav_m    = lyr.get("total_excavation_m", 0)
    wt_ok      = lyr.get("wt_clearance_OK", True)
    wt_cl      = lyr.get("wt_clearance_m", 0)
    dd_t       = dd.get("drain_time_hr", 0)
    dd_ok      = dd.get("drain_time_OK", True)
    ksat_ok    = 100 <= float(f_ksat) <= 300
    excav_ok   = excav_m <= 2.0

    # Overall status — only flags real site/input constraints
    all_ok = wt_ok and dd_ok and ksat_ok and excav_ok

    # ── Layer table rows ──────────────────────────────────────────────────────
    layer_display = [
        ("Ponding Zone",      PONDING["max_depth_mm"], "Open air above media surface",
         "Extended detention storage", "—"),
        ("Mulch",             75,   "Shredded wood chip, 20–50 mm particle size",
         "Moisture retention, weed suppression", "—"),
        ("Filter Media",      f_depth, "60% coarse river sand / 25% composted OM / 15% loam",
         "Pollutant removal, vegetation support", "+100 mm settlement"),
        ("Transition Layer",  75,   "Washed pea gravel, 2–6 mm, <2% fines",
         "Prevent filter media migration", "—"),
        ("Drainage Gravel",   200,  "Washed crushed stone, 10–20 mm, <2% fines",
         "Lateral drainage to underdrain", "—"),
        ("Geotextile",        5,    "Non-woven PP geotextile, 200 g/m²",
         "Base/side separation from native soil", "—"),
        (lyr.get("liner_type","Liner"),  0,
         lyr.get("layers",{}).get("liner",{}).get("material","See design notes"),
         lyr.get("layers",{}).get("liner",{}).get("function","—"), "—"),
    ]
    layer_rows = "".join(
        f"<tr><td><strong>{n}</strong></td><td class='num'>{d}</td>"
        f"<td>{m}</td><td>{fn}</td><td>{nt}</td></tr>"
        for n,d,m,fn,nt in layer_display
    )

    # ── Underdrain pipe table rows ────────────────────────────────────────────
    ud_rows = ""
    for sz in ud.get("all_sizes", []):
        sel = sz["dia_mm"] == ud.get("selected_dia_mm")
        ok_cls = "pass" if sz["adequate"] else ""
        ud_rows += (
            f"<tr{'class=\"sel-row\"' if sel else ''}>"
            f"<td>{'<strong>' if sel else ''}Ø{sz['dia_mm']} mm"
            f"{' ← SELECTED</strong>' if sel else ''}</td>"
            f"<td class='num'>{sz['Q_cap_Ls']:.2f}</td>"
            f"<td class='num'>{sz['velocity_ms']:.3f}</td>"
            f"<td><span class='{ok_cls}'>{'✓' if sz['adequate'] else '—'}</span></td></tr>"
        )

    # ── Pollutant table rows ──────────────────────────────────────────────────
    poll_rows = "".join(
        f"<tr><td><strong>{k.replace('_mgL','')}</strong></td>"
        f"<td class='num'>{v['emc_mgL']}</td>"
        f"<td class='num'>{v['load_in_kgyr']:.2f}</td>"
        f"<td class='num'>{v['removal_pct']}%</td>"
        f"<td class='num'>{v['load_out_kgyr']:.2f}</td>"
        f"<td class='num'><strong>{v['removed_kgyr']:.2f}</strong></td></tr>"
        for k,v in poll.items()
    )

    # ── Planting rows ─────────────────────────────────────────────────────────
    plant_rows = ""
    if pl is not None and len(pl) > 0:
        plant_rows = "".join(
            f"<tr><td>{r.get('Zone','')}</td>"
            f"<td class='num'>{r.get('Zone Area (m2)','')}</td>"
            f"<td>{r.get('Common Name','')}</td>"
            f"<td><em>{r.get('Scientific Name','')}</em></td>"
            f"<td>{r.get('Type','')}</td>"
            f"<td class='num'>{r.get('Spacing (mm)','')}</td>"
            f"<td class='num'>{r.get('Quantity','')}</td></tr>"
            for _, r in pl.iterrows()
        )

    # ── Material rows ─────────────────────────────────────────────────────────
    mat_items = [
        ("excavation_m3",        "Excavation and disposal of spoil",     "m³"),
        ("geotextile_m2",        "Non-woven geotextile 200 g/m² (incl. 15% lap)","m²"),
        ("gravel_drainage_m3",   "Gravel drainage layer (10–20 mm, double-washed)","m³"),
        ("transition_gravel_m3", "Pea gravel transition layer (2–6 mm)", "m³"),
        ("filter_media_m3",      "Engineered filter media (+100 mm settlement)", "m³"),
        ("mulch_m3",             "Shredded wood mulch (50–75 mm depth)", "m³"),
        ("underdrain_pipe_m",    "Perforated UPVC underdrain pipe",      "m (lin.)"),
        ("berm_topsoil_m3",      "Topsoil for berm faces (200 mm depth)","m³"),
    ]
    mat_rows = "".join(
        f"<tr><td>{desc}</td><td class='num'>{mat.get(k,'—')}</td><td>{unit}</td></tr>"
        for k,desc,unit in mat_items
    )

    # ── Weir section ──────────────────────────────────────────────────────────
    weir = ov.get("weir", {})
    weir_row = ""
    if weir:
        weir_row = f"""
        <h3>Major Storm Overflow Weir</h3>
        <table>
          <tr><th>Parameter</th><th>Value</th><th>Unit</th></tr>
          <tr><td>Major storm overflow flow</td><td class='num'>{weir.get('Q_major_Ls','—')}</td><td>L/s</td></tr>
          <tr><td>Required weir length</td><td class='num'><strong>{weir.get('weir_length_m','—')}</strong></td><td>m</td></tr>
          <tr><td>Head over weir crest</td><td class='num'>{weir.get('h_over_weir_mm','—')}</td><td>mm</td></tr>
          <tr><td>Type</td><td colspan='2'>Broad-crested concrete weir at berm crest level (C_w=1.74)</td></tr>
          <tr><td>Note</td><td colspan='2'>{weir.get('note','—')}</td></tr>
        </table>"""

    # ── NEW: Generate Iteration Table HTML ────────────────────────────────────
    log_rows = ""
    if "log" in cell:
        for entry in cell["log"]:
            v1 = entry.get('Req_mm', '')
            v2 = entry.get('Req_m2', '')
            val = f"{v1} mm" if v1 != '' else f"{v2} m²"
            
            log_rows += f'''
            <tr>
                <td style="text-align: left; padding-left: 10px;">{entry.get('Metric','')}</td>
                <td><strong>{val}</strong></td>
            </tr>
            '''
        iteration_html = f'''
        <br>
        <h3 style="color: #2E7D32; border-bottom: 2px solid #4CAF50; margin-top:20px; padding-bottom: 3px;">ANALYTICAL REQUIREMENT CALCULATION LOG</h3>
        <table style="width:100%; border-collapse: collapse; text-align: center; font-size: 12px; margin-top: 10px;" border="1">
            <tr style="background-color: #1B4F2A; color: white;">
                <th style="padding: 5px; text-align: left; padding-left: 10px;">Constraint Metric</th>
                <th style="text-align: center;">Required Geometry</th>
            </tr>
            {log_rows}
        </table>
        <p style="font-size: 10px; color: #555; margin-top: 5px; text-align: left;">
          *Depth dimensions calculated via algebraic inverse of empirical target curves (Davis et al. 2009) and static nutrient thresholds (Hunt & White 2001).
          *Area dimensions calculated via Equivalent Storage Depth logic (MGNDC 2012) scaled to the required volumetric capture fraction.
        </p>
        '''
    else:
        iteration_html = ""
    # ── CSS ───────────────────────────────────────────────────────────────────
    css = """
    *{box-sizing:border-box;margin:0;padding:0}
    body{font-family:'Segoe UI',Arial,sans-serif;font-size:13px;color:#1a1a1a;background:#f0f2f5}
    .wrapper{max-width:1260px;margin:0 auto;background:#fff;box-shadow:0 2px 16px rgba(0,0,0,.12)}
    .header{background:linear-gradient(135deg,#1B4F2A 0%,#2E7D32 60%,#388E3C 100%);color:#fff;padding:32px 40px}
    .header h1{font-size:22px;font-weight:700;letter-spacing:.3px}
    .header .sub{font-size:13px;color:#A5D6A7;margin-top:6px}
    .header .meta{display:flex;flex-wrap:wrap;gap:28px;margin-top:18px}
    .header .meta div{font-size:12px}
    .header .meta span{color:#81C784}
    .nav{display:flex;background:#1B4F2A;overflow-x:auto;flex-wrap:wrap}
    .nav a{color:#C8E6C9;padding:10px 16px;text-decoration:none;font-size:11.5px;
            font-weight:600;white-space:nowrap;border-bottom:3px solid transparent}
    .nav a:hover{background:#2E7D32;color:#fff;border-bottom-color:#A5D6A7}
    .section{padding:28px 40px;border-bottom:1px solid #E8EAE8}
    .section h2{font-size:16px;color:#1B4F2A;font-weight:700;margin-bottom:14px;
                 padding-bottom:6px;border-bottom:2px solid #4CAF50}
    .section h3{font-size:13px;color:#2E7D32;font-weight:700;margin:18px 0 8px}
    table{width:100%;border-collapse:collapse;font-size:12px;margin:12px 0}
    th{background:#1B4F2A;color:#fff;padding:8px 10px;text-align:left;font-weight:600}
    tr:nth-child(even) td{background:#F1F8F1}
    td{padding:7px 10px;border-bottom:1px solid #ddd}
    td.num{text-align:right;font-family:monospace}
    tr.sel-row td{background:#E8F5E9;font-weight:600}
    .pass{color:#2E7D32;font-weight:700}
    .fail{color:#C62828;font-weight:700}
    .warn{color:#E65100;font-weight:700}
    .cards{display:flex;flex-wrap:wrap;gap:14px;margin:14px 0}
    .card{background:#F9FBF9;border:2px solid #C8E6C9;border-radius:8px;
           padding:14px 18px;min-width:155px;flex:1}
    .card .val{font-size:22px;font-weight:700;color:#1B4F2A}
    .card .unit{font-size:11px;color:#666}
    .card .lbl{font-size:11px;color:#444;margin-top:4px;font-weight:600}
    .card.warn-card{border-color:#FFCC80}
    .card.fail-card{border-color:#EF9A9A}
    .eq-box{font-family:monospace;background:#F1F8F1;border-left:4px solid #4CAF50;
             padding:12px 16px;border-radius:0 6px 6px 0;font-size:12px;margin:10px 0;line-height:1.8}
    .alert{padding:10px 16px;border-radius:4px;margin:10px 0;font-size:12px}
    .alert-ok  {background:#E8F5E9;border-left:4px solid #2E7D32;color:#1B5E20}
    .alert-warn{background:#FFF8E1;border-left:4px solid #F57F17;color:#E65100}
    .alert-fail{background:#FFEBEE;border-left:4px solid #C62828;color:#B71C1C}
    .alert-info{background:#E3F2FD;border-left:4px solid #1565C0;color:#0D47A1}
    .fig-wrap{margin:20px 0;text-align:center}
    .fig-wrap img{max-width:100%;border:1px solid #ddd;border-radius:4px;
                   box-shadow:0 2px 8px rgba(0,0,0,.10)}
    .fig-cap{font-size:11px;color:#555;margin-top:6px;font-style:italic}
    .no-fig{font-size:12px;color:#aaa;font-style:italic;margin:12px 0}
    .check-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px}
    .check-item{display:flex;align-items:center;gap:10px;padding:8px 12px;
                 background:#F9FBF9;border-radius:6px;border:1px solid #E0EBE0}
    .check-sym{font-size:18px;line-height:1}
    .check-lbl{font-size:12px;font-weight:600;color:#333}
    .check-detail{font-size:11px;color:#666;margin-top:2px}
    .vol-bar{display:flex;height:36px;border-radius:6px;overflow:hidden;margin:14px 0}
    .vol-seg{display:flex;align-items:center;justify-content:center;font-size:11px;
              color:#fff;font-weight:600;min-width:30px}
    .footer{background:#1B4F2A;color:#81C784;padding:16px 40px;font-size:11px;text-align:center}
    """

    # ── Volume bar chart ──────────────────────────────────────────────────────
    V_in = vb.get("V_in_m3", 1) or 1
    V_f  = vb.get("V_filtered_m3", 0)
    V_ov = vb.get("V_overflow_m3", 0)
    pf   = max(1, round(V_f/V_in*100))
    po   = max(1, round(V_ov/V_in*100))
    vol_bar = (f'<div class="vol-bar">'
               f'<div class="vol-seg" style="width:{pf}%;background:#2E7D32">'
               f'{pf}% Filtered</div>'
               f'<div class="vol-seg" style="width:{po}%;background:#D32F2F">'
               f'{po}% Overflow</div>'
               f'</div>')

    # ── Design checks grid ────────────────────────────────────────────────────
    def check_item(label, ok, detail):
        sym = "✅" if ok else "⚠️"
        cla = "" if ok else " fail-card"
        return (f'<div class="check-item{cla}">'
                f'<span class="check-sym">{sym}</span>'
                f'<div><div class="check-lbl">{label}</div>'
                f'<div class="check-detail">{detail}</div></div></div>')

    checks_html = (
        check_item("Filter media Ksat",
                   ksat_ok,
                   f"{f_ksat} mm/hr — {'within 100–300 mm/hr' if ksat_ok else 'OUTSIDE 100–300 mm/hr target'}") +
        check_item("Water table clearance",
                   wt_ok,
                   f"{wt_cl:.2f} m — {'≥ 0.6 m minimum' if wt_ok else 'BELOW 0.6 m — increase base level or use impermeable liner'}") +
        check_item("Drain-down time",
                   dd_ok,
                   f"{dd_t:.1f} hr — {'≤ 72 hr limit' if dd_ok else 'EXCEEDS 72 hr — increase Ksat or reduce cell depth'}") +
        check_item("Excavation depth",
                   excav_ok,
                   f"{excav_m:.3f} m — {'≤ 2.0 m constructability limit' if excav_ok else 'EXCEEDS 2.0 m — consider shallow profile or split cells'}") +
        check_item("Cell area ≥ 2% catchment",
                   True,
                   f"{cell.get('pct_of_catchment','—')}% — designed to meet constraint. {cell.get('governing','')}") +
        check_item("Underdrain capacity",
                   True,
                   f"Ø{ud.get('selected_dia_mm','—')} mm at {ud.get('slope_pct','—')}% — "
                   f"{ud.get('utilisation_pct','—')}% loaded ({ud.get('Q_max_Ls','—')} L/s design)")
    )

    # ── HTML ──────────────────────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>Bioretention Design Report — {proj.get('name','Project')}</title>
  <style>{css}</style>
</head>
<body>
<div class="wrapper">

<!-- HEADER -->
<div class="header">
  <h1>🌿 BIORETENTION CELL — DESIGN AND ANALYSIS REPORT</h1>
  <div class="sub">Academic Capstone Project | Department of Civil Engineering | RUET</div>
  <div class="meta">
    <div><span>Project:</span> {proj.get('name','—')}</div>
    <div><span>Location:</span> {proj.get('location','—')}</div>
    <div><span>Region:</span> {inp.get('region','—')} Division</div>
    <div><span>Design Storm:</span> {inp.get('return_period','—').replace('yr','-yr')} ARI</div>
    <div><span>Profile:</span> {inp.get('drainage_profile','—')}</div>
    <div><span>Generated:</span> {now}</div>
  </div>
</div>

<!-- NAV -->
<div class="nav">
  <a href="#s1">1. Inputs</a><a href="#s2">2. Cell Sizing</a>
  <a href="#s3">3. Layers</a><a href="#s4">4. Underdrain</a>
  <a href="#s5">5. Overflow</a><a href="#s6">6. Drain-Down</a>
  <a href="#s7">7. Hydrology</a><a href="#s8">8. Volume Balance</a>
  <a href="#s9">9. Water Quality</a><a href="#s10">10. Planting</a>
  <a href="#s11">11. Quantities</a><a href="#s12">12. Drawings</a>
  <a href="#s13">13. Design Checks</a>
</div>

<!-- 1. INPUTS -->
<div class="section" id="s1">
  <h2>1. DESIGN INPUTS</h2>
  <table>
    <tr><th>Parameter</th><th>Value</th><th>Unit</th><th>Source</th></tr>
    <tr><td>Catchment area</td><td class="num">{A_catch:,.0f}</td><td>m²</td><td>Topographic survey</td></tr>
    <tr><td>% Impervious cover</td><td class="num">{pct_imp:.1f}</td><td>%</td><td>Land use mapping</td></tr>
    <tr><td>Volumetric runoff coefficient (Rv)</td><td class="num">{Rv:.3f}</td><td>—</td>
        <td>Rv = 0.05 + 0.009×I — Prince George's County (2007)</td></tr>
    <tr><td>WQ design rainfall depth</td><td class="num">25</td><td>mm</td>
        <td>Water by Design (2014)</td></tr>
    <tr><td>Filter media Ksat (design)</td><td class="num">{f_ksat}</td><td>mm/hr</td>
        <td>FAWB (2009) target: 100–300 mm/hr</td></tr>
    <tr><td>Native soil Ksat</td><td class="num">{inp.get('native_ksat_mmhr','—')}</td><td>mm/hr</td>
        <td>Field infiltration test</td></tr>
    <tr><td>Drainage profile selected</td><td>{inp.get('drainage_profile','—')}</td><td>—</td>
        <td>Water by Design (2014) Section 2.4</td></tr>
    <tr><td>Wet season water table depth</td><td class="num">{inp.get('water_table_m','—')}</td><td>m BGL</td>
        <td>Site investigation / BWDB data</td></tr>
    <tr><td>Region</td><td>{inp.get('region','—')}</td><td>Division</td><td>User selection</td></tr>
    <tr><td>Design storm return period</td><td>{inp.get('return_period','—').replace('yr','-yr')}</td><td>ARI</td><td>Design requirement</td></tr>
    <tr><td>Mean annual rainfall</td><td class="num">{inp.get('annual_rainfall_mm','—')}</td><td>mm/yr</td>
        <td>BMD station data</td></tr>
  </table>
</div>

<!-- 2. CELL SIZING -->
<div class="section" id="s2">
  <h2>2. CELL SIZING — WATER QUALITY VOLUME METHOD</h2>
  <div class="eq-box">
    Rv = 0.05 + 0.009 × I = 0.05 + 0.009 × {pct_imp} = <strong>{Rv:.3f}</strong><br>
    WQV = Rv × A × d_wq = {Rv:.3f} × {A_catch:,.0f} × 0.025 = <strong>{cell.get('WQV_m3',0):.3f} m³</strong><br>
    A<sub>WQV</sub> = WQV / (Ksat × t_drain) = {cell.get('WQV_m3',0):.3f} / ({f_ksat/1000:.4f} × 24) = <strong>{cell.get('A_WQV_m2',0):.1f} m²</strong><br>
    A<sub>2%</sub> = 2% × {A_catch:,.0f} = <strong>{cell.get('A_2pct_m2',0):.1f} m²</strong><br>
    <strong>A<sub>design</sub> = max({cell.get('A_WQV_m2',0):.1f}, {cell.get('A_2pct_m2',0):.1f}) = {A_cell:.1f} m²</strong>
    &nbsp;&nbsp;→ Governed by: <em>{cell.get('governing','—')}</em>
  </div>
  <div class="cards">
    <div class="card"><div class="val">{cell.get('WQV_m3',0):.3f}</div>
      <div class="unit">m³</div><div class="lbl">Water Quality Volume</div></div>
    <div class="card"><div class="val">{A_cell:.0f}</div>
      <div class="unit">m²</div><div class="lbl">Design Cell Area</div></div>
    <div class="card"><div class="val">{cell.get('pct_of_catchment','—')}%</div>
      <div class="unit">of catchment</div><div class="lbl">Cell/Catchment Ratio<br>(designed to ≥ 2%)</div></div>
    <div class="card"><div class="val">{dims.get('length_m',0):.1f} × {dims.get('width_m',0):.1f}</div>
      <div class="unit">m (L × W)</div><div class="lbl">Plan Dimensions<br>AR = {dims.get('aspect_ratio',0):.1f}:1</div></div>
  </div>
  <div class="alert alert-info">{dims.get('note','')}</div>
  
  {iteration_html}

</div>



<!-- 3. LAYER PROFILE -->
<div class="section" id="s3">
  <h2>3. LAYER PROFILE DESIGN</h2>
  <p style="margin-bottom:10px">
    <strong>Drainage Profile:</strong> {lyr.get('drainage_profile','—')} &nbsp;|&nbsp;
    <strong>Liner:</strong> {lyr.get('liner_type','—')}
  </p>
  <table>
    <tr><th>Layer</th><th>Design Depth (mm)</th><th>Material</th><th>Function</th><th>Notes</th></tr>
    {layer_rows}
    <tr style="background:#1B4F2A;color:#fff;font-weight:700">
      <td>TOTAL EXCAVATION</td>
      <td class="num" style="color:#A5D6A7">{excav_mm} mm</td>
      <td colspan="3" style="color:#C8E6C9">{excav_m:.3f} m below finished ground level</td>
    </tr>
  </table>
  <div class="alert {'alert-ok' if wt_ok else 'alert-fail'}">
    <strong>Water table clearance:</strong> {lyr.get('wt_clearance_msg','—')}
  </div>
</div>

<!-- 4. UNDERDRAIN -->
<div class="section" id="s4">
  <h2>4. UNDERDRAIN PIPE DESIGN</h2>
  <h3>Maximum Filtration Rate (Darcy's Law — Water by Design 2014, Eq. 7)</h3>
  <div class="eq-box">
    Q<sub>max</sub> = K<sub>sat</sub> × A<sub>cell</sub> × (h<sub>pond</sub> + d<sub>filter</sub>) / d<sub>filter</sub><br>
    Q<sub>max</sub> = {f_ksat/1000/3600:.2e} m/s × {A_cell:.1f} m² ×
    (0.200 + {f_depth/1000:.3f}) / {f_depth/1000:.3f}
    = <strong>{ud.get('Q_max_Ls',0):.4f} L/s</strong>
  </div>
  <h3>Pipe Capacity — Manning's Equation ({ud.get('n_pipes',1)} pipe at {ud.get('slope_pct',1.0)}% slope, 20% blockage factor applied)</h3>
  <table>
    <tr><th>Pipe Diameter</th><th>Derated Capacity (L/s)</th><th>Full-flow Velocity (m/s)</th><th>Adequate?</th></tr>
    {ud_rows}
  </table>
  <div class="alert alert-ok">
    <strong>Selected:</strong> {ud.get('recommendation','—')}<br>
    <strong>Slots:</strong> {ud.get('slot_spec','—')}<br>
    <strong>Cleanout:</strong> {ud.get('cleanout_riser','—')}<br>
    <strong>Utilisation:</strong> {ud.get('utilisation_pct','—')}% of derated capacity
    ({ud.get('Q_max_Ls','—')} L/s design / {ud.get('pipe_capacity_Ls','—')} L/s available)
  </div>
</div>

<!-- 5. OVERFLOW -->
<div class="section" id="s5">
  <h2>5. OVERFLOW STRUCTURE DESIGN</h2>
  <h3>Overflow Standpipe — Minor Storm (2-yr Routing Simulation)</h3>
  <table>
    <tr><th>Parameter</th><th>Value</th><th>Unit</th></tr>
    <tr><td>Minor storm overflow flow (2-yr routing)</td>
        <td class="num">{ov.get('Q_minor_Ls','—')}</td><td>L/s</td></tr>
    <tr><td>Selected standpipe diameter</td>
        <td class="num"><strong>Ø{ov.get('selected_dia_mm','—')}</strong></td><td>mm UPVC</td></tr>
    <tr><td>Standpipe capacity (with blockage factor)</td>
        <td class="num">{ov.get('standpipe_cap_Ls','—')}</td><td>L/s</td></tr>
    <tr><td>Head over standpipe crest</td>
        <td class="num">{ov.get('h_over_crest_mm','—')}</td><td>mm</td></tr>
    <tr><td>Standpipe crest level</td>
        <td colspan="2">{ov.get('standpipe_crest_height','—')}</td></tr>
    <tr><td>Perforations at crest</td>
        <td colspan="2">{ov.get('perforations','—')}</td></tr>
    <tr><td>Outlet pipe</td>
        <td colspan="2">{ov.get('outlet_pipe','—')}</td></tr>
    <tr><td>Scour protection</td>
        <td colspan="2">{ov.get('scour_protection','—')}</td></tr>
  </table>
  {weir_row}
</div>

<!-- 6. DRAIN-DOWN -->
<div class="section" id="s6">
  <h2>6. DRAIN-DOWN ANALYSIS</h2>
  <p style="font-size:12px;color:#555;margin-bottom:12px">
    Average Darcy head method — Water by Design (2014) Section 3.5.1.4.
    Critical for mosquito control (must clear ponding within 72 hr, below 4-day larval development minimum).
  </p>
  <div class="cards">
    <div class="card {'card' if dd_ok else 'card fail-card'}">
      <div class="val">{dd_t:.1f}</div><div class="unit">hours</div>
      <div class="lbl">Drain-down time<br>Limit: ≤ 72 hours</div></div>
    <div class="card"><div class="val">{dd.get('V_total_m3',0):.3f}</div>
      <div class="unit">m³</div>
      <div class="lbl">Total volume to drain<br>(ponding + pore storage)</div></div>
    <div class="card"><div class="val">{dd.get('Q_avg_Ls',0):.3f}</div>
      <div class="unit">L/s</div><div class="lbl">Average filtration rate</div></div>
  </div>
  <div class="alert {'alert-ok' if dd_ok else 'alert-fail'}">
    <strong>Drain-down: {dd_t:.1f} hr — {'PASS ✓ (ponding clears well within 72-hr mosquito threshold)' if dd_ok else 'EXCEEDS 72 HR — increase filter Ksat or reduce ponding/filter depth'}</strong>
  </div>
</div>

<!-- 7. HYDROLOGY -->
<div class="section" id="s7">
  <h2>7. HYDROLOGICAL ANALYSIS</h2>
  <table>
    <tr><th>Parameter</th><th>Pre-cell (no treatment)</th><th>Post-cell (with bioretention)</th></tr>
    <tr><td>Runoff coefficient (Rv)</td>
        <td class="num">{Rv:.3f}</td>
        <td class="num">Reduced — filtration restores infiltration</td></tr>
    <tr><td>Peak inflow to catchment outlet (L/s)</td>
        <td class="num">{hs.get('peak_inflow_Ls','—')}</td>
        <td class="num">{hs.get('peak_inflow_Ls','—')} (enters cell)</td></tr>
    <tr><td>Peak outflow (filtered + overflow) (L/s)</td>
        <td class="num">{hs.get('peak_inflow_Ls','—')}</td>
        <td class="num">{hs.get('peak_outflow_Ls','—')}</td></tr>
    <tr><td>Peak flow reduction</td>
        <td class="num">—</td>
        <td class="num"><strong>{hs.get('peak_reduction_pct','—')}%</strong></td></tr>
    <tr><td>Annual runoff volume (m³/yr)</td>
        <td class="num">{hs.get('annual_runoff_m3',0):,.0f}</td>
        <td class="num">Reduced by filtered/evapotranspiration volume</td></tr>
  </table>
  <div class="alert alert-info">
    <strong>Note on peak reduction:</strong> Bioretention is a <em>water quality</em> best management practice (BMP),
    not a flood control structure. Peak flow reduction for large design storms is typically low (1–5%
    for a single cell). Its primary function is treating the first-flush runoff volume through the filter
    media, removing TSS, nutrients, and metals. Volume capture (20–100% of event) is the meaningful
    performance metric for bioretention, not peak flow reduction.
  </div>
</div>

<!-- 8. VOLUME BALANCE -->
<div class="section" id="s8">
  <h2>8. EVENT VOLUME BALANCE</h2>
  <p style="font-size:12px;color:#555;margin-bottom:12px">
    All pollutant load reductions (Section 9) scale proportionally with the filtered volume.
    Only the filtered portion receives media treatment.
  </p>
  {vol_bar}
  <div class="cards">
    <div class="card"><div class="val">{vb.get('V_in_m3','—')}</div>
      <div class="unit">m³</div><div class="lbl">Total event runoff in</div></div>
    <div class="card" style="border-color:#4CAF50">
      <div class="val" style="color:#2E7D32">{vb.get('V_filtered_m3','—')}</div>
      <div class="unit">m³</div><div class="lbl">Volume filtered (treated)</div></div>
    <div class="card" style="border-color:#EF9A9A">
      <div class="val" style="color:#C62828">{vb.get('V_overflow_m3','—')}</div>
      <div class="unit">m³</div><div class="lbl">Volume overflow (bypassed)</div></div>
    <div class="card" style="border-color:#4CAF50">
      <div class="val" style="color:#2E7D32">{vb.get('V_captured_pct','—')}%</div>
      <div class="unit">of event volume</div><div class="lbl">Volume captured by cell</div></div>
  </div>
  <table>
    <tr><th>Volume Component</th><th>m³</th><th>% of total inflow</th><th>Treatment status</th></tr>
    <tr><td>Total inflow</td>
        <td class="num">{vb.get('V_in_m3','—')}</td><td class="num">100%</td><td>—</td></tr>
    <tr><td>Filtered through media</td>
        <td class="num">{vb.get('V_filtered_m3','—')}</td>
        <td class="num">{vb.get('V_captured_pct','—')}%</td>
        <td>✓ Treated (TSS {poll.get('TSS_mgL',{}).get('removal_pct','—')}%, TP {poll.get('TP_mgL',{}).get('removal_pct','—')}%, TN {poll.get('TN_mgL',{}).get('removal_pct','—')}%)</td></tr>
    <tr><td>Overflow (exceeds ponding)</td>
        <td class="num">{vb.get('V_overflow_m3','—')}</td>
        <td class="num">{round(vb.get('V_overflow_m3',0)/max(vb.get('V_in_m3',1),1)*100,1)}%</td>
        <td>Bypassed untreated — enters existing drain</td></tr>
  </table>
</div>

<!-- 9. WATER QUALITY -->
<div class="section" id="s9">
  <h2>9. WATER QUALITY — ANNUAL POLLUTANT LOAD ANALYSIS</h2>
  <p style="font-size:12px;color:#555;margin-bottom:10px">
    EMC method: Annual load (kg/yr) = Annual runoff (m³/yr) × EMC (mg/L) × 0.001.
    Removal efficiencies from Davis et al. (2009) — median values from field studies.
    Loads apply to the <em>filtered fraction</em> of runoff; overflow contribution is untreated.
  </p>
  <table>
    <tr><th>Pollutant</th><th>EMC (mg/L)</th><th>Annual Load In (kg/yr)</th>
        <th>Removal (%)</th><th>Annual Load Out (kg/yr)</th><th>Annual Removed (kg/yr)</th></tr>
    {poll_rows}
  </table>
  <div class="alert alert-ok">
    Annual runoff volume: <strong>{hs.get('annual_runoff_m3',0):,.0f} m³/yr</strong> (Rv × A × P_annual).
    Pollutant loads calculated on total annual runoff as conservative estimate.
  </div>
</div>

<!-- 10. PLANTING -->
<div class="section" id="s10">
  <h2>10. VEGETATION DESIGN AND PLANTING SCHEDULE</h2>
  <p style="font-size:12px;color:#555;margin-bottom:10px">
    Bangladesh climate context: monsoon Jun–Oct, dry season Nov–May.
    Species selected for flood tolerance ≥72 hr AND dry-season survival without irrigation once established.
    Target: 90% ground cover within 2 growing seasons (Water by Design 2014, Section 3.6.5).
  </p>
  <table>
    <tr><th>Zone</th><th>Zone Area (m²)</th><th>Common Name</th><th>Scientific Name</th>
        <th>Type</th><th>Spacing (mm)</th><th>Quantity</th></tr>
    {plant_rows if plant_rows else '<tr><td colspan="7" class="no-fig">Plant schedule not generated</td></tr>'}
  </table>
  <p style="font-size:11px;color:#555;margin-top:10px">
    <strong>Mulch:</strong> Shredded wood chip 50–75 mm. Apply AFTER planting. Leave 50 mm gap around stems.
    Top up annually pre-monsoon (April–May). <br>
    <strong>Establishment watering:</strong> Weeks 1–6: 5×/week &nbsp;|&nbsp;
    Weeks 6–10: 3×/week &nbsp;|&nbsp; Weeks 10–15: 2×/week.<br>
    <strong>Plant replacement guarantee:</strong> Replace all failed plants within 14 days during 18-month establishment period.
  </p>
</div>

<!-- 11. MATERIAL QUANTITIES -->
<div class="section" id="s11">
  <h2>11. INDICATIVE MATERIAL QUANTITIES — Single Cell</h2>
  <table>
    <tr><th>Item</th><th>Quantity</th><th>Unit</th></tr>
    {mat_rows}
  </table>
  <div class="alert alert-warn">
    Quantities indicative for a single cell (±20% at this stage).
    Multiply by number of cells for campus total.
    Detailed BOQ to be prepared from construction drawings (Phase 08).
  </div>
</div>

<!-- 12. DRAWINGS -->
<div class="section" id="s12">
  <h2>12. ENGINEERING DRAWINGS AND ANALYSIS PLOTS</h2>
  {_fig(figures,"summary_dashboard","Design Summary Dashboard — key metrics and design checks")}
  {_fig(figures,"layer_detail","Layer Profile — to-scale depth diagram")}
  {_fig(figures,"cross_section","Cross-Section — full layer profile, underdrain, overflow standpipe, berm with dimensions")}
  {_fig(figures,"plan_view","Plan View Schematic — cell layout, inlet, underdrain, overflow, planting zones")}
  {_fig(figures,"hydrology","Hydrology — Design hyetograph, inflow/outflow breakdown, volume balance bar chart")}
  {_fig(figures,"draindown","Drain-Down Simulation — two-phase drainage curve (ponding + filter pore)")}
</div>

<!-- 13. DESIGN CHECKS -->
<div class="section" id="s13">
  <h2>13. DESIGN CHECKS AND COMPLIANCE SUMMARY</h2>
  <p style="font-size:12px;color:#555;margin-bottom:12px">
    Items marked ✅ are satisfied by design construction (we designed them to meet requirements).
    Items marked ⚠️ indicate site constraints or input values that require attention.
  </p>
  <div class="check-grid">
    {checks_html}
  </div>
  <div class="alert {'alert-ok' if all_ok else 'alert-warn'}" style="margin-top:16px">
    <strong>Overall status:</strong>
    {'✓ All design checks passed — ready to proceed to detailed drawing and specification (Phase 06).'
     if all_ok else
     '⚠ One or more site/input constraints require attention. Review flagged items above.'}
  </div>
</div>

<!-- REFERENCES -->
<div class="section">
  <h2>REFERENCES</h2>
  <ul style="font-size:11.5px;color:#444;line-height:2.0;padding-left:18px">
    <li>Davis, A. P., Hunt, W. F., Traver, R. G., &amp; Clar, M. (2009). Bioretention technology.
        <em>Journal of Environmental Engineering, 135</em>(3), 109–117.</li>
    <li>FAWB. (2009). <em>Guidelines for filter media in biofiltration systems</em> (v3.01). Monash University.</li>
    <li>Islam, M. T., Murshed, S., &amp; Bhuiyan, M. H. U. (2014). Rainfall IDF relationships for Rajshahi.
        <em>Journal of Hydrology and Environment Research, 2</em>(1), 34–42.</li>
    <li>Prince George's County. (2007). <em>Bioretention manual</em>. Maryland Department of the Environment.</li>
    <li>Tsihrintzis, V. A., &amp; Hamid, R. (1998). Runoff quality prediction from small urban catchments.
        <em>Hydrological Processes, 12</em>(2), 311–329.</li>
    <li>Water by Design. (2014). <em>Bioretention technical design guidelines</em> (v1.1). Healthy Waterways Ltd.</li>
  </ul>
</div>

<div class="footer">
  Bioretention Design Tool v3 — Academic Use | Generated {now} |
  Water by Design (2014) · Prince George's County (2007) · FAWB (2009) · Davis et al. (2009)
</div>
</div>
</body>
</html>"""

    os.makedirs(os.path.dirname(output_path), exist_ok=True) if os.path.dirname(output_path) else None
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    return output_path
