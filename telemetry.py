"""Anonymous install and daily check-in.

Docker containers download two one-byte files from the public usage-stats
release. GitHub's download counters are the install statistics. No household
data is included. Set CHORESREWARDS_TELEMETRY=off to disable.
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone

import usage_stats

_DISABLED = {"0", "off", "false", "no", "disable", "disabled"}
_CHECKIN_INTERVAL = 20 * 60 * 60
_START_DELAY = 20
_RETRY = 60 * 60


def env_disabled() -> bool:
    raw = os.environ.get("CHORESREWARDS_TELEMETRY", "on").strip().lower()
    return raw in _DISABLED


def in_docker() -> bool:
    return os.path.exists("/.dockerenv")


def _state_path(app) -> str:
    return os.path.join(app.instance_path, "telemetry.json")


def _lock_path(app) -> str:
    return os.path.join(app.instance_path, "telemetry.lock")


def _read_state(path) -> dict:
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_state(path, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    temporary = path + ".tmp"
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(data, handle)
    os.replace(temporary, path)


def household_status(app) -> dict:
    state = _read_state(_state_path(app))
    return {
        "env_disabled": env_disabled(),
        "in_docker": in_docker(),
        "install_reported": bool(state.get("install_reported")),
        "last_checkin": state.get("last_checkin"),
    }


def _opted_out(app) -> bool:
    if env_disabled():
        return True
    try:
        with app.app_context():
            from extensions import db
            from models import AppSetting
            opted = AppSetting.get("telemetry_opt_out", "0") == "1"
            db.session.remove()
            return opted
    except Exception:
        return False


def _acquire_lock(path) -> bool:
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        try:
            if time.time() - os.path.getmtime(path) > 300:
                os.remove(path)
                return _acquire_lock(path)
        except OSError:
            return False
        return False
    try:
        os.write(fd, str(os.getpid()).encode())
    finally:
        os.close(fd)
    return True


def _release_lock(path) -> None:
    try:
        os.remove(path)
    except OSError:
        pass


def _download(asset: str):
    """Return True on success, None if the counter is not published yet."""
    url = usage_stats.counter_download_url(asset)
    request = urllib.request.Request(url, headers={"User-Agent": usage_stats.USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            response.read(64)
            return 200 <= getattr(response, "status", 200) < 300
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        return False
    except Exception:
        return False


def _parse_time(value):
    if not value:
        return None
    try:
        return datetime_from_iso(value)
    except ValueError:
        return None


def datetime_from_iso(value: str):
    text = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def _tick(app) -> int:
    if not in_docker() or _opted_out(app):
        return _RETRY
    lock = _lock_path(app)
    if not _acquire_lock(lock):
        return 60
    try:
        path = _state_path(app)
        state = _read_state(path)
        missing = False
        failed = False
        if not state.get("install_reported"):
            result = _download(usage_stats.INSTALL_ASSET)
            if result is True:
                state["install_reported"] = True
                print("[telemetry] recorded a new install")
            elif result is None:
                missing = True
            else:
                failed = True
        last = _parse_time(state.get("last_checkin"))
        due = last is None or (usage_stats._now() - last).total_seconds() >= _CHECKIN_INTERVAL
        if due:
            result = _download(usage_stats.CHECKIN_ASSET)
            if result is True:
                state["last_checkin"] = usage_stats._now().strftime("%Y-%m-%dT%H:%M:%SZ")
                print("[telemetry] recorded a daily check-in")
            elif result is None:
                missing = True
            else:
                failed = True
        if state.get("install_reported") or state.get("last_checkin"):
            _write_state(path, state)
        if missing and not getattr(_tick, "logged_missing", False):
            print("[telemetry] usage counters are not published yet; will retry")
            _tick.logged_missing = True
        if missing or failed:
            return _RETRY
        return _CHECKIN_INTERVAL
    finally:
        _release_lock(lock)


def _loop(app) -> None:
    time.sleep(_START_DELAY)
    while True:
        try:
            wait = _tick(app)
        except Exception as exc:
            print(f"[telemetry] {exc}")
            wait = _RETRY
        time.sleep(max(30, wait))


def start(app) -> None:
    if not in_docker():
        return
    thread = threading.Thread(target=_loop, args=(app,), name="usage-telemetry", daemon=True)
    thread.start()
