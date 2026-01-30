from flask import Flask, render_template, redirect, request, jsonify
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import check_password_hash
from models import *
import requests

def check_endpoint(url):
    """
    Generic endpoint health check
    Returns True if reachable, False otherwise
    """
    try:
        resp = requests.get(
            url,
            timeout=5,
            verify=False,
            headers={"User-Agent": "Monitoring-Portal"}
        )
        return resp.status_code < 400
    except Exception as e:
        print("Endpoint check failed:", url, e)
        return False


app = Flask(__name__)
app.config["SECRET_KEY"] = "shell-secure-key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///monitor.db"

db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ---------------- AUDIT HELPER ----------------
def audit(action, entity, old, new, notes=""):
    log = AuditLog(
        user=current_user.username,
        action=action,
        entity=entity,
        old_value=old,
        new_value=new,
        notes=notes
    )
    db.session.add(log)
    db.session.commit()


# ---------------- PUBLIC DASHBOARD ----------------
@app.route("/")
def home():
    systems = System.query.filter_by(is_active=True).all()
    return render_template("home.html", systems=systems)

@app.route("/health/<int:system_id>")
def health(system_id):
    monitors = MonitorConfig.query.filter_by(system_id=system_id, is_active=True).all()
    results = []

    for m in monitors:
        try:
            r = requests.get(m.endpoint_url, timeout=5, verify=False)
            results.append(r.status_code == 200)
        except:
            results.append(False)

    return jsonify({"ok": all(results) if results else False})

# ---------------- AUTH ----------------
@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(username=request.form["username"]).first()
        if user and check_password_hash(user.password_hash, request.form["password"]):
            login_user(user)
            return redirect("/admin")
    return render_template("login.html")

@app.route("/logout")
def logout():
    logout_user()
    return redirect("/")

# ---------------- ADMIN ----------------
@app.route("/admin", methods=["GET","POST"])
@login_required
def admin():
    if request.method == "POST":
        system = System(
            name=request.form["name"],
            environment=request.form["environment"]
        )
        db.session.add(system)
        db.session.commit()

        audit(
            "CREATE_SYSTEM",
            "System",
            "",
            f"{system.name} ({system.environment})"
        )

    return render_template("admin.html", systems=System.query.all())

@app.route("/admin/system/<int:id>/activate")
@login_required
def activate_system(id):
    s = System.query.get_or_404(id)
    s.is_active = True
    db.session.commit()

    audit(
        "ACTIVATE_SYSTEM",
        "System",
        f"{s.name} was inactive",
        f"{s.name} is active"
    )
    return redirect("/admin")

@app.route("/admin/system/<int:id>/inactivate")
@login_required
def inactivate_system(id):
    s = System.query.get_or_404(id)
    s.is_active = False
    db.session.commit()

    audit(
        "INACTIVATE_SYSTEM",
        "System",
        f"{s.name} was active",
        f"{s.name} is inactive"
    )
    return redirect("/admin")

@app.route("/admin/system/<int:id>/configure", methods=["GET","POST"])
@login_required
def configure(id):
    system = System.query.get_or_404(id)

    if request.method == "POST":
        m = MonitorConfig(
            system_id=id,
            monitor_type=request.form["type"],
            endpoint_url=request.form["url"]
        )
        db.session.add(m)
        db.session.commit()

        audit(
            "ADD_MONITOR",
            "MonitorConfig",
            "",
            f"{system.name} → {m.monitor_type} → {m.endpoint_url}"
        )

    monitors = MonitorConfig.query.filter_by(system_id=id).all()
    return render_template("configure_monitors.html", system=system, monitors=monitors)

# ---------------- AUDIT VIEW ----------------
@app.route("/audit")
@login_required
def audit_view():
    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).all()
    return render_template("audit.html", logs=logs)


@app.route("/admin/monitor/<int:id>/activate")
@login_required
def activate_monitor(id):
    m = MonitorConfig.query.get_or_404(id)
    m.is_active = True
    db.session.commit()

    audit(
        "ACTIVATE_MONITOR",
        "MonitorConfig",
        "Inactive",
        "Active",
        f"{m.monitor_type} | {m.endpoint_url}"
    )
    return redirect(request.referrer)


@app.route("/admin/monitor/<int:id>/inactivate")
@login_required
def inactivate_monitor(id):
    m = MonitorConfig.query.get_or_404(id)
    m.is_active = False
    db.session.commit()

    audit(
        "INACTIVATE_MONITOR",
        "MonitorConfig",
        "Active",
        "Inactive",
        f"{m.monitor_type} | {m.endpoint_url}"
    )
    return redirect(request.referrer)


@app.route("/admin/monitor/<int:id>/delete", methods=["POST"])
@login_required
def delete_monitor(id):
    m = MonitorConfig.query.get_or_404(id)
    note = request.form.get("note")

    audit(
        "DELETE_MONITOR",
        "MonitorConfig",
        f"{m.monitor_type} | {m.endpoint_url}",
        "Deleted",
        note
    )

    db.session.delete(m)
    db.session.commit()
    return redirect(request.referrer)


@app.route("/admin/system/<int:id>/delete", methods=["POST"])
@login_required
def delete_system(id):
    s = System.query.get_or_404(id)
    note = request.form.get("note")

    audit(
        "DELETE_SYSTEM",
        "System",
        f"{s.name} ({s.environment})",
        "Deleted",
        note
    )

    MonitorConfig.query.filter_by(system_id=id).delete()
    db.session.delete(s)
    db.session.commit()

    return redirect("/admin")


@app.route("/health/interface/<int:system_id>")
def interface_health(system_id):

    system = System.query.get_or_404(system_id)

    monitors = MonitorConfig.query.filter_by(
        system_id=system_id,
        is_active=True
    ).all()

    result = {
        "outbound": {
            "reachable": True,
            "total": 0,
            "failed": 0
        },
        "inbound": {
            "reachable": True,
            "total": 0,
            "failed": 0
        }
    }

    for m in monitors:
        ok = check_endpoint(m.endpoint_url)

        if m.monitor_type == "OUTBOUND":
            result["outbound"]["total"] += 1
            if not ok:
                result["outbound"]["failed"] += 1
                result["outbound"]["reachable"] = False

        elif m.monitor_type == "INBOUND":
            result["inbound"]["total"] += 1
            if not ok:
                result["inbound"]["failed"] += 1
                result["inbound"]["reachable"] = False

    return jsonify(result)



if __name__ == "__main__":
    app.run(debug=True)



