"""
engine.py — Headless computation engine for the web app.
Extracts all calculation logic from main.py into a single callable
`run_design(params: dict) -> dict` function that returns structured
results + paths to the two generated HTML documents.
"""

import os, sys, math, datetime, tempfile
import pandas as pd

ROOT       = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR   = os.path.join(ROOT, "data")
OUTPUT_DIR = os.path.join(ROOT, "outputs")
PLOTS_DIR  = os.path.join(OUTPUT_DIR, "plots")
os.makedirs(PLOTS_DIR, exist_ok=True)

sys.path.insert(0, ROOT)

from src.config    import FILTER_MEDIA, PONDING, SIZING, PIPE_SIZES_MM
from src.hydrology import (volumetric_runoff_coeff, water_quality_volume,
                            route_hyetograph, route_bioretention,
                            volume_balance, drain_down_time,
                            pollutant_loads, annual_runoff)
from src.design    import (size_cell, cell_plan_dimensions, layer_profile,
                            max_filtration_rate, size_underdrain, size_overflow,
                            berm_dimensions, planting_schedule, material_quantities)
from src.plots     import (draw_cross_section, draw_plan_view, plot_hydrology,
                            plot_draindown, plot_design_summary, plot_layer_detail)
from src.report    import generate_report
from src.calc_basis import generate_calc_basis


DIVS = ["Dhaka","Rajshahi","Khulna","Sylhet","Chattogram","Barishal","Mymensingh","Rangpur"]
RPS  = ["2yr","10yr","25yr"]

PROFILE_MAP = {
    "Type1_SaturatedZone": "Type 1 — Saturated Zone",
    "Type2_Sealed": "Type 2 — Sealed/Lined",
    "Type3_Conventional": "Type 3 — Conventional (Unlined)",
    "Type4_Pipeless": "Type 4 — Pipeless",
}


def load_data():
    h = os.path.join(DATA_DIR, "hyetographs.csv")
    p = os.path.join(DATA_DIR, "plant_palette.csv")
    if not os.path.exists(h):
        raise FileNotFoundError(f"hyetographs.csv not found in {DATA_DIR}")
    return pd.read_csv(h), pd.read_csv(p) if os.path.exists(p) else pd.DataFrame()


