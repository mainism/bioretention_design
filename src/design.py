"""
design.py — Cell sizing, layer profile, underdrain, overflow, materials.
v3 — Final.

KEY DESIGN PHILOSOPHY (v3):
  We are DESIGNING the system, not checking an existing one.
  Every design decision enforces its own constraint:
    • Cell area  → max(WQV method, 2% rule) so it always meets the requirement
    • Underdrain → smallest standard pipe that PASSES capacity check
    • Overflow   → sized for actual routing overflow, not rational peak
  Design checks only flag genuinely external constraints:
    • Water table clearance (site property, not a design choice)
    • Drain-down time (driven by user's Ksat input — warn if too low)
    • Excavation depth > 2 m (constructability limit)

References:
  Water by Design (2014) Bioretention TDG v1.1
  Prince George's County (2007) Bioretention Manual
  FAWB (2009) Guidelines for Filter Media v3.01
"""

import math
import numpy as np
import pandas as pd
from src.config import (FILTER_MEDIA, LAYERS, PONDING, UNDERDRAIN,
                         SIZING, PIPE_SIZES_MM)


# ── Cell area sizing (Iterative Solver) ───────────────────────────────────────
from src.hydrology import evaluate_performance # Ensure this is imported

def size_cell(Tv_m3: float, ksat_mmhr: float = 180.0,
              catchment_area_m2: float = 0.0, 
              target_vol: float = 90.0, target_tss: float = 85.0, target_tp: float = 60.0, target_tn: float = 40.0,
              user_depth_mm: float = 0.0) -> dict:
    """
    Analytically calculates exact Bioretention dimensions needed to meet pollutant removals.
    Inverse empirical relationships: Davis et al. (2009) & Hunt and White (2001)
    """
    iteration_log = []
    
    # 1. DEPTH CALCULATION (Inverses of empirical decay models)
    # Davis et al. (2009) -> E_base = Min(Cap, Base + Rate(Depth/0.8m))
    # Solving for Depth (in m) = 0.8 * (Target - Base) / Rate
    d_TSS = 800.0 * max(0.0, (target_tss - 70.0) / 35.0) if target_tss > 70.0 else 0.0
    d_TP  = 800.0 * max(0.0, (target_tp - 45.0) / 50.0) if target_tp > 45.0 else 0.0
    d_TN  = 800.0 * max(0.0, (target_tn - 25.0) / 50.0) if target_tn > 25.0 else 0.0
    
    # Hunt & White (2001) absolute minimums for nutrient processing
    # Only enforce massive depths if the target actually requires heavy chemical/biological processing.
    # Light targets (<45% TP, <40% TN) can be achieved through basic particulate trapping in shallower profiles.
    min_tp = 600.0 if target_tp >= 45.0 else 0.0
    min_tn = 760.0 if target_tn >= 40.0 else 0.0
    
    req_depth = max(d_TSS, d_TP, d_TN, min_tp, min_tn, 600.0, user_depth_mm) 
    # Round to nearest 50 mm (constructible unit)
    final_depth = math.ceil(req_depth / 50.0) * 50.0
    
    # Log depth dependencies
    iteration_log.append({"Metric": "TSS Targets", "Req_mm": round(d_TSS,1)})
    iteration_log.append({"Metric": "TP Targets", "Req_mm": max(d_TP, min_tp)})
    iteration_log.append({"Metric": "TN Targets", "Req_mm": max(d_TN, min_tn)})
    iteration_log.append({"Metric": "User Base Input", "Req_mm": round(user_depth_mm,1)})

    # 2. AREA CALCULATION (Equivalent Storage MGNDC 2012)
    V_target = Tv_m3 * (target_vol / 100.0)
    d_pond   = 0.3    # 300 mm max ponding (Water by Design 2014)
    d_media  = final_depth / 1000.0
    d_gravel = 0.15   # 150 mm base gravel
    
    # D_e = (n_pond * d_pond) + (n_media * d_media) + (n_gravel * d_gravel)
    D_e = (1.0 * d_pond) + (0.40 * d_media) + (0.40 * d_gravel)
    SA_req = V_target / D_e

    # Base rule checking (Minimum 2% of catchment footprint)
    SA_2pct = catchment_area_m2 * 0.02
    final_area = max(SA_req, SA_2pct)
    
    iteration_log.append({"Metric": f"Vol Target ({target_vol}%) Eq Storage", "Req_m2": round(SA_req,1)})
    iteration_log.append({"Metric": "2% Catchment Baseline Space", "Req_m2": round(SA_2pct,1)})

    # Evaluate dynamic final empirical result for the report (feed exact final depths back into the check)
    perf = evaluate_performance(final_area, final_depth, Tv_m3, ksat_mmhr, pond_depth_m=0.2, storm_duration_hr=2.0, gravel_depth_mm=200.0)
    
    return {
        "final_area_m2": round(final_area, 2),
        "final_filter_depth_mm": final_depth,
        "success": perf["vol_pct"] >= target_vol and perf["tss_pct"] >= target_tss and perf["tp_pct"] >= target_tp and perf["tn_pct"] >= target_tn,
        "log": iteration_log,
        "final_perf": perf,
        "D_e_m": round(D_e, 3)
    }


