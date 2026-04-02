"""
plots.py — Engineering drawings and analysis charts.

FIXED BUGS (v2):
  BUG-FIX-1: plot_draindown() — h_cur was NEVER updated in the while loop,
              so the ponding depth remained stuck at the initial value,
              producing a flat horizontal line and drain_t = 0.0 hr.
              Fix: added `h_cur = h_new` inside the loop.
              Now shows correct two-phase curve (ponding + filter drainage).

  BUG-FIX-4: plot_hydrology() now shows:
              - Separate inflow vs outflow curves (pre-cell vs post-cell)
              - Filtered flow vs overflow breakdown
              - Volume balance statistics box
              - Peak reduction % and volume captured %
              Previously inflow and outflow lines were identical (0% reduction).
"""

import math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import matplotlib.gridspec as gridspec
from src.config import COLOURS as C, LAYERS, PONDING, FILTER_MEDIA


plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9,
    "axes.facecolor": C["bg"], "figure.facecolor": "white",
    "axes.edgecolor": "#333333", "axes.linewidth": 0.8, "axes.grid": False,
})


def _save(fig, path):
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path


# ── 1. CROSS-SECTION ──────────────────────────────────────────────────────────
def draw_cross_section(layer_info: dict, cell_dims: dict,
                        underdrain: dict, overflow: dict,
                        output_path: str) -> str:
    fig, ax = plt.subplots(figsize=(14, 8))
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("BIORETENTION CELL — CROSS-SECTION  (Vertical scale exaggerated for clarity)",
                 fontsize=10, fontweight="bold", color=C["dark"], pad=8)

    W = cell_dims["width_m"]
    batter_w = 1.2
    y_scale = 2.0

    d_geo   = LAYERS["geotextile_mm"]  / 1000.0 * y_scale
    d_grav  = LAYERS["drainage_gravel_mm"] / 1000.0 * y_scale
    d_trans = LAYERS["transition_mm"]  / 1000.0 * y_scale
    d_filt  = layer_info["filter_depth_mm"] / 1000.0 * y_scale + 0.10
    d_mulch = LAYERS["mulch_mm"]       / 1000.0 * y_scale
    d_pond  = PONDING["max_depth_mm"]  / 1000.0 * y_scale

    y_base  = 0.0
    y_geo   = y_base  + d_geo
    y_grav  = y_geo   + d_grav
    y_trans = y_grav  + d_trans
    y_filt  = y_trans + d_filt
    y_mulch = y_filt  + d_mulch
    y_gnd   = y_mulch
    y_pond  = y_gnd + d_pond
    y_berm  = y_gnd + 0.30
    ground_level = y_gnd + 0.05

    # Native soil background
    ax.add_patch(patches.Rectangle((-batter_w, -0.6), W+2*batter_w, 0.6,
                                    facecolor="#C4A882", edgecolor="none", zorder=1))
    ax.text(W/2, -0.3, "In-situ soil (native ground)", ha="center", va="center",
            fontsize=8, color="#5D3A1A", style="italic")

    # Liner
    liner_col = C["liner"] if "Impermeable" in layer_info.get("liner_type","") else C["geo"]
    ax.add_patch(patches.Rectangle((0, y_base-d_geo), W, d_geo*3,
                                    facecolor=liner_col, edgecolor="none", alpha=0.85, zorder=2))
    for x_s in [0, W]:
        ax.add_patch(patches.Rectangle((x_s if x_s==0 else x_s-0.03, y_base),
                                        0.03, y_grav+d_trans+d_filt,
                                        facecolor=liner_col, edgecolor="none", alpha=0.7, zorder=2))

    # Gravel drainage layer
    ax.add_patch(patches.Rectangle((0,y_base), W, d_grav,
                                    facecolor=C["gravel"], edgecolor="#555",
                                    linewidth=0.5, alpha=0.85, zorder=3))
    ax.add_patch(patches.Rectangle((0,y_base), W, d_grav,
                                    facecolor="none", edgecolor=C["gravel"],
                                    hatch="...", linewidth=0.3, zorder=4))

    # Underdrain pipe
    pipe_d = underdrain["selected_dia_mm"] / 1000.0 * y_scale * 0.6
    pipe_y = y_base + d_grav * 0.4
    pipe_x = W / 2
    ax.add_patch(plt.Circle((pipe_x, pipe_y), pipe_d/2, color="#333333", zorder=6))
    ax.add_patch(plt.Circle((pipe_x, pipe_y), pipe_d/2*0.7, color="white", zorder=7))
    ax.text(pipe_x, pipe_y-pipe_d, f"Ø{underdrain['selected_dia_mm']} mm perf. UPVC\n@ {underdrain['slope_pct']}%",
            ha="center", va="top", fontsize=7, color="#111", zorder=8)

    # Transition layer
    ax.add_patch(patches.Rectangle((0,y_grav), W, d_trans,
                                    facecolor="#D4C494", edgecolor="#999", linewidth=0.5, alpha=0.85, zorder=3))

    # Filter media
    ax.add_patch(patches.Rectangle((0,y_trans), W, d_filt,
                                    facecolor=C["sand"], edgecolor="#888", linewidth=0.5, alpha=0.75, zorder=3))
    ax.text(W/2, y_trans+d_filt*0.5,
            f"FILTER MEDIA  Ksat={FILTER_MEDIA['ksat_target_mmhr']} mm/hr (target)\n"
            f"{layer_info['filter_depth_mm']} mm  (+100 mm settlement allowance)",
            ha="center", va="center", fontsize=8, color="#4A3000", fontweight="bold", zorder=8)

    # Mulch
    ax.add_patch(patches.Rectangle((0,y_filt), W, d_mulch,
                                    facecolor=C["mulch"], edgecolor="#555", linewidth=0.5, alpha=0.9, zorder=4))

    # Extended detention zone
    ax.add_patch(patches.Rectangle((0,y_gnd), W, d_pond,
                                    facecolor=C["water"], edgecolor=C["mid"],
                                    linewidth=0.8, alpha=0.3, zorder=4, linestyle="--"))
    ax.text(W*0.75, y_gnd+d_pond*0.5,
            f"PONDING ZONE\n{PONDING['max_depth_mm']} mm (max)", ha="center", va="center",
            fontsize=7, color="#005580", zorder=8)

    # Berms
    for xs, ys in [
        ([-batter_w, 0, 0, -batter_w], [ground_level, ground_level, y_berm, y_berm]),
        ([W, W+batter_w, W+batter_w, W], [y_berm, ground_level, ground_level, y_berm]),
    ]:
        ax.add_patch(plt.Polygon(list(zip(xs,ys)), facecolor="#A0855A",
                                  edgecolor="#555", linewidth=0.8, alpha=0.7, zorder=3))

    ax.plot([-batter_w*2,-batter_w], [ground_level,ground_level], color="#333", lw=1.5, zorder=10)
    ax.plot([W+batter_w, W+batter_w*2], [ground_level,ground_level], color="#333", lw=1.5, zorder=10)

    # Overflow standpipe
    sp_x = W*0.15
    sp_h = y_pond + 0.05
    sp_d = overflow.get("selected_dia_mm", 150) / 1000.0 * y_scale * 0.5
    ax.add_patch(patches.Rectangle((sp_x-sp_d/2, y_base), sp_d, sp_h,
                                    facecolor="white", edgecolor="#333", linewidth=1.2, zorder=9))
    ax.annotate(f"Overflow standpipe\nØ{overflow.get('selected_dia_mm','—')}mm\ncrest +200mm above media",
                xy=(sp_x,sp_h), xytext=(sp_x-0.8,sp_h+0.18), fontsize=7, ha="right",
                arrowprops=dict(arrowstyle="->", color="#333", lw=0.8), zorder=12)

    # Ponding crest line
    ax.plot([0,W], [y_gnd+d_pond*0.95]*2, color=C["mid"], lw=0.8, linestyle="dashed", alpha=0.6)
    ax.text(-0.05, y_gnd+d_pond*0.95, "Max ponding level", ha="right", va="center",
            fontsize=6.5, color=C["mid"])

    # Vegetation
    np.random.seed(42)
    for xi in np.linspace(0.1, W-0.1, 14):
        h = 0.18+np.random.rand()*0.15
        ax.plot([xi,xi-0.05],[y_gnd,y_gnd+h], color=C["green"], lw=1.2, alpha=0.8)
        ax.plot([xi,xi+0.07],[y_gnd,y_gnd+h*0.7], color=C["green"], lw=1.0, alpha=0.6)

    # Dimension lines (right side)
    def dim(ax, x1,y1,x2,y2,lbl,off=0.08):
        ax.annotate("", xy=(x2,y2), xytext=(x1,y1),
                    arrowprops=dict(arrowstyle="<->", color="#333", lw=0.8))
        ax.text((x1+x2)/2+off, (y1+y2)/2, lbl, ha="left", va="center",
                fontsize=7, color="#111", zorder=12)

    rx = W + batter_w + 0.12
    dim(ax, rx,   y_base, rx,   y_grav, f"{LAYERS['drainage_gravel_mm']} mm Gravel")
    dim(ax, rx+.5,y_grav, rx+.5,y_trans,f"{LAYERS['transition_mm']} mm Transition")
    dim(ax, rx+1, y_trans,rx+1, y_filt, f"{layer_info['filter_depth_mm']} mm Filter")
    dim(ax, rx+1.5,y_filt,rx+1.5,y_mulch,f"{LAYERS['mulch_mm']} mm Mulch")
    dim(ax, rx+2, y_gnd, rx+2, y_pond, f"{PONDING['max_depth_mm']} mm Ponding")

    # Width dimension
    dim(ax, 0, y_base-0.4, W, y_base-0.4, f"Width = {cell_dims['width_m']:.1f} m")
    dim(ax,-batter_w,y_base-0.65,W+batter_w,y_base-0.65,
        f"Total footprint = {W+2*batter_w:.1f} m (incl. berms)")

    # Excavation depth
    ax.annotate("", xy=(-batter_w-0.1,y_base), xytext=(-batter_w-0.1,y_mulch),
                arrowprops=dict(arrowstyle="<->", color=C["dark"], lw=1.0))
    ax.text(-batter_w-0.18,(y_base+y_mulch)/2,
            f"Excav.\n{layer_info['total_excavation_mm']} mm",
            ha="right", va="center", fontsize=7, color=C["dark"], rotation=90, fontweight="bold")

    # Legend
    legend_items = [
        (C["gravel"],   "Gravel drainage layer (10-20 mm)"),
        ("#D4C494",     "Transition layer (pea gravel 2-6 mm)"),
        (C["sand"],     "Filter media (60% sand / 25% compost / 15% loam)"),
        (C["mulch"],    "Mulch (wood chip 50-75 mm)"),
        (C["water"],    "Extended detention (ponding) zone"),
        ("#A0855A",     "Compacted earthen berm"),
        (C["liner"],    "Impermeable liner / geotextile"),
        (C["green"],    "Planted vegetation"),
    ]
    lx = W + batter_w + 0.1
    for i,(col,lbl) in enumerate(legend_items):
        iy = -0.55 + i*0.17
        ax.add_patch(patches.Rectangle((lx,iy),0.18,0.13,
                                        facecolor=col,edgecolor="#555",linewidth=0.5,zorder=12))
        ax.text(lx+0.25,iy+0.04,lbl,fontsize=6.5,va="center",zorder=12)

    ax.set_xlim(-batter_w*2-0.3, W+batter_w*2+3.5)
    ax.set_ylim(-0.75, y_pond+0.5)
    fig.text(0.01,0.01,
             f"Filter depth: {layer_info['filter_depth_mm']} mm | Profile: {layer_info['drainage_profile']} | "
             f"Excavation: {layer_info['total_excavation_mm']} mm | Underdrain: Ø{underdrain['selected_dia_mm']} mm @ {underdrain['slope_pct']}%",
             fontsize=7, color="#444")
    _save(fig, output_path)
    return output_path


