"""
app.py — Flask web application for the Bioretention Cell Design Tool.
Run with:  python app.py
Then open: http://localhost:5000
"""

import os, sys, json, threading, traceback
from flask import (Flask, render_template, request, jsonify,
                   send_file, send_from_directory)

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB upload limit

# Store last run result per session (simple in-process dict for single-user use)
_last_result: dict = {}

DIVS = ["Dhaka","Rajshahi","Khulna","Sylhet","Chattogram","Barishal","Mymensingh","Rangpur"]
RPS  = ["2yr","10yr","25yr"]
PROFILES = [
    ("Type1_SaturatedZone", "Type 1 — Saturated Zone"),
    ("Type2_Sealed",        "Type 2 — Sealed / Lined"),
    ("Type3_Conventional",  "Type 3 — Conventional (Unlined)"),
    ("Type4_Pipeless",      "Type 4 — Pipeless"),
]

# ── Startup diagnostics (visible in Render logs on every boot) ────────────────
print("=" * 60)
print("  BIORETENTION APP STARTUP")
print(f"  ROOT        : {ROOT}")
print(f"  templates/  : {os.path.exists(os.path.join(ROOT, 'templates'))}")
print(f"  data/       : {os.path.exists(os.path.join(ROOT, 'data'))}")
print(f"  src/        : {os.path.exists(os.path.join(ROOT, 'src'))}")
_data_dir = os.path.join(ROOT, "data")
if os.path.isdir(_data_dir):
    print(f"  data files  : {os.listdir(_data_dir)}")
_src_dir = os.path.join(ROOT, "src")
if os.path.isdir(_src_dir):
    print(f"  src files   : {os.listdir(_src_dir)}")
os.makedirs(os.path.join(ROOT, "outputs", "plots"), exist_ok=True)
print("  outputs/    : created/verified")
print("=" * 60)


# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/health")
def health():
    """Render health-check endpoint — always returns 200 OK."""
    return "OK", 200


@app.route("/")
def index():
    return render_template("index.html",
                           divs=DIVS, rps=RPS, profiles=PROFILES)


@app.route("/run", methods=["POST"])
def run_design():
    global _last_result
    try:
        params = request.get_json(force=True)
        from src.engine import run_design as _engine
        result = _engine(params)
        _last_result = result

        fig_urls = {}
        for key, path in result.get("figures", {}).items():
            if path and os.path.exists(str(path)):
                fig_urls[key] = "/figures/" + os.path.basename(str(path))

        return jsonify({
            "ok":       True,
            "summary":  result["summary"],
            "warnings": result["warnings"],
            "figures":  fig_urls,
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/figures/<path:filename>")
def serve_figure(filename):
    plots_dir = os.path.join(ROOT, "outputs", "plots")
    return send_from_directory(plots_dir, filename)


@app.route("/download/report")
def download_report():
    path = _last_result.get("report_path")
    if not path or not os.path.exists(path):
        return "No report available — run a design first.", 404
    return send_file(path, as_attachment=True,
                     download_name=os.path.basename(path),
                     mimetype="text/html")


@app.route("/download/calc_basis")
def download_calc_basis():
    path = _last_result.get("calc_basis_path")
    if not path or not os.path.exists(path):
        return "No calculation basis available — run a design first.", 404
    return send_file(path, as_attachment=True,
                     download_name=os.path.basename(path),
                     mimetype="text/html")


@app.errorhandler(500)
def internal_error(e):
    tb = traceback.format_exc()
    print("500 ERROR:\n", tb)
    return f"<pre>500 Internal Server Error\n\n{tb}</pre>", 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  Open  http://localhost:{port}  in your browser\n")
    app.run(host="0.0.0.0", port=port, debug=False)
