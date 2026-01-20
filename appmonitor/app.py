from flask import Flask, jsonify, render_template
import requests
import time

app = Flask(__name__)

SERVICES = [
    {"name": "API Service", "url": "https://api.github.com"},
    {"name": "Local App", "url": "http://localhost:5000"},
    {"name": "Invalid Service", "url": "http://localhost:9999"}
]

HEADERS = {"User-Agent": "Mozilla/5.0"}

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

@app.route("/")
def index():
    return render_template("index.html", services=SERVICES)

@app.route("/check/<int:index>")
def check(index):
    result = check_service(SERVICES[index])
    return jsonify(result)

if __name__ == "__main__":
    app.run(debug=True)