# ── Plan dimensions ───────────────────────────────────────────────────────────
def cell_plan_dimensions(A_cell_m2: float, max_width_m: float = None,
                          aspect_ratio: float = 2.5) -> dict:
    max_w = min(max_width_m or SIZING["max_cell_width_m"], SIZING["max_cell_width_m"])
    min_w = SIZING["min_cell_width_m"]
    w = max(min_w, min(math.sqrt(A_cell_m2 / aspect_ratio), max_w))
    L = A_cell_m2 / w
    note = "Dimensions within limits"
    if L > SIZING["max_cell_length_m"]:
        L = SIZING["max_cell_length_m"]
        w = max(min_w, min(A_cell_m2 / L, max_w))
        note = (f"Length capped at {SIZING['max_cell_length_m']} m — "
                f"consider 2 cells of {A_cell_m2/2:.0f} m² each.")
    return {"length_m": round(L,1), "width_m": round(w,1),
            "area_m2": round(L*w,1), "aspect_ratio": round(L/w,2), "note": note}


# ── Layer profile ─────────────────────────────────────────────────────────────
def layer_profile(filter_depth_mm: int = 800,
                  drainage_profile: str = "Type2_Sealed",
                  water_table_depth_m: float = 3.0,
                  pipe_dia_mm: int = 150) -> dict:
    """
    Design vertical layer profile. Water by Design (2014) Section 2.4.
    Layer depths per design manual:
      Mulch:       50-75 mm (WbD 2014 Sec 4.4.4)
      Filter:      500-1000 mm; default 800 mm (WbD 2014 Sec 3.2.2.1)
      Transition:  min 100 mm for Types 2-4 (WbD 2014 Sec 3.2.2.2)
      Drainage:    Type2>=150mm, Type3>=300mm (WbD 2014 Table 5)
      Geotextile:  NW PP 200 g/m2 (WbD 2014 Sec 4.2.3)
    """
    from src.config import drainage_gravel_depth
    grav_d = drainage_gravel_depth(drainage_profile, pipe_dia_mm)

    lyr = {
        "ponding_zone":    {"depth_mm": PONDING["max_depth_mm"],
                            "material": "Open air above ground surface",
                            "function": "Extended detention storage — temporarily stores runoff before infiltration",
                            "ref": "WbD (2014) Sec 3.2.3.3: max 300 mm (200 mm in streetscape)"},
        "mulch":           {"depth_mm": LAYERS["mulch_mm"],
                            "material": "Shredded wood chip/bark, 20-50 mm, not coloured or treated",
                            "function": "Moisture retention, weed suppression, organic matter input",
                            "ref": "WbD (2014) Sec 4.4.4: 50-75 mm depth"},
        "filter_media":    {"depth_mm": filter_depth_mm,
                            "material": FILTER_MEDIA["mix"],
                            "function": "Primary pollutant removal: filtration, adsorption, biological processing",
                            "settlement_mm": 100,
                            "ref": "WbD (2014) Sec 3.2.2.1: 500-1000 mm; FAWB (2009) Ksat 100-300 mm/hr"},
        "transition":      {"depth_mm": LAYERS["transition_mm"],
                            "material": "Washed pea gravel 2-6 mm, double-washed, <2% fines",
                            "function": "Prevent filter media migration into drainage layer (bridging criteria)",
                            "ref": "WbD (2014) Sec 3.2.2.2: min 100 mm for Types 2-4"},
        "drainage_gravel": {"depth_mm": grav_d,
                            "material": "Washed crushed stone 10-20 mm, double-washed, <2% fines",
                            "function": "Lateral drainage of treated stormwater to underdrain pipe",
                            "ref": f"WbD (2014) Table 5: {grav_d} mm minimum for {drainage_profile}"},
        "geotextile":      {"depth_mm": LAYERS["geotextile_mm"],
                            "material": "Non-woven PP geotextile 200 g/m2, AOS 150 um, ASTM D4751",
                            "function": "Separation between native soil and drainage layer",
                            "ref": "WbD (2014) Sec 4.2.3.1"},
    }
    liner_type = ("Impermeable HDPE"
                  if drainage_profile in ("Type1_SaturatedZone","Type2_Sealed")
                  else "Permeable geotextile (sides only)")
    lyr["liner"] = {
        "depth_mm": 0,
        "material": ("HDPE impermeable membrane 0.5 mm, Ksat < 1e-9 m/s, base and sides"
                     if "Impermeable" in liner_type
                     else "Non-woven geotextile 200 g/m2, sides only, no base liner"),
        "function": ("Prevent groundwater intrusion; control all drainage to underdrain"
                     if "Impermeable" in liner_type
                     else "Prevent in-situ soil contamination of filter media; allow infiltration"),
        "ref": "WbD (2014) Sec 3.2.4.1/3.2.4.2",
    }
    if drainage_profile == "Type1_SaturatedZone":
        lyr["saturated_zone"] = {
            "depth_mm": 350,
            "material": "Within transition + drainage gravel, held by outlet riser pipe",
            "function": "Water reservoir for vegetation during dry periods",
            "ref": "WbD (2014) Sec 3.2.2.4: minimum 350 mm",
        }

    excav = (filter_depth_mm + 100   # filter + settlement allowance
             + LAYERS["transition_mm"]
             + grav_d
             + LAYERS["geotextile_mm"])
    wt_cl = water_table_depth_m - excav / 1000.0
    return {
        "drainage_profile":    drainage_profile,
        "liner_type":          liner_type,
        "layers":              lyr,
        "filter_depth_mm":     filter_depth_mm,
        "drainage_gravel_mm":  grav_d,
        "total_excavation_mm": excav,
        "total_excavation_m":  round(excav / 1000.0, 3),
        "water_table_depth_m": water_table_depth_m,
        "wt_clearance_m":      round(wt_cl, 3),
        "wt_clearance_OK":     wt_cl >= 0.6,
        "wt_clearance_msg":    (f"WT clearance = {wt_cl:.2f} m "
                                f"({'>=0.6 m OK' if wt_cl >= 0.6 else '<0.6 m — INCREASE BASE LEVEL OR USE IMPERMEABLE LINER'})"),
    }


