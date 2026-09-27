"""Adult-only usage dashboard."""

import os

from flask import Blueprint, current_app, redirect, render_template, request, session, url_for

import telemetry
import usage_stats
from models import AppSetting

usage_bp = Blueprint("usage", __name__)


def _allowed():
    return session.get("adult_mode", False) or session.get("authenticated", False)


@usage_bp.route("/usage", methods=["GET", "POST"])
def usage_stats_page():
    if not _allowed():
        return redirect(url_for("routes.index"))

    if request.method == "POST" and not telemetry.env_disabled():
        enabled = request.form.get("telemetry") == "on"
        AppSetting.set("telemetry_opt_out", "0" if enabled else "1")
        return redirect(url_for("usage.usage_stats_page", saved=1))

    bundled = os.path.join(current_app.root_path, "stats", "usage.json")
    cache = os.path.join(current_app.instance_path, "usage_dashboard_cache.json")
    try:
        view = usage_stats.load_dashboard(
            cache,
            bundled,
            force=request.args.get("refresh") == "1",
        )
    except Exception:
        view = usage_stats.present(usage_stats.load_json(bundled))
        view["error"] = "Usage figures could not be refreshed just now."

    status = telemetry.household_status(current_app)
    opted_out = AppSetting.get("telemetry_opt_out", "0") == "1"
    view["telemetry_on"] = (not status["env_disabled"]) and (not opted_out)
    view["telemetry_forced_off"] = status["env_disabled"]
    view["in_docker"] = status["in_docker"]
    view["install_reported"] = status["install_reported"]
    view["last_checkin"] = status["last_checkin"]
    view["saved"] = request.args.get("saved") == "1"
    return render_template("usage.html", **view)
