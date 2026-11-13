"""Powerwall Grid Scheduler: a small web app that takes a Powerwall 2 off-grid and
back on-grid on a weekly schedule, with a battery safety cutoff.

Run on an always-on computer on the same network as your Powerwall gateway.
"""

import json
import os
import threading
import uuid
import inspect
from datetime import datetime
from functools import wraps
from pathlib import Path
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, redirect, render_template, request, url_for

from powerwall_client import PowerwallError, make_client

load_dotenv()

TZ = ZoneInfo(os.environ.get("TIMEZONE", "America/Los_Angeles"))
MIN_SOC = float(os.environ.get("MIN_BATTERY_PERCENT", "20"))  # reconnect at/below this
START_MARGIN = float(os.environ.get("START_MARGIN_PERCENT", "5"))  # need MIN_SOC + this to go off-grid
CHECK_SECONDS = int(os.environ.get("SAFETY_CHECK_SECONDS", "60"))
APP_USER = os.environ.get("APP_USERNAME", "admin")
APP_PASS = os.environ.get("APP_PASSWORD", "")
POWERWALL_HOST = os.environ.get("POWERWALL_HOST", "192.168.86.249")

DATA_DIR = Path(os.environ.get("DATA_DIR", Path(__file__).parent / "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
SCHEDULES_FILE = DATA_DIR / "schedules.json"
LOG_FILE = DATA_DIR / "log.json"

DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
DAY_LABELS = {"mon": "Mon", "tue": "Tue", "wed": "Wed", "thu": "Thu", "fri": "Fri", "sat": "Sat", "sun": "Sun"}

app = Flask(__name__)
powerwall = make_client()
scheduler = BackgroundScheduler(timezone=TZ)
file_lock = threading.Lock()


# ---------- storage ----------

def _read(path, default):
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def _write(path, data):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)


def load_schedules():
    with file_lock:
        return _read(SCHEDULES_FILE, [])


def save_schedules(items):
    with file_lock:
        _write(SCHEDULES_FILE, items)


def log(event, detail=""):
    entry = {"time": datetime.now(TZ).strftime("%Y-%m-%d %H:%M:%S"), "event": event, "detail": detail}
    print(f"[{entry['time']}] {event} {detail}", flush=True)
    with file_lock:
        entries = _read(LOG_FILE, [])
        entries.insert(0, entry)
        _write(LOG_FILE, entries[:300])


def read_log():
    with file_lock:
        return _read(LOG_FILE, [])


# ---------- actions ----------

def is_islanded(status):
    return status["grid"] in ("ISLANDED", "ISLANDED_READY", "TRANSITION_TO_ISLAND")


def take_off_grid(reason):
    try:
        status = powerwall.status()
    except PowerwallError as e:
        log("Off-grid skipped", f"{reason}: {e}")
        return False, str(e)
    if is_islanded(status):
        log("Off-grid skipped", f"{reason}: already off-grid")
        return True, "Already off-grid"
    needed = MIN_SOC + START_MARGIN
    if status["charge"] < needed:
        msg = f"battery {status['charge']}% is below {needed:g}% needed to start"
        log("Off-grid skipped", f"{reason}: {msg}")
        return False, msg.capitalize()
    try:
        powerwall.go_off_grid()
    except PowerwallError as e:
        log("Off-grid FAILED", f"{reason}: {e}")
        return False, str(e)
    log("Went off-grid", f"{reason} (battery {status['charge']}%)")
    return True, "Taking the house off-grid"


def bring_on_grid(reason):
    try:
        powerwall.go_on_grid()
    except PowerwallError as e:
        log("On-grid FAILED", f"{reason}: {e}")
        return False, str(e)
    log("Back on-grid", reason)
    return True, "Reconnecting to the grid"


def safety_check():
    try:
        status = powerwall.status()
    except PowerwallError as e:
        log("Safety check error", str(e))
        return
    if is_islanded(status) and status["charge"] <= MIN_SOC:
        bring_on_grid(f"Safety cutoff: battery at {status['charge']}% (limit {MIN_SOC:g}%)")


# ---------- scheduling ----------

def shift_days(days, by=1):
    return [DAYS[(DAYS.index(d) + by) % 7] for d in days]


def register_jobs():
    for job in scheduler.get_jobs():
        if job.id.startswith("sched-"):
            job.remove()
    for s in load_schedules():
        if not s.get("enabled", True) or not s.get("days"):
            continue
        off_h, off_m = map(int, s["off_time"].split(":"))
        on_h, on_m = map(int, s["on_time"].split(":"))
        overnight = (on_h, on_m) <= (off_h, off_m)
        on_days = shift_days(s["days"]) if overnight else s["days"]
        scheduler.add_job(
            take_off_grid, CronTrigger(day_of_week=",".join(s["days"]), hour=off_h, minute=off_m, timezone=TZ),
            args=[f"Schedule '{s['name']}'"], id=f"sched-{s['id']}-off", misfire_grace_time=300,
        )
        scheduler.add_job(
            bring_on_grid, CronTrigger(day_of_week=",".join(on_days), hour=on_h, minute=on_m, timezone=TZ),
            args=[f"Schedule '{s['name']}' ended"], id=f"sched-{s['id']}-on", misfire_grace_time=3600,
        )


def next_runs():
    runs = []
    for job in scheduler.get_jobs():
        if job.id.startswith("sched-") and job.next_run_time:
            runs.append({"when": job.next_run_time, "action": "Off-grid" if job.id.endswith("-off") else "On-grid",
                         "label": job.args[0]})
    runs.sort(key=lambda r: r["when"])
    return [{**r, "when": r["when"].strftime("%a %b %-d, %-I:%M %p")} for r in runs[:6]]


# ---------- web ----------

def requires_auth(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if APP_PASS:
            auth = request.authorization
            if not auth or auth.username != APP_USER or auth.password != APP_PASS:
                return Response("Login required", 401, {"WWW-Authenticate": 'Basic realm="Powerwall Scheduler"'})
        return f(*args, **kwargs)
    return wrapper


def fmt_time(t):
    return datetime.strptime(t, "%H:%M").strftime("%-I:%M %p")


@app.route("/")
@requires_auth
def index():
    schedules = load_schedules()
    for s in schedules:
        s["days_label"] = ", ".join(DAY_LABELS[d] for d in DAYS if d in s["days"])
        s["off_label"], s["on_label"] = fmt_time(s["off_time"]), fmt_time(s["on_time"])
        s["overnight"] = s["on_time"] <= s["off_time"]
    return render_template(
        "index.html", schedules=schedules, log=read_log()[:40], upcoming=next_runs(),
        days=DAYS, day_labels=DAY_LABELS, min_soc=MIN_SOC, start_soc=MIN_SOC + START_MARGIN,
        demo=os.environ.get("POWERWALL_DEMO", "") in ("1", "true", "yes"), message=request.args.get("msg"),
    )


@app.route("/api/status")
@requires_auth
def api_status():
    try:
        print("HERE", vars(powerwall), inspect.getsourcefile(type(powerwall)))
        return jsonify({"ok": True, **powerwall.status()})
    except PowerwallError as e:
        return jsonify({"ok": False, "error": str(e)}), 502


@app.post("/action/off")
@requires_auth
def action_off():
    _, msg = take_off_grid("Manual (web)")
    return redirect(url_for("index", msg=msg))


@app.post("/action/on")
@requires_auth
def action_on():
    _, msg = bring_on_grid("Manual (web)")
    return redirect(url_for("index", msg=msg))


@app.post("/schedules")
@requires_auth
def add_schedule():
    f = request.form
    days = [d for d in DAYS if f.get(d)]
    off_t, on_t = f.get("off_time", ""), f.get("on_time", "")
    if not days or not off_t or not on_t or off_t == on_t:
        return redirect(url_for("index", msg="Pick at least one day and two different times."))
    items = load_schedules()
    items.append({"id": uuid.uuid4().hex[:8], "name": f.get("name", "").strip() or "Schedule",
                  "days": days, "off_time": off_t, "on_time": on_t, "enabled": True})
    save_schedules(items)
    register_jobs()
    log("Schedule added", items[-1]["name"])
    return redirect(url_for("index", msg="Schedule saved."))


@app.post("/schedules/<sid>/toggle")
@requires_auth
def toggle_schedule(sid):
    items = load_schedules()
    for s in items:
        if s["id"] == sid:
            s["enabled"] = not s.get("enabled", True)
            log("Schedule " + ("enabled" if s["enabled"] else "paused"), s["name"])
    save_schedules(items)
    register_jobs()
    return redirect(url_for("index"))


@app.post("/schedules/<sid>/delete")
@requires_auth
def delete_schedule(sid):
    items = load_schedules()
    removed = [s for s in items if s["id"] == sid]
    save_schedules([s for s in items if s["id"] != sid])
    register_jobs()
    if removed:
        log("Schedule deleted", removed[0]["name"])
    return redirect(url_for("index", msg="Schedule deleted."))


def start():
    register_jobs()
    scheduler.add_job(safety_check, "interval", seconds=CHECK_SECONDS, id="safety", max_instances=1, coalesce=True)
    scheduler.start()
    log("Scheduler started", f"safety cutoff {MIN_SOC:g}%, checks every {CHECK_SECONDS}s")


if __name__ == "__main__":
    if not APP_PASS:
        print("WARNING: APP_PASSWORD is not set; anyone on your network can open this page.", flush=True)
    start()
    print("POWERWALL_HOST=", os.environ.get("POWERWALL_HOST"))
    app.run(host=os.environ.get("BIND_HOST", "0.0.0.0"), port=int(os.environ.get("PORT", "8080")))
