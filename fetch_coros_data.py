#!/usr/bin/env python3
"""COROS Team API data fetcher with incremental update support."""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime
from pathlib import Path

import requests

# ──────────────────────────────────────────────
# Configuration – reads from env vars (set by Streamlit secrets on Cloud)
# Falls back to hardcoded defaults for local development
# ──────────────────────────────────────────────
_token = os.environ.get("COROS_ACCESS_TOKEN", "")
CONFIG = {
    "access_token": _token,
    "cookies": {
        "_c_WBKFRo": os.environ.get("COROS_COOKIE_WBKFRO", ""),
        "CPL-coros-token": _token,
        "CPL-coros-region": os.environ.get("COROS_COOKIE_REGION", "2"),
    },
    "user_id": os.environ.get("COROS_USER_ID", ""),
    "base_url": os.environ.get("COROS_BASE_URL", "https://teamcnapi.coros.com"),
    "page_size": 20,
}

DATA_DIR = Path(__file__).parent / "data"
ACTIVITIES_FILE = DATA_DIR / "activities.json"
ANALYSE_FILE = DATA_DIR / "analyse.json"
DASHBOARD_FILE = DATA_DIR / "dashboard.json"
META_FILE = DATA_DIR / "fetch_meta.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


def _headers(with_yf: bool = False) -> dict:
    h = {
        "accept": "application/json, text/plain, */*",
        "accept-language": "zh-CN,zh;q=0.9,en;q=0.8",
        "accesstoken": CONFIG["access_token"],
        "origin": "https://t.coros.com",
        "referer": "https://t.coros.com/",
        "user-agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/145.0.0.0 Safari/537.36"
        ),
    }
    if with_yf:
        h["yfheader"] = json.dumps({"userId": CONFIG["user_id"]})
    return h


def _cookies() -> dict:
    return CONFIG["cookies"]


def _load_json(path: Path) -> dict | list | None:
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _save_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_meta() -> dict:
    meta = _load_json(META_FILE)
    if meta is None:
        meta = {"last_fetch": None, "known_label_ids": [], "latest_happen_day": None}
    return meta


def _save_meta(meta: dict):
    meta["last_fetch"] = datetime.now().isoformat()
    _save_json(META_FILE, meta)


# ──────────────────────────────────────────────
# Activities – paginated, incremental by labelId
# ──────────────────────────────────────────────
def fetch_activities(known_ids: set[str]) -> list[dict]:
    """Fetch activity pages until all items on a page are already known."""
    url = f"{CONFIG['base_url']}/activity/query"
    all_new = []
    page = 1

    while True:
        params = {"size": CONFIG["page_size"], "pageNumber": page, "modeList": ""}
        resp = requests.get(
            url, params=params, headers=_headers(with_yf=True), cookies=_cookies()
        )
        resp.raise_for_status()
        body = resp.json()

        if body.get("result") != "0000":
            log.error("Activity API error: %s", body.get("message"))
            break

        data_list = body["data"].get("dataList", [])
        if not data_list:
            break

        new_on_page = [a for a in data_list if a["labelId"] not in known_ids]
        all_new.extend(new_on_page)

        if len(new_on_page) == 0:
            log.info("Page %d: all %d items already known – stopping", page, len(data_list))
            break

        log.info(
            "Page %d: %d new / %d total on page", page, len(new_on_page), len(data_list)
        )

        if len(new_on_page) < len(data_list):
            break

        total_pages = body["data"].get("totalPage", 1)
        if page >= total_pages:
            break

        page += 1
        time.sleep(0.3)

    return all_new


def sync_activities():
    existing = _load_json(ACTIVITIES_FILE) or []
    known_ids = {str(a["labelId"]) for a in existing}
    log.info("Activities: %d existing records, %d known IDs", len(existing), len(known_ids))

    new_items = fetch_activities(known_ids)
    if new_items:
        merged = new_items + existing
        merged.sort(key=lambda a: a.get("startTime", 0), reverse=True)
        _save_json(ACTIVITIES_FILE, merged)
        log.info("Activities: added %d new records (total %d)", len(new_items), len(merged))
    else:
        log.info("Activities: no new records")

    return {str(a["labelId"]) for a in (new_items + existing)}


# ──────────────────────────────────────────────
# Analyse – daily metrics, incremental by happenDay
# ──────────────────────────────────────────────
def sync_analyse():
    url = f"{CONFIG['base_url']}/analyse/query"
    resp = requests.get(url, headers=_headers(with_yf=True), cookies=_cookies())
    resp.raise_for_status()
    body = resp.json()

    if body.get("result") != "0000":
        log.error("Analyse API error: %s", body.get("message"))
        return

    api_data = body["data"]
    existing = _load_json(ANALYSE_FILE)

    if existing is None:
        _save_json(ANALYSE_FILE, api_data)
        day_count = len(api_data.get("dayList", []))
        log.info("Analyse: initial save – %d days of data", day_count)
        return

    existing_days = {d["happenDay"]: d for d in existing.get("dayList", [])}
    new_count = 0
    for day in api_data.get("dayList", []):
        hd = day["happenDay"]
        if hd not in existing_days:
            existing_days[hd] = day
            new_count += 1

    existing["dayList"] = sorted(existing_days.values(), key=lambda d: d["happenDay"])

    for key in api_data:
        if key != "dayList":
            existing[key] = api_data[key]

    _save_json(ANALYSE_FILE, existing)
    log.info(
        "Analyse: %d new days added (total %d days)",
        new_count,
        len(existing["dayList"]),
    )


# ──────────────────────────────────────────────
# Dashboard – always full refresh
# ──────────────────────────────────────────────
def sync_dashboard():
    url = f"{CONFIG['base_url']}/dashboard/detail/query"
    resp = requests.get(url, headers=_headers(), cookies=_cookies())
    resp.raise_for_status()
    body = resp.json()

    if body.get("result") != "0000":
        log.error("Dashboard API error: %s", body.get("message"))
        return

    _save_json(DASHBOARD_FILE, body["data"])
    log.info("Dashboard: refreshed successfully")


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────
def main():
    log.info("=" * 50)
    log.info("COROS Data Sync – starting")
    log.info("=" * 50)

    if not CONFIG["access_token"]:
        log.error("COROS_ACCESS_TOKEN not set. Configure secrets first.")
        raise SystemExit(1)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    meta = _load_meta()

    log.info("--- Syncing Activities ---")
    all_ids = sync_activities()
    meta["known_label_ids"] = list(all_ids)[:50]  # keep a sample for debugging

    log.info("--- Syncing Analyse ---")
    sync_analyse()

    log.info("--- Syncing Dashboard ---")
    sync_dashboard()

    _save_meta(meta)
    log.info("=" * 50)
    log.info("COROS Data Sync – complete")
    log.info("=" * 50)


if __name__ == "__main__":
    main()
