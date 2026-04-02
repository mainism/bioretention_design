"""
hydrology.py — Runoff volume, peak flow, hydrograph routing, volume balance.
v3 — Final. All routing, balance, and drain-down functions correct.

References:
  Prince George's County (2007) — Rv, WQV
  Water by Design (2014) — Darcy routing, level-pool
  Davis et al. (2009) — pollutant removal
"""

import numpy as np
import pandas as pd
from src.config import RUNOFF_COEFFICIENTS, EMC_URBAN, POLLUTANT_REMOVAL


# ── Rv ────────────────────────────────────────────────────────────────────────
def volumetric_runoff_coeff(pct_impervious: float) -> float:
    """Rv = 0.05 + 0.009 × I  (Prince George's County 2007)."""
    return min(max(0.05 + 0.009 * float(pct_impervious), 0.05), 0.95)


# ── WQV ───────────────────────────────────────────────────────────────────────
def water_quality_volume(catchment_area_m2: float, pct_impervious: float,
                          design_depth_mm: float = 25.0) -> float:
    """WQV (m³) = Rv × A × d_wq."""
    return volumetric_runoff_coeff(pct_impervious) * catchment_area_m2 * design_depth_mm / 1000.0


# ── Rational Method peak flow ─────────────────────────────────────────────────
def rational_peak_flow(C: float, i_mmhr: float, A_ha: float) -> float:
    """Q (m³/s) = C × i (mm/hr) × A (ha) / 360."""
    return C * i_mmhr * A_ha / 360.0


# ── Weighted runoff coefficient ───────────────────────────────────────────────
def weighted_runoff_coeff(areas_and_covers: list) -> float:
    total_cA, total_A = 0.0, 0.0
    for area, cover in areas_and_covers:
        C = RUNOFF_COEFFICIENTS.get(cover, 0.5)
        total_cA += C * area; total_A += area
    return total_cA / total_A if total_A > 0 else 0.5


# ── Hyetograph → catchment inflow hydrograph ─────────────────────────────────
def route_hyetograph(hyetograph_df: pd.DataFrame,
                     catchment_area_m2: float, rv: float,
                     return_period: str = "2yr",
                     dt_min: float = 5.0) -> pd.DataFrame:
    """Convert 12-bin design hyetograph to inflow hydrograph (L/s)."""
    df = hyetograph_df.copy().sort_values("time_min").reset_index(drop=True)
    dt_hr = dt_min / 60.0
    col = {"2yr":  "intensity_2yr_mmhr", "10yr": "intensity_10yr_mmhr",
           "25yr": "intensity_25yr_mmhr", "custom": "intensity_2yr_mmhr"
           }.get(return_period, "intensity_2yr_mmhr")

    df["intensity_mmhr"]  = df[col]
    df["runoff_mmhr"]     = df["intensity_mmhr"] * rv
    df["inflow_Ls"]       = df["runoff_mmhr"] * catchment_area_m2 / 3600.0
    df["rainfall_mm"]     = df["intensity_mmhr"] * dt_hr
    df["runoff_mm"]       = df["runoff_mmhr"] * dt_hr
    df["cumul_rain_mm"]   = df["rainfall_mm"].cumsum()
    df["cumul_runoff_mm"] = df["runoff_mm"].cumsum()
    return df[["time_min","intensity_mmhr","runoff_mmhr","inflow_Ls",
               "rainfall_mm","runoff_mm","cumul_rain_mm","cumul_runoff_mm"]]


