"""Public usage figures for ChoresRewards.

Image pulls come from the GitHub Container Registry package page.
Installs and daily check-ins come from download counters on a tiny
pre-release (see ``ensure_counter_release``). Households do not send
names, chores, or server details. They only download those files.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO = "matda59/ChoresRewards"
IMAGE = "ghcr.io/matda59/choresrewards"
PACKAGE_PAGE = f"https://github.com/{REPO}/pkgs/container/choresrewards"
RELEASE_TAG = "usage-stats"
INSTALL_ASSET = "install"
CHECKIN_ASSET = "checkin"
CACHE_SECONDS = 15 * 60
USER_AGENT = "ChoresRewards-Usage/1 (+https://github.com/matda59/ChoresRewards)"

_TOTAL_RE = re.compile(
    r"Total downloads</span>\s*<h3[^>]*\stitle=\"(\d+)\"",
    re.IGNORECASE,
)
_DAY_RE = re.compile(
    r'data-merge-count="(\d+)"\s+data-date="(\d{4}-\d{2}-\d{2})"',
)


def counter_download_url(asset: str) -> str:
    return f"https://github.com/{REPO}/releases/download/{RELEASE_TAG}/{asset}"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _today() -> str:
    return _now().date().isoformat()


def http_request(url, *, token=None, timeout=20, data=None, method=None, content_type=None, accept=None):
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": accept or "application/vnd.github+json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
        headers["X-GitHub-Api-Version"] = "2022-11-28"
    if content_type:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read() if exc.fp else b""
    except Exception:
        return 0, b""


def parse_package_html(html: str) -> dict:
    total_match = _TOTAL_RE.search(html or "")
    daily = [
        {"date": day, "count": int(count)}
        for count, day in _DAY_RE.findall(html or "")
    ]
    daily.sort(key=lambda row: row["date"])
    return {
        "total": int(total_match.group(1)) if total_match else None,
        "daily": daily,
    }


def fetch_package_stats() -> dict:
    status, body = http_request(PACKAGE_PAGE, accept="text/html", timeout=25)
    if status != 200:
        return {"total": None, "daily": []}
    return parse_package_html(body.decode("utf-8", "replace"))


def fetch_repo_stats() -> dict:
    status, body = http_request(f"https://api.github.com/repos/{REPO}", timeout=20)
    if status != 200:
        return {}
    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        return {}
    return {
        "stars": payload.get("stargazers_count"),
        "forks": payload.get("forks_count"),
    }


def _traffic_payload(url, token, series_key) -> dict:
    status, body = http_request(url, token=token, timeout=20)
    if status != 200:
        return {}
    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        return {}
    rows = []
    for item in payload.get(series_key) or []:
        stamp = str(item.get("timestamp") or "")
        day = stamp[:10]
        if not day:
            continue
        rows.append({
            "date": day,
            "count": int(item.get("count") or 0),
            "uniques": int(item.get("uniques") or 0),
        })
    return {
        "rows": rows,
        "count": payload.get("count"),
        "uniques": payload.get("uniques"),
    }


def fetch_traffic(token: str) -> dict:
    if not token:
        return {}
    clones = _traffic_payload(f"https://api.github.com/repos/{REPO}/traffic/clones", token, "clones")
    views = _traffic_payload(f"https://api.github.com/repos/{REPO}/traffic/views", token, "views")
    return {
        "clones": clones.get("rows") or [],
        "views": views.get("rows") or [],
        "clone_count_14": clones.get("count"),
        "clone_uniques_14": clones.get("uniques"),
        "view_count_14": views.get("count"),
        "view_uniques_14": views.get("uniques"),
    }


def fetch_release_counts(token=None) -> dict | None:
    status, body = http_request(
        f"https://api.github.com/repos/{REPO}/releases/tags/{RELEASE_TAG}",
        token=token,
        timeout=20,
    )
    if status == 404:
        return None
    if status != 200:
        return None
    try:
        payload = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        return None
    counts = {INSTALL_ASSET: 0, CHECKIN_ASSET: 0}
    found = set()
    for asset in payload.get("assets") or []:
        name = asset.get("name")
        if name in counts:
            counts[name] = int(asset.get("download_count") or 0)
            found.add(name)
    if not found:
        return {"installs": 0, "checkins": 0, "ready": False}
    return {
        "installs": counts[INSTALL_ASSET],
        "checkins": counts[CHECKIN_ASSET],
        "ready": INSTALL_ASSET in found and CHECKIN_ASSET in found,
    }


def _upload_asset(upload_url: str, name: str, token: str) -> None:
    url = upload_url.split("{", 1)[0] + f"?name={name}"
    status, body = http_request(
        url,
        token=token,
        data=b"\n",
        method="POST",
        content_type="application/octet-stream",
        timeout=30,
    )
    if status not in (201, 422):
        detail = body.decode("utf-8", "replace")[:200]
        print(f"[usage] could not upload {name}: HTTP {status} {detail}")


def ensure_counter_release(token: str) -> None:
    """Create the pre-release that holds the install and check-in counters."""
    if not token:
        return
    status, body = http_request(
        f"https://api.github.com/repos/{REPO}/releases/tags/{RELEASE_TAG}",
        token=token,
    )
    if status == 404:
        payload = json.dumps({
            "tag_name": RELEASE_TAG,
            "name": "Usage counters",
            "body": (
                "Not a software release. These one-byte files count anonymous "
                "ChoresRewards installs and daily check-ins. Downloading them "
                "changes the public counters, so leave them alone."
            ),
            "prerelease": True,
            "make_latest": "false",
        }).encode()
        status, body = http_request(
            f"https://api.github.com/repos/{REPO}/releases",
            token=token,
            data=payload,
            method="POST",
            content_type="application/json",
        )
        if status not in (201, 422):
            detail = body.decode("utf-8", "replace")[:300]
            print(f"[usage] could not create counter release: HTTP {status} {detail}")
            return
        if status == 422 and b"make_latest" in body:
            payload = json.dumps({
                "tag_name": RELEASE_TAG,
                "name": "Usage counters",
                "body": (
                    "Not a software release. These one-byte files count anonymous "
                    "ChoresRewards installs and daily check-ins. Downloading them "
                    "changes the public counters, so leave them alone."
                ),
                "prerelease": True,
            }).encode()
            status, body = http_request(
                f"https://api.github.com/repos/{REPO}/releases",
                token=token,
                data=payload,
                method="POST",
                content_type="application/json",
            )
        if status == 422:
            status, body = http_request(
                f"https://api.github.com/repos/{REPO}/releases/tags/{RELEASE_TAG}",
                token=token,
            )
            if status != 200:
                return
    elif status != 200:
        print(f"[usage] counter release lookup failed: HTTP {status}")
        return

    try:
        release = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        return
    names = {asset.get("name") for asset in release.get("assets") or []}
    upload_url = release.get("upload_url") or ""
    if not upload_url:
        return
    for name in (INSTALL_ASSET, CHECKIN_ASSET):
        if name not in names:
            _upload_asset(upload_url, name, token)


def _merge_dated(old_rows, new_rows) -> list:
    merged = {}
    for row in old_rows or []:
        if row.get("date"):
            merged[row["date"]] = dict(row)
    for row in new_rows or []:
        if not row.get("date"):
            continue
        current = merged.get(row["date"], {})
        current.update(row)
        merged[row["date"]] = current
    return [merged[key] for key in sorted(merged)]


def empty_snapshot() -> dict:
    return {
        "updated": None,
        "image": IMAGE,
        "repo": REPO,
        "pulls": {"total": None, "daily": []},
        "installs": {"total": None, "checkins": None, "history": []},
        "github": {
            "stars": None,
            "forks": None,
            "clones": [],
            "views": [],
            "clone_count_14": None,
            "clone_uniques_14": None,
            "view_count_14": None,
            "view_uniques_14": None,
        },
    }


def load_json(path) -> dict:
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def save_json(path, data) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, destination)


def merge_snapshot(existing: dict, incoming: dict) -> dict:
    base = empty_snapshot()
    previous = existing or {}
    pulls = previous.get("pulls") or {}
    installs = previous.get("installs") or {}
    github = previous.get("github") or {}
    new_pulls = incoming.get("pulls") or {}
    new_installs = incoming.get("installs") or {}
    new_github = incoming.get("github") or {}

    if new_pulls.get("total") is not None:
        base["pulls"]["total"] = int(new_pulls["total"])
    elif pulls.get("total") is not None:
        base["pulls"]["total"] = pulls.get("total")
    base["pulls"]["daily"] = _merge_dated(pulls.get("daily"), new_pulls.get("daily"))

    history = list(installs.get("history") or [])
    if new_installs.get("total") is not None and new_installs.get("checkins") is not None:
        base["installs"]["total"] = int(new_installs["total"])
        base["installs"]["checkins"] = int(new_installs["checkins"])
        history = _merge_dated(history, [{
            "date": incoming.get("date") or _today(),
            "installs": int(new_installs["total"]),
            "checkins": int(new_installs["checkins"]),
        }])
    else:
        base["installs"]["total"] = installs.get("total")
        base["installs"]["checkins"] = installs.get("checkins")
    base["installs"]["history"] = history

    for key in (
        "stars",
        "forks",
        "clone_count_14",
        "clone_uniques_14",
        "view_count_14",
        "view_uniques_14",
    ):
        if new_github.get(key) is not None:
            base["github"][key] = new_github.get(key)
        else:
            base["github"][key] = github.get(key)
    base["github"]["clones"] = _merge_dated(github.get("clones"), new_github.get("clones"))
    base["github"]["views"] = _merge_dated(github.get("views"), new_github.get("views"))
    base["updated"] = _now().strftime("%Y-%m-%dT%H:%M:%SZ")
    return base


def collect(token=None) -> dict:
    package = fetch_package_stats()
    repo = fetch_repo_stats()
    traffic = fetch_traffic(token) if token else {}
    if token:
        ensure_counter_release(token)
    release = fetch_release_counts(token)
    incoming = {
        "date": _today(),
        "pulls": package,
        "github": {**repo, **traffic},
        "installs": {},
    }
    if release and release.get("ready"):
        incoming["installs"] = {
            "total": release["installs"],
            "checkins": release["checkins"],
        }
    return incoming


def write_snapshot(path, token=None) -> dict:
    existing = load_json(path)
    incoming = collect(token)
    if incoming["pulls"].get("total") is None and not existing:
        raise RuntimeError("Could not read image pull counts from GitHub.")
    merged = merge_snapshot(existing, incoming)
    if incoming["pulls"].get("total") is None and not merged["pulls"].get("daily"):
        raise RuntimeError("Could not read image pull counts from GitHub.")
    save_json(path, merged)
    return merged


def fetch_published_snapshot() -> dict:
    status, body = http_request(
        f"https://raw.githubusercontent.com/{REPO}/main/stats/usage.json",
        accept="application/json",
        timeout=20,
    )
    if status != 200:
        return {}
    try:
        data = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _sum_recent(rows, days, field="count") -> int | None:
    if not rows:
        return None
    cutoff = (_now().date() - timedelta(days=days - 1)).isoformat()
    return sum(int(row.get(field) or 0) for row in rows if row.get("date", "") >= cutoff)


def _fill_days(rows, days=30) -> list:
    by_date = {row["date"]: int(row.get("count") or 0) for row in rows or [] if row.get("date")}
    end = _now().date()
    start = end - timedelta(days=days - 1)
    filled = []
    cursor = start
    while cursor <= end:
        key = cursor.isoformat()
        filled.append({"date": key, "count": by_date.get(key, 0)})
        cursor += timedelta(days=1)
    return filled


def _install_deltas(history, live_installs, live_checkins) -> list:
    points = [dict(row) for row in history or [] if row.get("date")]
    today = _today()
    if live_installs is not None and live_checkins is not None:
        if points and points[-1]["date"] == today:
            points[-1] = {"date": today, "installs": live_installs, "checkins": live_checkins}
        else:
            points.append({"date": today, "installs": live_installs, "checkins": live_checkins})
    deltas = []
    previous = None
    for row in points:
        if previous is not None:
            deltas.append({
                "date": row["date"],
                "new_installs": int(row.get("installs") or 0) - int(previous.get("installs") or 0),
                "checkins": int(row.get("checkins") or 0) - int(previous.get("checkins") or 0),
            })
        previous = row
    return deltas


def _chart(rows) -> list:
    peak = max((row["count"] for row in rows), default=0)
    chart = []
    for index, row in enumerate(rows):
        count = row["count"]
        if peak <= 0 or count <= 0:
            height = 0
        else:
            height = max(8, round(count / peak * 100))
        parsed = datetime.strptime(row["date"], "%Y-%m-%d")
        show_label = index == 0 or index == len(rows) - 1 or (index % 10 == 0 and index < len(rows) - 3)
        chart.append({
            "date": row["date"],
            "count": count,
            "height": height,
            "label": f"{parsed.strftime('%b')} {parsed.day}",
            "show_label": show_label,
        })
    return chart


def _fmt(value) -> str | None:
    if value is None:
        return None
    return f"{int(value):,}"


def present(snapshot: dict, *, release: dict | None = None) -> dict:
    snapshot = snapshot or empty_snapshot()
    pulls = snapshot.get("pulls") or {}
    installs = snapshot.get("installs") or {}
    github = snapshot.get("github") or {}
    daily = pulls.get("daily") or []
    chart_rows = _fill_days(daily, 30) if daily else []
    reported_30 = _sum_recent(daily, 30)
    live_installs = installs.get("total")
    live_checkins = installs.get("checkins")
    if release and release.get("ready"):
        live_installs = release["installs"]
        live_checkins = release["checkins"]
    deltas = _install_deltas(installs.get("history"), live_installs, live_checkins)
    latest = deltas[-1] if deltas else None
    clones_14 = github.get("clone_count_14")
    views_14 = github.get("view_count_14")
    clone_uniques = github.get("clone_uniques_14")
    view_uniques = github.get("view_uniques_14")
    return {
        "updated": snapshot.get("updated"),
        "pulls_total": _fmt(pulls.get("total")),
        "pulls_30": _fmt(reported_30),
        "chart": _chart(chart_rows),
        "installs_total": _fmt(live_installs),
        "checkins_total": _fmt(live_checkins),
        "installs_ready": live_installs is not None,
        "latest_new_installs": _fmt(latest["new_installs"]) if latest else None,
        "latest_checkins": _fmt(latest["checkins"]) if latest else None,
        "latest_date": latest["date"] if latest else None,
        "recent": list(reversed(deltas[-14:])),
        "stars": _fmt(github.get("stars")),
        "forks": _fmt(github.get("forks")),
        "clones_14": _fmt(clones_14),
        "clone_uniques_14": _fmt(clone_uniques),
        "views_14": _fmt(views_14),
        "view_uniques_14": _fmt(view_uniques),
        "package_url": PACKAGE_PAGE,
        "repo_url": f"https://github.com/{REPO}",
    }


def load_dashboard(cache_path, bundled_path, *, force=False) -> dict:
    cache = {} if force else load_json(cache_path)
    fetched_at = cache.get("fetched_at") or 0
    if cache.get("view") and (_now().timestamp() - fetched_at) < CACHE_SECONDS:
        return cache["view"]

    with ThreadPoolExecutor(max_workers=4) as pool:
        package_f = pool.submit(fetch_package_stats)
        repo_f = pool.submit(fetch_repo_stats)
        release_f = pool.submit(fetch_release_counts)
        published_f = pool.submit(fetch_published_snapshot)
        package = package_f.result()
        repo = repo_f.result()
        release = release_f.result()
        published = published_f.result()

    if not published:
        published = load_json(bundled_path)
    incoming = {
        "date": _today(),
        "pulls": package,
        "github": repo,
        "installs": {},
    }
    if release and release.get("ready"):
        incoming["installs"] = {"total": release["installs"], "checkins": release["checkins"]}
    snapshot = merge_snapshot(published, incoming)
    view = present(snapshot, release=release)
    published_total = (published.get("pulls") or {}).get("total") if published else None
    if package.get("total") is None and published_total is None:
        view["error"] = "Image pull counts could not be read from GitHub."
    elif package.get("total") is None:
        view["error"] = "Showing the last saved snapshot. GitHub could not be reached just now."
    else:
        view["error"] = None
    view["from_cache"] = False
    try:
        save_json(cache_path, {"fetched_at": _now().timestamp(), "view": view})
    except OSError:
        pass
    return view