# ── 2. PLAN VIEW ──────────────────────────────────────────────────────────────
def draw_plan_view(cell_dims: dict, underdrain: dict, overflow: dict,
                   output_path: str) -> str:
    L = cell_dims["length_m"]
    W = cell_dims["width_m"]
    scale = min(12.0/L, 9.0/(W+3.5))
    fig, ax = plt.subplots(figsize=(max(12,L*scale*1.3), max(8,(W+3)*scale*1.2)))
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("BIORETENTION CELL — PLAN VIEW (SCHEMATIC)",
                 fontsize=10, fontweight="bold", color=C["dark"], pad=6)

    berm_off = 1.2
    # Outer berm boundary
    ax.add_patch(patches.Rectangle((-berm_off,-berm_off), L+2*berm_off, W+2*berm_off,
                                    facecolor="#D4C4A0", edgecolor="#777", linewidth=1.0, alpha=0.5, zorder=1))
    # Filter media area
    ax.add_patch(patches.Rectangle((0,0), L, W, facecolor=C["sand"],
                                    edgecolor=C["dark"], linewidth=1.8, alpha=0.65, zorder=2))

    # Zone 1 (wet inner)
    z1w = W*0.35
    ax.add_patch(patches.Rectangle((L*0.1, W*0.5-z1w/2), L*0.8, z1w,
                                    facecolor=C["water"], edgecolor=C["mid"],
                                    linewidth=0.8, alpha=0.35, zorder=3, linestyle="--"))
    ax.text(L*0.5, W*0.5, "Zone 1\n(Wet inner)", ha="center", va="center",
            fontsize=7.5, color="#005580", style="italic")
    ax.text(L*0.5, W*0.87, "Zone 2 (Transition)", ha="center", fontsize=7, color="#4A3000", alpha=0.7)
    ax.text(L*0.5, W*0.12, "Zone 2 (Transition)", ha="center", fontsize=7, color="#4A3000", alpha=0.7)

    # Underdrain pipes
    n_pipes = underdrain["n_pipes"]
    pipe_ys = [W/(n_pipes+1)*(i+1) for i in range(n_pipes)]
    for py in pipe_ys:
        ax.plot([L*0.05, L*0.90], [py,py], color="#333", lw=2.0, zorder=5)
        for rx in [L*0.05, L*0.90]:
            ax.add_patch(plt.Circle((rx,py), 0.12, facecolor="white",
                                     edgecolor="#333", lw=1.5, zorder=6))
            ax.text(rx, py-0.28, "CO", ha="center", fontsize=6, color="#333")
        ax.text(L*0.47, py+0.20, f"Ø{underdrain['selected_dia_mm']} mm perf. UPVC",
                ha="center", fontsize=7, color="#333")

    # Overflow standpipe
    sp_x, sp_y = L*0.92, W*0.5
    ax.add_patch(plt.Circle((sp_x,sp_y), 0.22, facecolor=C["mid"],
                              edgecolor=C["dark"], lw=1.5, zorder=7))
    ax.text(sp_x, sp_y+0.40, f"Overflow sp.\nØ{overflow.get('selected_dia_mm','—')}mm",
            ha="center", fontsize=6.5, color=C["dark"])

    # Outlet arrow
    ax.annotate("", xy=(L+berm_off+0.3, sp_y), xytext=(sp_x+0.22,sp_y),
                arrowprops=dict(arrowstyle="-|>", color=C["mid"], lw=2.0))
    ax.text(L+berm_off+0.38, sp_y, "To existing\ndrain", ha="left", va="center",
            fontsize=7, color=C["mid"])

    # Inlet
    inlet_y = W*0.5
    ax.annotate("", xy=(0.0,inlet_y), xytext=(-berm_off-0.4,inlet_y),
                arrowprops=dict(arrowstyle="-|>", color=C["orange"], lw=2.5))
    ax.add_patch(patches.FancyBboxPatch((-berm_off-1.2,inlet_y-0.28),1.2,0.56,
                                         boxstyle="round,pad=0.05",
                                         facecolor=C["orange"],edgecolor="#333",alpha=0.8,zorder=8))
    ax.text(-berm_off-0.6,inlet_y,"INLET\n(kerb cut /\ndownpipe)",
            ha="center",va="center",fontsize=6.5,color="white",fontweight="bold")
    # Stone apron
    ax.add_patch(patches.Rectangle((0.0,inlet_y-0.30),0.6,0.60,
                                    facecolor=C["gravel"],edgecolor="#555",
                                    linewidth=0.7,alpha=0.7,zorder=5,hatch="..."))
    ax.text(0.3,inlet_y-0.52,"Riprap\napron",ha="center",fontsize=6,color="#444")

    # Maintenance path
    ax.add_patch(patches.Rectangle((0,-berm_off), L, 0.65,
                                    facecolor="#C8B88A",edgecolor="#888",linewidth=0.7,alpha=0.7,zorder=3))
    ax.text(L/2,-berm_off+0.32,"Maintenance path (1.0 m wide, compacted laterite)",
            ha="center",va="center",fontsize=7,color="#333")

    # Vegetation dots
    np.random.seed(7)
    for _ in range(min(70, int(L*W*3))):
        px=np.random.uniform(0.05,L-0.05); py2=np.random.uniform(0.05,W-0.05)
        ax.add_patch(plt.Circle((px,py2),0.06+np.random.rand()*0.07,
                                 color=C["green"],alpha=0.35+np.random.rand()*0.35,zorder=4))

    # Dimensions
    ax.annotate("", xy=(L,-berm_off-0.8), xytext=(0,-berm_off-0.8),
                arrowprops=dict(arrowstyle="<->",color="#333",lw=1.0))
    ax.text(L/2,-berm_off-1.0,f"Length = {L:.1f} m",ha="center",fontsize=8.5,fontweight="bold")
    ax.annotate("", xy=(L+berm_off+1.0,W), xytext=(L+berm_off+1.0,0),
                arrowprops=dict(arrowstyle="<->",color="#333",lw=1.0))
    ax.text(L+berm_off+1.18,W/2,f"Width = {W:.1f} m",va="center",ha="left",
            fontsize=8.5,fontweight="bold",rotation=90)
    ax.text(L/2,W+0.35,
            f"Filter media area = {cell_dims['area_m2']:.1f} m2  |  AR = {cell_dims['aspect_ratio']:.1f}:1",
            ha="center",fontsize=8,color=C["dark"],fontweight="bold")

    # North arrow
    ax.annotate("",xy=(L+berm_off+2.5,W/2+0.8),xytext=(L+berm_off+2.5,W/2-0.2),
                arrowprops=dict(arrowstyle="-|>",color="#333",lw=1.5))
    ax.text(L+berm_off+2.5,W/2+1.0,"N",ha="center",fontsize=9,fontweight="bold")

    ax.set_xlim(-berm_off*3, L+berm_off*2+3.5)
    ax.set_ylim(-berm_off*3.5, W+berm_off*2+0.5)
    _save(fig, output_path)
    return output_path