# ── Level-pool bioretention routing ──────────────────────────────────────────
def route_bioretention(inflow_df: pd.DataFrame,
                       cell_area_m2: float,
                       filter_ksat_mmhr: float,
                       filter_depth_mm: float,
                       ponding_max_mm: float,
                       native_ksat_mmhr: float = 0.0,
                       dt_min: float = 5.0) -> pd.DataFrame:
    """
    Level-pool routing. Darcy: Q_filt = Ksat × A × (h + d) / d.
    Overflow when ponding > max. Mass balance tracked each step.
    """
    dt_s    = dt_min * 60.0
    ksat_ms = filter_ksat_mmhr / (1000.0 * 3600.0)
    d_filt  = filter_depth_mm / 1000.0
    h_max   = ponding_max_mm / 1000.0
    n       = len(inflow_df)

    h_pond = np.zeros(n + 1)
    q_filt = np.zeros(n)
    q_over = np.zeros(n)
    q_nat  = np.zeros(n)
    q_ud   = np.zeros(n)
    q_in   = inflow_df["inflow_Ls"].values / 1000.0  # m³/s
    
    nat_ksat_ms = native_ksat_mmhr / (1000.0 * 3600.0)

    for i in range(n):
        h = h_pond[i]
        Q_f = ksat_ms * (h + d_filt) / d_filt * cell_area_m2  # m³/s Darcy
        net_vol = (q_in[i] - Q_f) * dt_s
        h_new   = h + net_vol / cell_area_m2

        if h_new > h_max:
            q_over[i] = (h_new - h_max) * cell_area_m2 / dt_s * 1000.0
            h_new = h_max
        if h_new < 0.0:
            avail = q_in[i] * dt_s + h * cell_area_m2
            Q_f   = avail / dt_s
            h_new = 0.0

        h_pond[i + 1] = h_new
        q_filt[i]     = Q_f * 1000.0
        
        # Split filter flow: native soil vs underdrain pipe
        max_nat_Q = nat_ksat_ms * cell_area_m2 * 1000.0 # L/s
        q_nat[i] = min(q_filt[i], max_nat_Q)
        q_ud[i] = max(0.0, q_filt[i] - q_nat[i])

    df = inflow_df.copy()
    df["ponding_mm"]     = h_pond[:-1] * 1000.0
    df["q_filt_Ls"]      = q_filt
    df["q_native_Ls"]    = q_nat
    df["q_underdrain_Ls"]= q_ud
    df["q_overflow_Ls"]  = np.maximum(q_over, 0.0)
    # Total Outflow (leaving site to storm network) = underdrain + overflow (native infiltration soaked into earth)
    df["q_total_out_Ls"] = df["q_underdrain_Ls"] + df["q_overflow_Ls"]
    return df


# ── Volume balance ─────────────────────────────────────────────────────────────
def volume_balance(inflow_df: pd.DataFrame,
                   routed_bf: pd.DataFrame,
                   dt_min: float = 5.0) -> dict:
    """Event volume balance: V_in → V_filtered + V_overflow."""
    dt_s  = dt_min * 60.0
    V_in  = (inflow_df["inflow_Ls"].values / 1000.0 * dt_s).sum()
    V_ov  = (routed_bf["q_overflow_Ls"].values / 1000.0 * dt_s).sum()
    
    # Extract specific routing volumes
    V_nat = (routed_bf["q_native_Ls"].values / 1000.0 * dt_s).sum()
    V_ud  = (routed_bf["q_underdrain_Ls"].values / 1000.0 * dt_s).sum()
    
    V_f   = max(0.0, V_in - V_ov)  # Total water captured (infiltrated + underdrain + pond/pores)
    pct   = (V_f / V_in * 100.0) if V_in > 0 else 0.0
    Qi    = inflow_df["inflow_Ls"].max()
    Qo    = routed_bf["q_total_out_Ls"].max()
    pk_r  = max(0.0, (1.0 - Qo / Qi) * 100.0) if Qi > 0 else 0.0
    
    return {"V_in_m3": round(V_in,2), "V_filtered_m3": round(V_f,2),
            "V_native_m3": round(V_nat,2), "V_underdrain_m3": round(V_ud,2),
            "V_overflow_m3": round(V_ov,2), "V_captured_pct": round(pct,1),
            "Q_in_peak_Ls": round(Qi,2), "Q_out_peak_Ls": round(Qo,2),
            "peak_red_pct": round(pk_r,1)}


