from flask import Flask, jsonify, render_template
import requests
import time

app = Flask(__name__)

HEADERS = {"User-Agent": "Mozilla/5.0"}

# =========================================================
# FEATURE 1: Application Service Health (SEQUENTIAL CHECK)
# =========================================================

SERVICES = [
    {"name": "API Service", "url": "https://api.github.com"},
    {"name": "Local App", "url": "http://localhost:5000"},
    {"name": "Invalid Service", "url": "http://localhost:9999"}
]

def check_service(service):
    time.sleep(2)  # simulate real check
    try:
        r = requests.get(service["url"], timeout=5, headers=HEADERS, verify=False)
        return {
            "ok": r.status_code == 200,
            "message": f"Healthy ({r.status_code})"
        }
    except Exception:
        return {
            "ok": False,
            "message": "Unreachable"
        }

@app.route("/check/<int:index>")
def check(index):
    result = check_service(SERVICES[index])
    return jsonify(result)

# =========================================================
# FEATURE 2: Integration / Connectivity Dashboard
# =========================================================

SYSTEMS = [
    {
        "name": "SAP",
        "outbound_url": "https://www.google.com",
        "inbound_url": "https://api.github.com"
    },
    {
        "name": "Primavera",
        "outbound_url": "https://api.github.com",
        "inbound_url": "https://api.github.com"
    },
    {
        "name": "MDS",
        "outbound_url": "https://api.github.com",
        "inbound_url": "http://localhost:9999"
    },
    {
        "name": "SharePoint",
        "outbound_url": "https://api.github.com",
        "inbound_url": "https://api.github.com"
    }
]

def check_url(url):
    try:
        r = requests.get(url, timeout=5, headers=HEADERS, verify=False)
        return r.status_code == 200
    except Exception:
        return False

@app.route("/")
def index():
    integration_results = []

    for system in SYSTEMS:
        integration_results.append({
            "name": system["name"],
            "outbound": check_url(system["outbound_url"]),
            "inbound": check_url(system["inbound_url"]),
            "tx_outbound": "--",
            "tx_inbound": "--"
        })

    return render_template(
        "index.html",
        services=SERVICES,
        systems=integration_results
    )

if __name__ == "__main__":
    app.run(debug=True)