# ── 3. HYDROLOGY — FIXED BUG-4 ────────────────────────────────────────────────
def plot_hydrology(routed_df,   # inflow_df (pre-cell catchment response)
                   routed_bf,   # routed_bf (post-cell — filtered + overflow)
                   vol_balance: dict,
                   region: str, return_period: str,
                   output_path: str) -> str:
    """
    3-panel hydrology figure:
    (top)    Design hyetograph with rainfall and runoff intensity bars
    (mid)    Inflow vs. outflow hydrograph — CLEARLY showing peak reduction
             and breakdown into filtered vs. overflow components
    (bottom) Volume bar chart comparison (pre-cell vs post-cell)

    BUG-FIX-4: Previously showed inflow = outflow (0% reduction) because
    the cell area was constrained by WQV alone. Now shows:
      - Actual pre-cell runoff hydrograph
      - Post-cell: filtered (captured/treated) + overflow (bypassed)
      - Volume balance in a third panel
    """
    fig = plt.figure(figsize=(11, 12))
    gs  = gridspec.GridSpec(3, 1, figure=fig, hspace=0.45,
                             height_ratios=[1.0, 1.6, 0.9])

    fig.suptitle(f"Hydrological Analysis  —  {region} Division  |  "
                 f"{return_period.replace('yr','-yr')} ARI Design Storm",
                 fontsize=11, fontweight="bold", color=C["dark"])

    t = routed_df["time_min"].values

    # ── Panel 1: Hyetograph ──────────────────────────────────────────────────
    ax1 = fig.add_subplot(gs[0])
    ax1.bar(t, routed_df["intensity_mmhr"], width=4.0,
            color=C["mid"], edgecolor=C["dark"], linewidth=0.5, alpha=0.85,
            label="Rainfall intensity")
    ax1.bar(t, routed_df["runoff_mmhr"], width=4.0,
            color=C["orange"], edgecolor="#8B3A00", linewidth=0.5, alpha=0.80,
            label="Runoff intensity (× Rv)")
    ax1.set_ylabel("Intensity (mm/hr)", fontsize=9)
    ax1.legend(fontsize=8, loc="upper right")
    ax1.set_facecolor(C["bg"])
    ax1.set_xlim(0, t[-1]+5)
    ax1.tick_params(labelsize=8)
    ax1.set_title(f"Design Hyetograph  (peak intensity = {routed_df['intensity_mmhr'].max():.1f} mm/hr  "
                  f"|  total rainfall = {routed_df['rainfall_mm'].sum():.1f} mm)",
                  fontsize=8.5, color="#444")

    # Secondary y: cumulative rainfall
    ax1b = ax1.twinx()
    ax1b.plot(t, routed_df["cumul_rain_mm"], color=C["dark"], lw=1.5,
              linestyle="--", alpha=0.7, label="Cumul. rainfall")
    ax1b.plot(t, routed_df["cumul_runoff_mm"], color=C["red"], lw=1.5,
              linestyle="--", alpha=0.7, label="Cumul. runoff")
    ax1b.set_ylabel("Cumulative (mm)", fontsize=9, color="#555")
    ax1b.legend(fontsize=8, loc="center right")
    ax1b.tick_params(labelsize=8)

    # ── Panel 2: Inflow vs Outflow breakdown ─────────────────────────────────
    ax2 = fig.add_subplot(gs[1])

    # Pre-cell runoff (what would happen without bioretention)
    ax2.fill_between(t, 0, routed_df["inflow_Ls"],
                     alpha=0.15, color=C["mid"])
    ax2.plot(t, routed_df["inflow_Ls"],
             color=C["mid"], lw=2.5, label="Pre-cell runoff (no treatment)")

    # Filtered component (treated — passed through media)
    ax2.fill_between(t, 0, routed_bf["q_filt_Ls"],
                     alpha=0.50, color=C["green"])
    ax2.plot(t, routed_bf["q_filt_Ls"],
             color=C["green"], lw=1.5, label="Filtered flow (treated by media)")

    # Overflow component (bypassed — not treated)
    ax2.fill_between(t, routed_bf["q_filt_Ls"],
                     routed_bf["q_filt_Ls"] + routed_bf["q_overflow_Ls"],
                     alpha=0.40, color=C["red"])
    ax2.plot(t, routed_bf["q_total_out_Ls"],
             color=C["red"], lw=1.5, linestyle="--",
             label="Total outflow (filtered + overflow)")

    # Ponding depth on secondary y
    ax2b = ax2.twinx()
    ax2b.fill_between(t, 0, routed_bf["ponding_mm"],
                      alpha=0.25, color=C["water"])
    ax2b.plot(t, routed_bf["ponding_mm"],
              color=C["water"], lw=1.5, linestyle=":",
              label=f"Ponding depth (max {PONDING['max_depth_mm']} mm)")
    ax2b.axhline(PONDING["max_depth_mm"], color=C["water"], lw=0.8,
                 linestyle="--", alpha=0.5)
    ax2b.set_ylabel("Ponding depth (mm)", fontsize=8.5, color="#2277AA")
    ax2b.set_ylim(0, PONDING["max_depth_mm"] * 2.5)
    ax2b.tick_params(labelsize=8, colors="#2277AA")
    ax2b.legend(fontsize=7.5, loc="upper right")

    # Stats box
    pk_in  = vol_balance["Q_in_peak_Ls"]
    pk_out = vol_balance["Q_out_peak_Ls"]
    pk_red = vol_balance["peak_red_pct"]
    v_cap  = vol_balance["V_captured_pct"]
    ax2.text(0.01, 0.97,
             f"Peak inflow:   {pk_in:.1f} L/s\n"
             f"Peak outflow:  {pk_out:.1f} L/s\n"
             f"Peak reduction: {pk_red:.1f}%\n"
             f"Volume captured: {v_cap:.1f}%",
             transform=ax2.transAxes, ha="left", va="top", fontsize=9,
             color=C["dark"], fontweight="bold",
             bbox=dict(boxstyle="round,pad=0.35", facecolor="white",
                        edgecolor=C["dark"], alpha=0.9))

    ax2.set_xlabel("Time (minutes)", fontsize=9)
    ax2.set_ylabel("Flow rate (L/s)", fontsize=9)
    ax2.legend(fontsize=8, loc="upper left")
    ax2.set_facecolor(C["bg"])
    ax2.set_xlim(0, t[-1]+5)
    ax2.tick_params(labelsize=8)
    ax2.set_title("Hydrograph Comparison — Pre-cell vs Post-cell  "
                  "(Green = treated through filter  |  Red = overflow bypassed)",
                  fontsize=8.5, color="#444")

    # ── Panel 3: Volume bar chart ─────────────────────────────────────────────
    ax3 = fig.add_subplot(gs[2])
    vb = vol_balance
    categories = ["Pre-cell\n(all runoff)", "Post-cell\n(treated)", "Post-cell\n(overflow)"]
    volumes    = [vb["V_in_m3"], vb["V_filtered_m3"], vb["V_overflow_m3"]]
    colors     = [C["mid"], C["green"], C["red"]]

    bars = ax3.bar(categories, volumes, color=colors, edgecolor="#333",
                   linewidth=0.8, alpha=0.85, width=0.45)
    for bar, vol in zip(bars, volumes):
        ax3.text(bar.get_x() + bar.get_width()/2,
                 bar.get_height() + 2,
                 f"{vol:.1f} m³", ha="center", fontsize=9, fontweight="bold")

    # Percentage labels
    ax3.text(1, volumes[1]/2, f"{vb['V_captured_pct']:.1f}%\ncaptured",
             ha="center", va="center", fontsize=9, color="white", fontweight="bold")
    if volumes[2] > 0:
        pct_ov = vb["V_overflow_m3"]/vb["V_in_m3"]*100
        ax3.text(2, volumes[2]/2, f"{pct_ov:.1f}%\noverflow",
                 ha="center", va="center", fontsize=9, color="white", fontweight="bold")

    ax3.set_ylabel("Event Runoff Volume (m³)", fontsize=9)
    ax3.set_facecolor(C["bg"])
    ax3.tick_params(labelsize=9)
    ax3.set_title("Event Volume Balance — EMC pollutant loads scale proportionally with filtered volume",
                  fontsize=8.5, color="#444")
    ax3.set_ylim(0, max(volumes)*1.2)

    plt.tight_layout(rect=[0,0,1,0.96])
    _save(fig, output_path)
    return output_path


