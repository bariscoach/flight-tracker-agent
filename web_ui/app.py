"""
web_ui/app.py
Local settings UI for flight-tracker-agent.
Run with: python3.11 web_ui/app.py
Then open: http://localhost:5050
"""

import json
import os
import subprocess
import threading
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, url_for

app = Flask(__name__)
app.secret_key = os.urandom(24)

PROJECT_ROOT = Path(__file__).parent.parent
CONFIG_FILE = PROJECT_ROOT / "user_config.json"
LOG_FILE = PROJECT_ROOT / "logs" / "tracker.log"
PYTHON = "/usr/local/bin/python3.11"

# ── Defaults shown on first load ──────────────────────────────────────────────

DEFAULTS = {
    "ANTHROPIC_API_KEY": "",
    "GMAIL_USER": "",
    "GMAIL_APP_PASSWORD": "",
    "FIRESTORE_PROJECT": "flight-tracker",
    "FIRESTORE_KEY_PATH": "firestore-key.json",
    "ORIGINS": ["YYZ"],
    "DESTINATIONS": ["IST", "ESB", "SAW"],
    "OUTBOUND_DATE": "2026-07-18",
    "RETURN_DATE": "2026-08-22",
    "OUTBOUND_FLEXIBILITY_DAYS": 2,
    "RETURN_FLEXIBILITY_DAYS": 2,
    "ADULTS": 1,
    "CHILDREN": 1,
    "CHILD_AGE": 7,
    "RECIPIENTS": [],
    "MAX_TRAVEL_HOURS": 20,
    "ACTIVE_HUBS_COUNT": 3,
}


def load_config() -> dict:
    if CONFIG_FILE.exists():
        saved = json.loads(CONFIG_FILE.read_text())
        return {**DEFAULTS, **saved}
    return dict(DEFAULTS)


def save_config(data: dict) -> None:
    CONFIG_FILE.write_text(json.dumps(data, indent=2))


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def index():
    cfg = load_config()
    # Convert lists to comma-separated strings for the form
    cfg["_origins_str"] = ", ".join(cfg.get("ORIGINS", []))
    cfg["_destinations_str"] = ", ".join(cfg.get("DESTINATIONS", []))
    cfg["_recipients_str"] = ", ".join(cfg.get("RECIPIENTS", []))
    return render_template("index.html", cfg=cfg)


@app.route("/save", methods=["POST"])
def save():
    def _list(field: str) -> list[str]:
        return [x.strip() for x in request.form.get(field, "").split(",") if x.strip()]

    def _int(field: str, default: int) -> int:
        try:
            return int(request.form.get(field, default))
        except ValueError:
            return default

    data = {
        "ANTHROPIC_API_KEY": request.form.get("anthropic_api_key", "").strip(),
        "GMAIL_USER": request.form.get("gmail_user", "").strip(),
        "GMAIL_APP_PASSWORD": request.form.get("gmail_app_password", "").strip(),
        "FIRESTORE_PROJECT": request.form.get("firestore_project", "flight-tracker").strip(),
        "FIRESTORE_KEY_PATH": request.form.get("firestore_key_path", "firestore-key.json").strip(),
        "ORIGINS": _list("origins"),
        "DESTINATIONS": _list("destinations"),
        "OUTBOUND_DATE": request.form.get("outbound_date", "").strip(),
        "RETURN_DATE": request.form.get("return_date", "").strip(),
        "OUTBOUND_FLEXIBILITY_DAYS": _int("outbound_flex", 2),
        "RETURN_FLEXIBILITY_DAYS": _int("return_flex", 2),
        "ADULTS": _int("adults", 1),
        "CHILDREN": _int("children", 0),
        "CHILD_AGE": _int("child_age", 7),
        "RECIPIENTS": _list("recipients"),
        "MAX_TRAVEL_HOURS": _int("max_travel_hours", 20),
        "ACTIVE_HUBS_COUNT": _int("active_hubs_count", 3),
    }
    save_config(data)
    flash("✅ Settings saved!", "success")
    return redirect(url_for("index"))


@app.route("/run", methods=["POST"])
def run_now():
    def _run():
        env = os.environ.copy()
        cfg = load_config()
        # Inject API keys into subprocess environment
        for key in ("ANTHROPIC_API_KEY", "GMAIL_USER", "GMAIL_APP_PASSWORD",
                    "FIRESTORE_PROJECT", "FIRESTORE_KEY_PATH"):
            if cfg.get(key):
                env[key] = cfg[key]
        subprocess.run(
            [PYTHON, str(PROJECT_ROOT / "main.py")],
            cwd=str(PROJECT_ROOT),
            env=env,
        )
    threading.Thread(target=_run, daemon=True).start()
    flash("🚀 Tracker started in background. Check logs in a minute.", "info")
    return redirect(url_for("index"))


@app.route("/logs")
def logs():
    if LOG_FILE.exists():
        lines = LOG_FILE.read_text(errors="replace").splitlines()[-150:]
        return "\n".join(lines), 200, {"Content-Type": "text/plain; charset=utf-8"}
    return "No logs yet.", 200, {"Content-Type": "text/plain"}


if __name__ == "__main__":
    print("\n✈️  Flight Tracker Settings")
    print("   Open http://localhost:5050 in your browser\n")
    app.run(host="127.0.0.1", port=5050, debug=False)