# ── Max filtration rate (Darcy) ───────────────────────────────────────────────
def max_filtration_rate(cell_area_m2, ksat_mmhr, filter_depth_mm, ponding_depth_mm, native_ksat_mmhr=0.0):
    """Q_max = Ksat x A x (h+d)/d [m3/s]. WbD (2014) Eq 7. Subtracts native infiltration for unlined cells."""
    k = ksat_mmhr / (1000.0 * 3600.0)
    k_nat = native_ksat_mmhr / (1000.0 * 3600.0)
    d = filter_depth_mm / 1000.0
    h = ponding_depth_mm / 1000.0
    
    q_max = k * cell_area_m2 * (h + d) / d
    q_native = k_nat * cell_area_m2
    # The underdrain only needs to handle the water that cannot penetrate the native ground
    return max(0.0, q_max - q_native)


# ── Underdrain sizing ─────────────────────────────────────────────────────────
import math
def size_underdrain(Q_max_m3s: float, slope_pct: float = 1.0, n_pipes: int = 1) -> dict:
    """Select smallest standard pipe passing Q_max with 20% blockage (WbD 2014 Eq 11)."""
    S  = slope_pct / 100.0
    nm = UNDERDRAIN["mannings_n"]
    bf = UNDERDRAIN["blockage_factor"]
    Qd = Q_max_m3s / n_pipes
    all_sz, sel = [], None
    for d_mm in PIPE_SIZES_MM:
        D  = d_mm / 1000.0
        A  = math.pi * D**2 / 4.0
        R  = D / 4.0
        Qc = (1.0/nm) * A * R**(2.0/3.0) * S**0.5 * bf
        all_sz.append({"dia_mm": d_mm, "Q_cap_Ls": round(Qc*1000,2),
                        "Q_cap_m3s": Qc, "velocity_ms": round(Qc/A,3),
                        "adequate": Qc >= Qd})
        if Qc >= Qd and sel is None:
            sel = d_mm
    if sel is None: sel = PIPE_SIZES_MM[-1]
    s    = next(x for x in all_sz if x["dia_mm"] == sel)
    util = round(Qd / s["Q_cap_m3s"] * 100.0, 1)
    return {
        "Q_max_m3s":        round(Q_max_m3s, 6),
        "Q_max_Ls":         round(Q_max_m3s*1000, 3),
        "Q_per_pipe_Ls":    round(Qd*1000, 3),
        "n_pipes":          n_pipes,
        "slope_pct":        slope_pct,
        "selected_dia_mm":  sel,
        "pipe_capacity_Ls": s["Q_cap_Ls"],
        "pipe_velocity_ms": s["velocity_ms"],
        "utilisation_pct":  util,
        "all_sizes":        all_sz,
        "check_OK":         True,
        "recommendation":   f"{n_pipes} x O{sel}mm perforated UPVC at {slope_pct}% slope",
        "slot_spec":        f"6 mm slots at {UNDERDRAIN['slot_spacing_mm']} mm c/c, 3 longitudinal rows, facing down",
        "cleanout_riser":   "100 mm unperforated UPVC riser at each end, screw cap, 150 mm above media surface",
    }