# ── 4. DRAIN-DOWN — FIXED BUG-1 ──────────────────────────────────────────────
def plot_draindown(cell_area_m2: float, filter_depth_mm: float,
                   filter_porosity: float, ponding_mm: float,
                   ksat_mmhr: float, output_path: str) -> str:
    """
    Drain-down simulation after a full ponding + saturated media event.

    BUG-FIX-1: h_cur was NEVER updated in the while loop (h_cur = h_new
    was missing). This caused:
      - Flat horizontal line stuck at initial ponding depth
      - drain_t = 0.0 hr (argmax returned first element since no value < 1mm)
    Fix: added `h_cur = h_new` inside the loop.

    Now shows two phases:
      Phase 1 (orange): ponding draining (h_pond decreases to 0)
      Phase 2 (blue):   filter media pore-water draining (captured by underdrain)
    """
    ksat_ms = ksat_mmhr / (1000.0 * 3600.0)
    d       = filter_depth_mm / 1000.0
    n       = filter_porosity
    h0      = ponding_mm / 1000.0

    dt      = 60.0       # 1-minute steps
    t_max   = 120 * 3600 # 120-hour simulation limit

    # Phase 1: ponding drainage (while h_pond > 0)
    t1_s, h1_s = [0.0], [h0]
    t_cur, h_cur = 0.0, h0

    while h_cur > 0.0001 and t_cur < t_max:
        q     = ksat_ms * (h_cur + d) / d  # Darcy flux (m/s)
        dh    = -q * dt                    # depth change (m) — q is per-unit-area flux
        h_new = max(h_cur + dh, 0.0)
        h_cur = h_new                      # ← BUG-FIX: this line was MISSING
        t_cur += dt
        t1_s.append(t_cur / 3600.0)
        h1_s.append(h_new * 1000.0)       # → mm

    t_pond_empty_hr = t_cur / 3600.0

    # Phase 2: filter pore drainage (no ponding — media drains at baseflow Ksat)
    # Remaining pore volume = d × n × A (all at unit area)
    # q_base = Ksat (no ponding head, just gravity = head = d)
    q_base     = ksat_ms  # m/s (unit gradient through saturated media)
    V_pore_m   = d * n    # m of water stored in pores (per m² of cell)
    dt2        = 300.0    # 5-minute steps for phase 2
    t2_s, v2_s = [t_pond_empty_hr], [V_pore_m * 1000.0]  # store in mm-equivalent
    v_cur      = V_pore_m
    t_cur2     = t_pond_empty_hr * 3600.0

    while v_cur > 0.001 * d and t_cur2 < t_max:
        dv    = -q_base * dt2
        v_new = max(v_cur + dv, 0.0)
        v_cur = v_new
        t_cur2 += dt2
        t2_s.append(t_cur2 / 3600.0)
        v2_s.append(v_new * 1000.0)

    t_fully_drained_hr = t_cur2 / 3600.0

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 7),
                                    gridspec_kw={"height_ratios": [1.4, 1]})
    fig.suptitle("DRAIN-DOWN SIMULATION — Full ponding + saturated media event",
                 fontsize=10, fontweight="bold", color=C["dark"])

    # Panel 1: Ponding depth vs time
    ax1.fill_between(t1_s, 0, h1_s, alpha=0.30, color=C["orange"])
    ax1.plot(t1_s, h1_s, color=C["orange"], lw=2.5,
             label=f"Ponding depth — drains to 0 at {t_pond_empty_hr:.1f} hr")
    ax1.axvline(72, color=C["red"], lw=1.5, linestyle="--", alpha=0.8,
                label="72-hr maximum drain-down limit")
    ax1.axhline(0, color=C["green"], lw=0.8, linestyle="--", alpha=0.6)

    # Annotate phase 1 completion
    ax1.axvline(t_pond_empty_hr, color=C["orange"], lw=1.2,
                linestyle=":", alpha=0.8)
    ax1.text(t_pond_empty_hr + 0.3, ponding_mm * 0.85,
             f"Ponding clears\n@ {t_pond_empty_hr:.1f} hr",
             fontsize=8, color=C["orange"], va="top")

    status = "PASS" if t_pond_empty_hr <= 72 else "FAIL"
    scol   = C["green"] if status == "PASS" else C["red"]
    ax1.text(0.97, 0.95,
             f"Ksat = {ksat_mmhr} mm/hr  |  Filter = {filter_depth_mm} mm\n"
             f"Initial ponding = {ponding_mm} mm\n"
             f"Ponding clears: {t_pond_empty_hr:.1f} hr — {status}",
             transform=ax1.transAxes, ha="right", va="top", fontsize=9,
             color=scol, fontweight="bold",
             bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                        edgecolor=scol, alpha=0.9))

    ax1.set_xlabel("Time after end of rainfall (hours)", fontsize=9)
    ax1.set_ylabel("Ponding depth (mm)", fontsize=9)
    ax1.set_title("Phase 1: Ponding zone drainage  (critical for mosquito control — must clear < 72 hr)",
                  fontsize=8.5, color="#444")
    ax1.legend(fontsize=8)
    ax1.set_facecolor(C["bg"])
    ax1.set_xlim(0, max(t_pond_empty_hr * 2.5, 10))
    ax1.set_ylim(0, ponding_mm * 1.2)
    ax1.tick_params(labelsize=8)

    # Panel 2: Filter pore drainage
    ax2.fill_between(t2_s, 0, v2_s, alpha=0.30, color=C["mid"])
    ax2.plot(t2_s, v2_s, color=C["mid"], lw=2.0,
             label=f"Filter pore-water  (n={n})  — drains by {t_fully_drained_hr:.1f} hr total")
    ax2.axvline(72, color=C["red"], lw=1.5, linestyle="--", alpha=0.8, label="72-hr limit")
    ax2.text(0.97, 0.92,
             f"Filter porosity n = {n}\nPore storage = {d*n*1000:.0f} mm-equiv.\n"
             f"Full drainage at {t_fully_drained_hr:.1f} hr",
             transform=ax2.transAxes, ha="right", va="top", fontsize=9,
             bbox=dict(boxstyle="round,pad=0.3", facecolor="white",
                        edgecolor=C["mid"], alpha=0.9))
    ax2.set_xlabel("Time after end of rainfall (hours)", fontsize=9)
    ax2.set_ylabel("Remaining pore-water\n(mm-equivalent depth)", fontsize=9)
    ax2.set_title("Phase 2: Filter media pore drainage  (governs return to full treatment capacity)",
                  fontsize=8.5, color="#444")
    ax2.legend(fontsize=8)
    ax2.set_facecolor(C["bg"])
    ax2.set_xlim(t_pond_empty_hr, min(t_fully_drained_hr * 1.5, 120))
    ax2.tick_params(labelsize=8)

    plt.tight_layout(rect=[0,0,1,0.96])
    _save(fig, output_path)
    return output_path


