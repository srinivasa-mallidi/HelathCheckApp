from flask import Flask, render_template
import requests
import time

app = Flask(__name__)

SERVICES = [
    {"name": "API Service", "url": "https://api.github.com"},
    {"name": "Local App", "url": "http://localhost:5000"},
    {"name": "Example Down", "url": "http://localhost:9999"},
]

headers = {"User-Agent": "Mozilla/5.0"}

def check_health(url):
    try:
        time.sleep(2)  # simulate real check delay
        r = requests.get(url, timeout=5, headers=headers, verify=False)
        return True, f"Healthy ({r.status_code})"
    except Exception:
        return False, "Unreachable"

@app.route("/")
def index():
    return render_template("index.html", services=SERVICES)

@app.route("/check/<int:idx>")
def check(idx):
    service = SERVICES[idx]
    ok, message = check_health(service["url"])

    next_idx = idx + 1 if idx + 1 < len(SERVICES) else None

    return render_template(
        "row.html",
        service=service,
        ok=ok,
        message=message,
        idx=idx,
        next_idx=next_idx
    )

if __name__ == "__main__":
    app.run(debug=True)