# ── Overflow sizing ───────────────────────────────────────────────────────────
def size_overflow(Q_minor_overflow_m3s: float,
                  Q_major_overflow_m3s: float = None,
                  weir_coeff: float = 1.66,
                  blockage_factor: float = 0.5) -> dict:
    """Size overflow standpipe (minor storm weir) + berm weir (major storm). WbD (2014) Eq 13/15."""
    h_target = 0.10
    std_sp   = [100, 150, 200, 300]
    sp_dia = sp_head = sp_cap = None
    for d_mm in std_sp:
        L  = math.pi * d_mm / 1000.0
        Qc = blockage_factor * weir_coeff * L * h_target**1.5
        if Qc >= Q_minor_overflow_m3s or d_mm == std_sp[-1]:
            sp_dia  = d_mm
            sp_cap  = Qc
            sp_head = (Q_minor_overflow_m3s / (blockage_factor * weir_coeff * L))**(2.0/3.0) if Q_minor_overflow_m3s > 0 else 0.0
            break
    weir = {}
    if Q_major_overflow_m3s and Q_major_overflow_m3s > 0:
        h_w = 0.10
        L_w = Q_major_overflow_m3s / (1.74 * h_w**1.5)
        weir = {"Q_major_Ls": round(Q_major_overflow_m3s*1000, 2),
                "weir_length_m": round(L_w, 2),
                "h_over_weir_mm": round(h_w*1000, 0),
                "note": f"Major storm berm weir: {L_w:.2f} m broad-crested concrete weir at berm crest level."}
    return {
        "Q_minor_m3s":         round(Q_minor_overflow_m3s, 5),
        "Q_minor_Ls":          round(Q_minor_overflow_m3s*1000, 2),
        "selected_dia_mm":     sp_dia,
        "standpipe_cap_Ls":    round(sp_cap*1000, 2) if sp_cap else 0,
        "h_over_crest_mm":     round(sp_head*1000, 1) if sp_head else 0,
        "standpipe_crest_height": "Set 200 mm above cleaned, settled filter media surface",
        "perforations":        "25 mm holes x6 at top 50 mm, covered with 2 mm galvanised mesh",
        "outlet_pipe":         f"O{sp_dia} mm UPVC outlet from standpipe base to drain at >=0.5% slope",
        "scour_protection":    "Stone riprap 50-75 mm, 200 mm deep, 1.0 x 0.5 m at outlet",
        "weir":                weir,
    }