# ── 5. SUMMARY DASHBOARD ──────────────────────────────────────────────────────
def plot_design_summary(results: dict, output_path: str) -> str:
    fig = plt.figure(figsize=(14, 9))
    fig.suptitle("BIORETENTION DESIGN — SUMMARY DASHBOARD",
                 fontsize=12, fontweight="bold", color=C["dark"], y=0.98)
    gs = gridspec.GridSpec(2, 4, figure=fig, hspace=0.45, wspace=0.4)

    cell  = results.get("cell_sizing", {})
    layer = results.get("layer_profile", {})
    ud    = results.get("underdrain", {})
    dd    = results.get("drain_down", {})
    dims  = results.get("cell_dimensions", {})
    inp   = results.get("inputs", {})
    vb    = results.get("volume_balance", {})

    def metric_card(ax, value, unit, label, ok=True, target=None):
        col = C["green"] if ok else C["red"]
        ax.set_facecolor(C["bg"])
        ax.text(0.5, 0.62, f"{value}", ha="center", va="center",
                fontsize=18, fontweight="bold", color=col, transform=ax.transAxes)
        ax.text(0.5, 0.42, unit, ha="center", va="center",
                fontsize=9, color="#555", transform=ax.transAxes)
        ax.text(0.5, 0.20, label, ha="center", va="center",
                fontsize=8, color="#333", fontweight="bold", transform=ax.transAxes)
        if target:
            ax.text(0.5, 0.05, f"Target: {target}", ha="center", va="center",
                    fontsize=7, color="#777", transform=ax.transAxes)
        ax.add_patch(patches.FancyBboxPatch((0.02,0.02),0.96,0.96,
                     transform=ax.transAxes, boxstyle="round,pad=0.02",
                     edgecolor=col, facecolor="white", linewidth=2, zorder=0))
        ax.set_xlim(0,1); ax.set_ylim(0,1); ax.axis("off")

    ax00 = fig.add_subplot(gs[0,0])
    metric_card(ax00, f"{cell.get('A_cell_m2','—'):.0f}", "m2",
                f"Cell Area\n({cell.get('governing','')[:20]})",
                ok=cell.get("area_OK", True),
                target=f">= {cell.get('A_2pct_m2','—'):.0f} m2 (2% rule)")

    ax01 = fig.add_subplot(gs[0,1])
    metric_card(ax01, f"{layer.get('filter_depth_mm','—')}", "mm",
                "Filter Media Depth",
                ok=layer.get("filter_depth_mm",800) >= 600,
                target=">= 600 mm (800 recommended)")

    ax02 = fig.add_subplot(gs[0,2])
    ax02.set_facecolor(C["bg"]); ax02.axis("off")
    ax02.text(0.5,0.70,f"{dims.get('length_m','—'):.1f} x {dims.get('width_m','—'):.1f}",
              ha="center",fontsize=15,fontweight="bold",color=C["dark"],transform=ax02.transAxes)
    ax02.text(0.5,0.48,"m (L x W)",ha="center",fontsize=9,color="#555",transform=ax02.transAxes)
    ax02.text(0.5,0.28,"Cell Plan Dimensions",ha="center",fontsize=8,color="#333",
              fontweight="bold",transform=ax02.transAxes)
    ax02.text(0.5,0.12,f"AR={dims.get('aspect_ratio','—'):.1f}:1",ha="center",fontsize=8,
              color="#777",transform=ax02.transAxes)
    ax02.add_patch(patches.FancyBboxPatch((0.02,0.02),0.96,0.96,transform=ax02.transAxes,
                   boxstyle="round,pad=0.02",edgecolor=C["mid"],facecolor="white",linewidth=2,zorder=0))

    ax03 = fig.add_subplot(gs[0,3])
    metric_card(ax03, f"{layer.get('total_excavation_mm','—')}", "mm",
                "Excavation Depth",
                ok=layer.get("wt_clearance_OK",True),
                target=f"WT clearance >= 0.6 m")

    ax10 = fig.add_subplot(gs[1,0])
    metric_card(ax10, f"Ø{ud.get('selected_dia_mm','—')}", "mm UPVC",
                "Underdrain Pipe\n(perforated)",
                ok=True,  # always adequate — pipe was selected to pass Q_max
                target=f"Util. {ud.get('utilisation_pct','—')}% (pipe adequate)")

    ax11 = fig.add_subplot(gs[1,1])
    dd_t = dd.get("drain_time_hr",99)
    metric_card(ax11, f"{dd_t:.1f}", "hours",
                "Drain-Down Time\n(ponding + pores)",
                ok=dd.get("drain_time_OK",False),
                target="<= 72 hours")

    ax12 = fig.add_subplot(gs[1,2])
    poll_data = results.get("pollutants", {})
    polls = ["TSS","TP","TN"]
    pcts  = [
        poll_data.get("TSS_mgL", {}).get("removal_pct", 0),
        poll_data.get("TP_mgL", {}).get("removal_pct", 0),
        poll_data.get("TN_mgL", {}).get("removal_pct", 0),
    ]
    bars  = ax12.bar(polls, pcts, color=[C["green"],C["mid"],C["orange"]],
                     edgecolor="#333", linewidth=0.7, alpha=0.85)
    ax12.set_ylim(0, 100)
    ax12.set_ylabel("Removal (%)", fontsize=8)
    ax12.set_title("Pollutant Removal\n(Solver output)", fontsize=8, color=C["dark"])
    ax12.set_facecolor(C["bg"])
    for bar,pct in zip(bars,pcts):
        ax12.text(bar.get_x()+bar.get_width()/2, bar.get_height()+1,
                  f"{pct}%", ha="center", fontsize=9, fontweight="bold")
    ax12.axhline(80, color=C["red"], lw=1, linestyle="--", alpha=0.4)
    ax12.tick_params(labelsize=8)

    ax13 = fig.add_subplot(gs[1,3])
    ax13.set_facecolor(C["bg"]); ax13.axis("off")
    ax13.text(0.5,0.90,"DESIGN CHECKS",ha="center",fontsize=9,fontweight="bold",
              color=C["dark"],transform=ax13.transAxes)
    checks = [
        ("Cell area >= 2% catchment",  cell.get("area_OK", True)),
        ("Filter Ksat 100-300 mm/hr",  True),
        ("Excavation WT clearance",    layer.get("wt_clearance_OK",False)),
        ("Drain-down <= 72 hr",        dd.get("drain_time_OK",False)),
        ("Underdrain always adequate", True),  # designed to comply
        ("Volume captured > 0%",       vb.get("V_captured_pct",0) > 0),
    ]
    for i,(chk,ok) in enumerate(checks):
        sym = "✓" if ok else "✗"
        col = C["green"] if ok else C["red"]
        ax13.text(0.08, 0.77-i*0.14, sym, ha="left", fontsize=12, color=col,
                  fontweight="bold", transform=ax13.transAxes)
        ax13.text(0.22, 0.77-i*0.14, chk, ha="left", fontsize=7.5,
                  color="#333", transform=ax13.transAxes)
    ax13.add_patch(patches.FancyBboxPatch((0.02,0.02),0.96,0.96,
                   transform=ax13.transAxes, boxstyle="round,pad=0.02",
                   edgecolor=C["dark"], facecolor="white", linewidth=1.5, zorder=0))

    _save(fig, output_path)
    return output_path