def run_design(params: dict) -> dict:
    """
    Run the full bioretention design from a parameter dictionary.

    Required keys
    -------------
    proj_name       : str
    proj_loc        : str
    region          : str  (one of DIVS)
    return_period   : str  ("2yr" / "10yr" / "25yr")
    catchment_area  : float  (m²)
    pct_impervious  : float  (%)
    annual_rainfall : float  (mm/yr)
    avail_space     : float  (m², 0=unconstrained)
    max_width       : float  (m, 0=standard)
    native_ksat     : float  (mm/hr)
    wt_depth        : float  (m BGL)
    profile         : str   (Type2_Sealed etc)
    filter_ksat     : float  (mm/hr)
    filter_depth    : int   (mm)
    target_vol      : float  (%)
    target_tss      : float  (%)
    target_tp       : float  (%)
    target_tn       : float  (%)
    ud_slope        : float  (%)
    n_pipes         : int   (1 or 2)

    Returns a dict with keys:
        summary   : flat dict of key KPIs for on-screen display
        results   : full results dict (for report generators)
        WQV       : float
        report_path      : str (path to HTML design report)
        calc_basis_path  : str (path to HTML calc basis doc)
        figures   : dict of figure paths
        warnings  : list[str]
    """
    hyeto_df, plant_df = load_data()
    warnings = []

    # ── unpack params ─────────────────────────────────────────────────────────
    proj_name   = params.get("proj_name", "Bioretention Design")
    proj_loc    = params.get("proj_loc",  "SC-01")
    region      = params.get("region",    "Rajshahi")
    rp          = params.get("return_period", "2yr")
    A_catch     = float(params.get("catchment_area", 44700))
    pct_imp     = float(params.get("pct_impervious", 38))
    ann_rf      = float(params.get("annual_rainfall", 1431))
    avail_space = float(params.get("avail_space", 0))
    max_width   = float(params.get("max_width", 0)) or SIZING["max_cell_width_m"]
    native_ksat = float(params.get("native_ksat", 10))
    wt_depth    = float(params.get("wt_depth", 2.5))
    profile     = params.get("profile", "Type2_Sealed")
    f_ksat      = float(params.get("filter_ksat", 180))
    f_depth     = int(params.get("filter_depth", 800))
    target_vol  = float(params.get("target_vol", 90))
    target_tss  = float(params.get("target_tss", 85))
    target_tp   = float(params.get("target_tp",  60))
    target_tn   = float(params.get("target_tn",  40))
    ud_slope    = float(params.get("ud_slope", 1.0))
    n_pipes     = int(params.get("n_pipes", 1))

    # ── hyetograph ────────────────────────────────────────────────────────────
    prec_df = hyeto_df[hyeto_df["division"] == region].copy()
    if prec_df.empty:
        raise ValueError(f"No rainfall data for region: {region}")

    # ── core calculations ─────────────────────────────────────────────────────
    Rv    = volumetric_runoff_coeff(pct_imp)
    WQV   = water_quality_volume(A_catch, pct_imp)
    ann_r = annual_runoff(A_catch, pct_imp, ann_rf)

    cell = size_cell(WQV, f_ksat, A_catch, target_vol, target_tss, target_tp, target_tn, f_depth)
    A_cell  = cell["final_area_m2"]
    f_depth = cell["final_filter_depth_mm"]

    cell["A_cell_m2"]       = A_cell
    cell["A_WQV_m2"]        = A_cell
    cell["A_2pct_m2"]       = A_catch * 0.02
    cell["governing"]       = "Analytical Requirement Calculation"
    cell["pct_of_catchment"] = (A_cell / A_catch) * 100
    cell["area_OK"]         = True
    cell["area_ok"]         = True

    if avail_space > 0 and A_cell > avail_space:
        warnings.append(f"Required area ({A_cell:.1f} m²) exceeds available space ({avail_space:.1f} m²). "
                        f"Cell constrained — 2% rule may not be met.")
        A_cell = avail_space
        cell["A_cell_m2"]        = A_cell
        cell["pct_of_catchment"] = round(A_cell / A_catch * 100, 2)

    nat_ksat_val = native_ksat if profile in ["Type3_Conventional", "Type4_Pipeless"] else 0.0
    Q_max = max_filtration_rate(A_cell, f_ksat, f_depth, PONDING["max_depth_mm"], nat_ksat_val)
    ud    = size_underdrain(Q_max, ud_slope, n_pipes)

    dims  = cell_plan_dimensions(A_cell, max_width)
    lyr   = layer_profile(f_depth, profile, wt_depth, ud["selected_dia_mm"])

    routed = route_hyetograph(prec_df, A_catch, Rv, rp)
    rb     = route_bioretention(routed, A_cell, f_ksat, f_depth, PONDING["max_depth_mm"], nat_ksat_val)
    vb     = volume_balance(routed, rb)

    if rp != "2yr":
        prec2yr = route_hyetograph(prec_df, A_catch, Rv, "2yr")
        rb2yr   = route_bioretention(prec2yr, A_cell, f_ksat, f_depth, PONDING["max_depth_mm"], nat_ksat_val)
        Q_minor = rb2yr["q_overflow_Ls"].max() / 1000.0
        Q_major = rb["q_overflow_Ls"].max() / 1000.0
    else:
        Q_minor = rb["q_overflow_Ls"].max() / 1000.0
        Q_major = None

    ov   = size_overflow(Q_minor, Q_major)
    dd   = drain_down_time(A_cell, f_depth, FILTER_MEDIA["porosity"],
                           PONDING["max_depth_mm"], f_ksat, lyr["drainage_gravel_mm"])
    berm = berm_dimensions(lyr["total_excavation_mm"], PONDING["max_depth_mm"])
    poll = pollutant_loads(ann_r)

    poll["TSS_mgL"]["removal_pct"] = cell["final_perf"]["tss_pct"]
    poll["TP_mgL"]["removal_pct"]  = cell["final_perf"]["tp_pct"]
    poll["TN_mgL"]["removal_pct"]  = cell["final_perf"]["tn_pct"]
    for key in poll:
        poll[key]["removed_kgyr"]  = poll[key]["load_in_kgyr"] * (poll[key]["removal_pct"] / 100.0)
        poll[key]["load_out_kgyr"] = poll[key]["load_in_kgyr"] - poll[key]["removed_kgyr"]

    pl  = planting_schedule(A_cell, plant_df) if not plant_df.empty else None
    mat = material_quantities(A_cell, lyr, dims["length_m"] * n_pipes)

    # ksat flag
    if not (100 <= f_ksat <= 300):
        warnings.append(f"Filter Ksat ({f_ksat} mm/hr) is outside the recommended 100–300 mm/hr range (FAWB 2009).")

    # ── results bundle ────────────────────────────────────────────────────────
    results = {
        "project":   {"name": proj_name, "location": proj_loc},
        "inputs":    {"catchment_area_m2": A_catch, "pct_impervious": pct_imp,
                      "Rv": Rv, "filter_ksat_mmhr": f_ksat, "native_ksat_mmhr": native_ksat,
                      "drainage_profile": profile, "water_table_m": wt_depth,
                      "region": region, "return_period": rp, "annual_rainfall_mm": ann_rf},
        "cell_sizing":     cell,
        "cell_dimensions": dims,
        "layer_profile":   lyr,
        "underdrain":      ud,
        "overflow":        ov,
        "drain_down":      dd,
        "berm":            berm,
        "materials":       mat,
        "plants":          pl,
        "pollutants":      poll,
        "volume_balance":  vb,
        "hydrology_summary": {
            "Rv": Rv,
            "peak_inflow_Ls":     vb["Q_in_peak_Ls"],
            "peak_outflow_Ls":    vb["Q_out_peak_Ls"],
            "peak_reduction_pct": vb["peak_red_pct"],
            "annual_runoff_m3":   ann_r,
        },
        "catchment_area_m2": A_catch,
    }

    # ── generate plots + HTML files ───────────────────────────────────────────
    ts   = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    slug = proj_name.replace(" ", "_").replace("/", "-")[:28]

    figs = {}
    plot_funcs = [
        ("summary_dashboard", lambda p: plot_design_summary(results, p)),
        ("layer_detail",      lambda p: plot_layer_detail(lyr, p)),
        ("cross_section",     lambda p: draw_cross_section(lyr, dims, ud, ov, p)),
        ("plan_view",         lambda p: draw_plan_view(dims, ud, ov, p)),
        ("hydrology",         lambda p: plot_hydrology(routed, rb, vb, region, rp, p)),
        ("draindown",         lambda p: plot_draindown(A_cell, f_depth,
                                         FILTER_MEDIA["porosity"], PONDING["max_depth_mm"],
                                         f_ksat, p)),
    ]
    for key, func in plot_funcs:
        path = os.path.join(PLOTS_DIR, f"{slug}_{key}_{ts}.png")
        try:
            figs[key] = func(path)
        except Exception as e:
            warnings.append(f"Plot '{key}' failed: {e}")

    report_path = os.path.join(OUTPUT_DIR, f"{slug}_report_{ts}.html")
    try:
        generate_report(results, figs, report_path)
    except Exception as e:
        warnings.append(f"Design report generation failed: {e}")
        report_path = None

    calc_basis_path = os.path.join(OUTPUT_DIR, f"{slug}_Calculation_Basis_{ts}.html")
    try:
        generate_calc_basis(results, WQV, calc_basis_path)
    except Exception as e:
        warnings.append(f"Calculation basis generation failed: {e}")
        calc_basis_path = None

    # ── flat summary for UI display ───────────────────────────────────────────
    summary = {
        # Catchment
        "catchment_area_m2":   A_catch,
        "pct_impervious":      pct_imp,
        "Rv":                  round(Rv, 4),
        "WQV_m3":              round(WQV, 2),
        "annual_runoff_m3yr":  round(ann_r, 0),
        # Cell
        "cell_area_m2":        round(A_cell, 1),
        "pct_of_catchment":    round(A_cell / A_catch * 100, 2),
        "cell_length_m":       dims["length_m"],
        "cell_width_m":        dims["width_m"],
        # Layers
        "filter_depth_mm":     f_depth,
        "profile":             profile,
        "excavation_mm":       lyr["total_excavation_mm"],
        "wt_clearance_m":      round(lyr["wt_clearance_m"], 3),
        "gravel_depth_mm":     lyr["drainage_gravel_mm"],
        # Underdrain
        "Q_max_Ls":            round(ud["Q_max_Ls"], 3),
        "pipe_dia_mm":         ud["selected_dia_mm"],
        "pipe_util_pct":       ud["utilisation_pct"],
        "pipe_rec":            ud["recommendation"],
        # Overflow
        "overflow_standpipe_mm": ov["selected_dia_mm"],
        "overflow_q_Ls":         round(ov["Q_minor_Ls"], 2),
        # Drain-down
        "drain_time_hr":       dd["drain_time_hr"],
        "drain_ok":            dd["drain_time_OK"],
        # Volume balance
        "V_in_m3":             vb["V_in_m3"],
        "V_filtered_m3":       vb["V_filtered_m3"],
        "V_underdrain_m3":     vb.get("V_underdrain_m3", 0),
        "V_native_m3":         vb.get("V_native_m3", 0),
        "V_overflow_m3":       vb["V_overflow_m3"],
        "V_captured_pct":      vb["V_captured_pct"],
        "peak_inflow_Ls":      vb["Q_in_peak_Ls"],
        "peak_outflow_Ls":     vb["Q_out_peak_Ls"],
        "peak_red_pct":        vb["peak_red_pct"],
        # Pollutants
        "tss_removal_pct":     round(cell["final_perf"]["tss_pct"], 1),
        "tp_removal_pct":      round(cell["final_perf"]["tp_pct"], 1),
        "tn_removal_pct":      round(cell["final_perf"]["tn_pct"], 1),
        "vol_capture_pct":     round(cell["final_perf"]["vol_pct"], 1),
        # Checks
        "ksat_ok":             100 <= f_ksat <= 300,
        "wt_ok":               lyr["wt_clearance_OK"],
        "excav_ok":            lyr["total_excavation_m"] <= 2.0,
    }

    return {
        "summary":          summary,
        "results":          results,
        "WQV":              WQV,
        "report_path":      report_path,
        "calc_basis_path":  calc_basis_path,
        "figures":          figs,
        "warnings":         warnings,
        "slug":             slug,
        "ts":               ts,
    }
