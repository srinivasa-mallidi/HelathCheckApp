"""
scheduler.py
Background monitoring engine
Runs independently of UI requests
"""

import threading
import time
import requests

from models import (
    db,
    Application,
    Interface,
    InterfaceEndpoint
)

# =====================================================
# CONFIG
# =====================================================

POLL_INTERVAL = 30   # seconds

# In-memory cache (safe for intranet, single-node)
MONITOR_CACHE = {
    "applications": {},
    "interfaces": {}
}


# =====================================================
# HELPERS
# =====================================================

def check_url(url):
    try:
        r = requests.get(
            url,
            timeout=5,
            verify=False,
            headers={"User-Agent": "Monitoring-Scheduler"}
        )
        return r.status_code < 400
    except Exception:
        return False


def fetch_number(url):
    try:
        r = requests.get(url, timeout=5, verify=False)
        return int(r.text.strip())
    except Exception:
        return 0


# =====================================================
# APPLICATION MONITOR
# =====================================================

def monitor_applications(app_context):
    with app_context():
        while True:
            print("[Scheduler] Checking applications...")

            for app in Application.query.filter_by(is_active=True).all():
                health = check_url(app.app_health_url)
                users = fetch_number(app.active_users_url)

                MONITOR_CACHE["applications"][app.id] = {
                    "healthy": health,
                    "active_users": users,
                    "last_checked": time.time()
                }

            time.sleep(POLL_INTERVAL)


# =====================================================
# INTERFACE MONITOR
# =====================================================

def monitor_interfaces(app_context):
    with app_context():
        while True:
            print("[Scheduler] Checking interfaces...")

            for interface in Interface.query.filter_by(is_active=True).all():
                result = {
                    "inbound": None,
                    "outbound": None
                }

                endpoints = InterfaceEndpoint.query.filter_by(
                    interface_id=interface.id,
                    is_active=True
                ).all()

                for ep in endpoints:
                    data = {
                        "reachable": check_url(ep.connectivity_url),
                        "total": fetch_number(ep.transaction_count_url),
                        "failed": fetch_number(ep.error_count_url),
                        "last_checked": time.time()
                    }

                    if ep.direction == "INBOUND":
                        result["inbound"] = data
                    elif ep.direction == "OUTBOUND":
                        result["outbound"] = data

                MONITOR_CACHE["interfaces"][interface.id] = result

            time.sleep(POLL_INTERVAL)


# =====================================================
# START SCHEDULER
# =====================================================

def start_scheduler(app):
    """
    Call this once from app.py
    """

    print("[Scheduler] Starting background monitors...")

    app_context = app.app_context

    threading.Thread(
        target=monitor_applications,
        args=(app_context,),
        daemon=True
    ).start()

    threading.Thread(
        target=monitor_interfaces,
        args=(app_context,),
        daemon=True
    ).start()
