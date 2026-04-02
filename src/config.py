"""
config.py — Design constants, material defaults, and reference values
All values reference Water by Design (2014) and Prince George's County (2007)
unless otherwise noted.
"""

# ── FILTER MEDIA ──────────────────────────────────────────────────────────────
FILTER_MEDIA = {
    "ksat_min_mmhr":   100,      # Minimum acceptable Ksat (mm/hr)
    "ksat_target_mmhr":180,      # Target/design Ksat (mm/hr)
    "ksat_max_mmhr":   300,      # Maximum acceptable Ksat (mm/hr)
    "depth_min_mm":    600,      # Minimum filter media depth (mm)
    "depth_default_mm":800,      # Default/recommended depth (mm)
    "depth_trees_mm":  700,      # Minimum depth if trees planted (mm)
    "porosity":        0.38,     # Volumetric porosity of filter media
    "om_pct_min":      3.0,      # Min organic matter content (%)
    "om_pct_max":      6.0,      # Max organic matter content (%)
    "mix": "60% coarse river sand (0.25–1.0 mm) / 25% composted OM (C:N>12, pH 6.5–7.5) / 15% topsoil loam",
}

# ── LAYER DEPTHS (mm) — Water by Design (2014) Table 5 ───────────────────────
# Transition layer: Section 3.2.2.2 — "at least 100 mm deep" for Types 2, 3, 4
# Drainage layer: Table 5 —
#   Type 1: ≥50 mm above pipe (depth governed by saturated zone config)
#   Type 2: ≥150 mm total, grades to outlet at 0.5%
#   Type 3: ≥50 mm above + ≥200 mm below pipe ≈ ≥300 mm total
#   Type 4: no drainage layer
LAYERS = {
    "mulch_mm":                  75,   # Mulch surface cover (WbD 2014 Sec 3.2.2)
    "filter_media_mm":          800,   # Default filter depth (WbD 2014 Sec 3.2.2.1: 500–1000 mm)
    "transition_mm":            100,   # WbD 2014 Sec 3.2.2.2 — minimum 100 mm for Types 2–4
    "drainage_gravel_Type1_mm": 150,   # WbD 2014 Table 5 — Type 1: ≥50 mm above pipe
    "drainage_gravel_Type2_mm": 200,   # WbD 2014 Table 5 — Type 2: ≥150 mm (use 200 mm)
    "drainage_gravel_Type3_mm": 300,   # WbD 2014 Table 5 — Type 3: ≥300 mm (50+pipe+200)
    "drainage_gravel_mm":       200,   # Default fallback (overridden by profile in design.py)
    "geotextile_mm":              5,   # Geotextile (nominal depth for excavation calc)
}

def drainage_gravel_depth(drainage_profile: str, pipe_dia_mm: int = 150) -> int:
    """Return drainage gravel depth (mm) for given profile per WbD (2014) Table 5.
       Dynamically sized to ensure at least 50mm cover above the required pipe diameter."""
    if drainage_profile == "Type4_Pipeless":
        return 0
    
    # Minimum physical absolute cover geometry (pipe diameter + 50mm top cover)
    min_physical_cover = pipe_dia_mm + 50
    
    # Water by Design (2014) structural defaults by profile
    wbd_defaults = {
        "Type1_SaturatedZone": LAYERS["drainage_gravel_Type1_mm"],
        "Type2_Sealed":        LAYERS["drainage_gravel_Type2_mm"],
        "Type3_Conventional":  LAYERS["drainage_gravel_Type3_mm"],
    }.get(drainage_profile, LAYERS["drainage_gravel_mm"])
    
    return max(wbd_defaults, min_physical_cover)

# ── PONDING AND HYDRAULICS ────────────────────────────────────────────────────
PONDING = {
    "max_depth_mm":          200,  # Maximum extended detention depth (mm)
    "max_draindown_hrs":      72,  # Maximum drain-down time (hours)
    "overflow_standpipe_dia": 150, # Default overflow standpipe diameter (mm)
}

# ── UNDERDRAIN ────────────────────────────────────────────────────────────────
UNDERDRAIN = {
    "min_dia_mm":    100,   # Minimum underdrain pipe diameter (mm)
    "std_sizes_mm":  [100, 150, 200, 250, 300],  # Standard UPVC sizes
    "slope_min_pct": 0.5,   # Minimum slope (%)
    "slope_default_pct": 1.0,
    "mannings_n":    0.011, # Manning's n for smooth UPVC
    "blockage_factor": 0.8, # Capacity reduction for blockage (80% of full)
    "slot_width_mm": 6,     # Perforation slot width (mm)
    "slot_spacing_mm": 150, # Slot spacing (mm)
    "max_spacing_m": 2.5,   # Max lateral spacing between underdrain pipes (m)
}