# ── Drain-down time (analytical) ─────────────────────────────────────────────
def drain_down_time(cell_area_m2: float, filter_depth_mm: float,
                    filter_porosity: float, ponding_depth_mm: float,
                    ksat_mmhr: float, gravel_depth_mm: float = 0.0) -> dict:
    """Average Darcy head method. Water by Design (2014) Sec 3.5.1.4."""
    from src.config import DRAINAGE_LAYER
    h  = ponding_depth_mm / 1000.0
    d  = filter_depth_mm / 1000.0
    k  = ksat_mmhr / (1000.0 * 3600.0)
    Vp = cell_area_m2 * h
    Vf = cell_area_m2 * d * filter_porosity
    Vg = cell_area_m2 * (gravel_depth_mm / 1000.0) * DRAINAGE_LAYER["porosity"]
    
    Q  = k * (h / 2.0 + d) / d * cell_area_m2
    t  = (Vp + Vf + Vg) / Q / 3600.0
    return {"V_pond_m3": round(Vp,3), "V_pore_m3": round(Vf+Vg,3),
            "V_total_m3": round(Vp+Vf+Vg,3), "Q_avg_Ls": round(Q*1000,3),
            "drain_time_hr": round(t,1), "drain_time_OK": t <= 72.0}


# ── Pollutant loads (EMC method) ─────────────────────────────────────────────
def pollutant_loads(annual_runoff_m3: float) -> dict:
    out = {}
    for p, emc in EMC_URBAN.items():
        L_in = annual_runoff_m3 * emc * 0.001
        pkey = p.replace("_mgL","_pct")
        rem  = POLLUTANT_REMOVAL.get(pkey, 0) / 100.0
        L_out = L_in * (1.0 - rem)
        out[p] = {"emc_mgL": emc, "load_in_kgyr": round(L_in,2),
                  "removal_pct": POLLUTANT_REMOVAL.get(pkey,0),
                  "load_out_kgyr": round(L_out,2),
                  "removed_kgyr": round(L_in-L_out,2)}
    return out


# ── Annual runoff ─────────────────────────────────────────────────────────────
def annual_runoff(catchment_area_m2, pct_impervious, annual_rainfall_mm):
    return volumetric_runoff_coeff(pct_impervious) * catchment_area_m2 * annual_rainfall_mm / 1000.0
def evaluate_performance(A_cell, d_media_mm, V_inflow_m3, ksat_mmhr, pond_depth_m=0.2, storm_duration_hr=2.0, gravel_depth_mm=0.0):
    """
    Evaluates volume capture and pollutant reduction based on empirical depth relationships.
    Citations: Davis et al. (2009), Water by Design (2014).
    """
    from src.config import DRAINAGE_LAYER
    # 1. Volume Capture
    V_pond = A_cell * pond_depth_m
    V_pores = A_cell * (d_media_mm / 1000.0) * 0.38  # 38% porosity of filter
    V_gravel = A_cell * (gravel_depth_mm / 1000.0) * DRAINAGE_LAYER["porosity"]
    
    V_inf = (ksat_mmhr / 1000.0) * A_cell * storm_duration_hr # Infiltration during storm
    
    V_cap = min(V_inflow_m3, V_pond + V_pores + V_gravel + V_inf)
    vol_pct = (V_cap / V_inflow_m3) * 100.0 if V_inflow_m3 > 0 else 100.0
    
    # 2. Empirical Pollutant Base Efficiency based on Media Depth (m)
    depth_m = d_media_mm / 1000.0
    base_tss = min(98.0, 70.0 + 35.0 * (depth_m / 0.8)) # Approaches 98% at 0.8m
    base_tp  = min(85.0, 45.0 + 50.0 * (depth_m / 0.8)) # Approaches 85% at 0.8m
    base_tn  = min(65.0, 25.0 + 50.0 * (depth_m / 0.8)) # Nitrogen requires deep media
    
    # 3. Overall Efficiency = Base Efficiency * Fraction of Water Captured
    # (Water that bypasses gets 0% treatment)
    cap_frac = V_cap / V_inflow_m3 if V_inflow_m3 > 0 else 1.0
    
    return {
        "vol_pct": round(vol_pct, 1),
        "tss_pct": round(base_tss * cap_frac, 1),
        "tp_pct": round(base_tp * cap_frac, 1),
        "tn_pct": round(base_tn * cap_frac, 1)
    }