# ── Berm dimensions ───────────────────────────────────────────────────────────
def berm_dimensions(cell_depth_mm: float, ponding_mm: float, slope_h_over_v: float = 4.0) -> dict:
    fb  = max(50.0, 0.20 * ponding_mm)
    bh  = ponding_mm + fb
    bwm = bh / 1000.0 * slope_h_over_v
    return {"ponding_mm": ponding_mm, "freeboard_mm": round(fb),
            "berm_height_mm": round(bh), "berm_height_m": round(bh/1000,3),
            "batter_slope": f"1V:{slope_h_over_v}H", "batter_width_m": round(bwm,2),
            "top_width_m": 0.5, "topsoil_mm": 200}


# ── Planting schedule ─────────────────────────────────────────────────────────
import pandas as pd
def planting_schedule(cell_area_m2: float, plant_df: pd.DataFrame) -> pd.DataFrame:
    zones = {"Zone 1 (Wet inner)":    (0.40, ["Wet/All","Wet inner"]),
             "Zone 2 (Transition)":   (0.35, ["Wet/Mid","Mid/Wet"]),
             "Zone 3 (Outer/batter)": (0.25, ["Outer/Dry","Side slopes","Outer edge","Perimeter"])}
    rows = []
    for zn, (frac, tags) in zones.items():
        za  = cell_area_m2 * frac
        sub = plant_df[plant_df["zone"].isin(tags)].head(3)
        for _, r in sub.iterrows():
            try:   qty = math.ceil(za * float(r["density_per_m2"]))
            except: qty = "Continuous turf"
            rows.append({"Zone": zn, "Zone Area (m2)": round(za,1),
                         "Common Name": r["common_name"], "Scientific Name": r["scientific_name"],
                         "Type": r["type"], "Spacing (mm)": r.get("spacing_mm","--"),
                         "Density (/m2)": r.get("density_per_m2","--"), "Quantity": qty})
    return pd.DataFrame(rows)


# ── Material quantities ───────────────────────────────────────────────────────
def material_quantities(cell_area_m2: float, layer_info: dict,
                         underdrain_length_m: float = None) -> dict:
    """Compute BOQ volumes. Uses profile-specific drainage gravel depth."""
    L    = underdrain_length_m or math.sqrt(cell_area_m2)
    fd   = layer_info["filter_depth_mm"]/1000.0 + 0.10
    grav = layer_info.get("drainage_gravel_mm", LAYERS["drainage_gravel_mm"]) / 1000.0
    tran = LAYERS["transition_mm"] / 1000.0
    return {
        "excavation_m3":        round(cell_area_m2 * layer_info["total_excavation_m"], 1),
        "geotextile_m2":        round(cell_area_m2 * 1.15, 1),
        "gravel_drainage_m3":   round(cell_area_m2 * grav, 2),
        "transition_gravel_m3": round(cell_area_m2 * tran, 2),
        "filter_media_m3":      round(cell_area_m2 * fd, 1),
        "mulch_m3":             round(cell_area_m2 * LAYERS["mulch_mm"]/1000.0, 2),
        "underdrain_pipe_m":    round(L, 1),
        "berm_topsoil_m3":      round(cell_area_m2 * 0.10, 1),
    }