# ── GRAVEL DRAINAGE LAYER ─────────────────────────────────────────────────────
DRAINAGE_LAYER = {
    "material": "Double-washed crushed stone or river gravel, 10–20 mm",
    "ksat_mmhr": 50000,   # Effective Ksat of gravel layer (very high)
    "porosity": 0.40,     # Void ratio of gravel
    "fines_pct_max": 2.0, # Maximum fines content (%)
}

# ── GEOTEXTILE ────────────────────────────────────────────────────────────────
GEOTEXTILE = {
    "base_gsm":      200,  # Base/side geotextile (g/m²)
    "transition_gsm": 150, # Transition layer geotextile (g/m²)
}

# ── SIZING RULES ─────────────────────────────────────────────────────────────
SIZING = {
    "wq_design_depth_mm": 25,    # Water quality design rainfall depth (mm)
    "cell_area_min_pct":   2.0,  # Min cell area as % of contributing catchment
    "cell_area_target_pct":3.0,  # Target cell area as % of contributing catchment
    "drain_time_hrs":     24.0,  # Target drain-down time (hours)
    "min_cell_area_m2":    4.0,  # Minimum practical cell area (m2)
    "max_cell_length_m":  40.0,  # Maximum cell length (m)
    "max_cell_width_m":   15.0,  # Maximum cell width (one-side access)
    "min_cell_width_m":    0.6,  # Minimum practical cell width (m)
    "ar_min":              1.5,  # Minimum length:width aspect ratio
    "ar_default":          2.5,  # Default aspect ratio (length:width)
}

# ── RUNOFF COEFFICIENTS (Rational Method) ─────────────────────────────────────
RUNOFF_COEFFICIENTS = {
    "roof_concrete":   0.90,
    "paved_road":      0.85,
    "gravel_road":     0.60,
    "lawn_flat":       0.18,
    "lawn_steep":      0.25,
    "playing_field":   0.20,
    "woodland":        0.12,
    "water_body":      1.00,
}

# ── POLLUTANT REMOVAL (published median values) ───────────────────────────────
POLLUTANT_REMOVAL = {
    "TSS_pct":   88,   # Total Suspended Solids removal (Davis et al., 2009)
    "TP_pct":    65,   # Total Phosphorus removal
    "TN_pct":    42,   # Total Nitrogen removal
    "Zn_pct":    90,   # Zinc removal
    "Cu_pct":    85,   # Copper removal
}

# ── EVENT MEAN CONCENTRATIONS — urban stormwater (Tsihrintzis & Hamid, 1998) ──
EMC_URBAN = {
    "TSS_mgL":   150,
    "TP_mgL":    0.30,
    "TN_mgL":    2.00,
}

# ── TOTAL EXCAVATION DEPTH ────────────────────────────────────────────────────
def total_excavation_depth(filter_depth_mm=800, saturated_zone=False, sz_depth_mm=350):
    """
    Returns total excavation depth below finished ground surface (mm).
    Layers: ponding (0 — above ground) + mulch + filter + transition + gravel + geotextile
    Add settlement allowance (100 mm) to filter media.
    """
    settlement_mm = 100
    d = (LAYERS["mulch_mm"]
         + filter_depth_mm + settlement_mm
         + LAYERS["transition_mm"]
         + LAYERS["drainage_gravel_mm"]
         + LAYERS["geotextile_mm"])
    if saturated_zone:
        d += sz_depth_mm  # additional saturated zone below drainage gravel
    return d


# ── PIPE STANDARD SIZES ───────────────────────────────────────────────────────
PIPE_SIZES_MM = [100, 150, 200, 250, 300, 375, 450]

# ── COLOUR PALETTE (for plots) ───────────────────────────────────────────────
COLOURS = {
    "bg":       "#F5F5F0",
    "dark":     "#1F3864",
    "mid":      "#2E75B6",
    "light":    "#D6E4F0",
    "green":    "#2E7D32",
    "green_l":  "#C8E6C9",
    "sand":     "#D4A843",
    "gravel":   "#8B7355",
    "water":    "#4FC3F7",
    "red":      "#C62828",
    "orange":   "#E65100",
    "grey":     "#607D8B",
    "mulch":    "#6D4C41",
    "geo":      "#B0BEC5",
    "liner":    "#263238",
    "grass":    "#558B2F",
}