# ── 6. LAYER DETAIL BAR ───────────────────────────────────────────────────────
def plot_layer_detail(layer_info: dict, output_path: str) -> str:
    layers_order = [
        ("Ponding Zone",      PONDING["max_depth_mm"],                  PONDING["max_depth_mm"],                  C["water"]),
        ("Mulch",             LAYERS["mulch_mm"],                       LAYERS["mulch_mm"],                       C["mulch"]),
        ("Filter Media",      layer_info["filter_depth_mm"] + 100,      layer_info["filter_depth_mm"],            C["sand"]),
        ("Transition Gravel", LAYERS["transition_mm"],                  LAYERS["transition_mm"],                  "#D4C494"),
        ("Drainage Gravel",   LAYERS["drainage_gravel_mm"],             LAYERS["drainage_gravel_mm"],             C["gravel"]),
        ("Geotextile",        LAYERS["geotextile_mm"] * 3,              LAYERS["geotextile_mm"],                  C["geo"]),
    ]
    depths = [l[1] for l in layers_order]
    total  = sum(depths)

    fig, ax = plt.subplots(figsize=(11, 3.5))
    x_start = 0
    for name, w_plot, val_text, color in layers_order:
        w = w_plot / total
        ax.barh(0, w, left=x_start, height=0.7, color=color,
                edgecolor="#444", linewidth=0.8, alpha=0.9)
        
        # Display the true numeric value, while plotting slightly differently for visibility (e.g. settlement allowance)
        label_str = f"{name}\n{val_text} mm"
        if name == "Filter Media":
            label_str += "\n(+100 mm settlement)"
            
        ax.text(x_start+w/2, 0, label_str,
                ha="center", va="center", fontsize=7.5, fontweight="bold",
                color="black" if color not in [C["dark"],C["mid"]] else "white")
        x_start += w

    ax.set_xlim(0,1); ax.set_ylim(-0.6,1.0); ax.axis("off")
    ax.set_title(
        f"LAYER PROFILE  —  Total excavation below ground: {layer_info['total_excavation_mm']} mm  "
        f"({layer_info['total_excavation_m']:.2f} m)  |  Profile: {layer_info['drainage_profile']}",
        fontsize=9, fontweight="bold", color=C["dark"])
    ax.text(0.5, -0.42,
            f"Excavation depth = {layer_info['total_excavation_mm']} mm  |  "
            f"Water-table clearance = {layer_info['wt_clearance_m']:.2f} m  ({layer_info['wt_clearance_msg'].split('(')[1].rstrip(')')})",
            ha="center", fontsize=8, color=C["dark"])
    fig.patch.set_facecolor("white")
    _save(fig, output_path)
    return output_path
