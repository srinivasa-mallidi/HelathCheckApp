from flask import (
    Flask, render_template, redirect,
    request, jsonify, session, url_for
)
from flask_login import (
    LoginManager, login_user,
    login_required, logout_user, current_user
)
from werkzeug.security import check_password_hash
from datetime import datetime
import requests

from models import (
    db, User,
    Application, Interface, InterfaceEndpoint,
    AuditLog
)

app = Flask(__name__)
app.config["SECRET_KEY"] = "shell-secure-key"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///monitor.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

login_manager = LoginManager(app)
login_manager.login_view = "login"


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# =====================================================
# HELPERS
# =====================================================

def audit(action, entity, old=None, new=None):
    if not current_user.is_authenticated:
        return

    log = AuditLog(
        user=current_user.username,
        action=action,
        entity=entity,
        old_value=str(old) if old else "",
        new_value=str(new) if new else "",
        timestamp=datetime.utcnow()
    )
    db.session.add(log)
    db.session.commit()


def check_url(url):
    try:
        r = requests.get(url, timeout=5, verify=False)
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
# APPLICATION SELECTION
# =====================================================

@app.route("/", methods=["GET", "POST"])
def select_application():
    apps = Application.query.filter_by(is_active=True).all()

    if request.method == "POST":
        session["selected_app_id"] = int(request.form["application_id"])
        return redirect("/home")

    return render_template("select_app.html", applications=apps)


@app.route("/change-app")
def change_app():
    session.pop("selected_app_id", None)
    return redirect("/")


# =====================================================
# HOME DASHBOARD
# =====================================================

@app.route("/home")
def home():
    app_id = session.get("selected_app_id")
    if not app_id:
        return redirect("/")

    app_obj = Application.query.get_or_404(app_id)

    interfaces = Interface.query.filter_by(
        source_app_id=app_id,
        is_active=True
    ).all()

    return render_template("home.html", app=app_obj, interfaces=interfaces)


# =====================================================
# AJAX APIs
# =====================================================

@app.route("/api/app-health/<int:app_id>")
def api_app_health(app_id):
    app_obj = Application.query.get_or_404(app_id)

    return jsonify({
        "healthy": check_url(app_obj.app_health_url),
        "active_users": fetch_number(app_obj.active_users_url)
    })


@app.route("/api/interface-health/<int:interface_id>")
def api_interface_health(interface_id):
    endpoints = InterfaceEndpoint.query.filter_by(
        interface_id=interface_id,
        is_active=True
    ).all()

    result = {"inbound": None, "outbound": None}

    for ep in endpoints:
        data = {
            "reachable": check_url(ep.connectivity_url),
            "total": fetch_number(ep.transaction_count_url),
            "failed": fetch_number(ep.error_count_url)
        }
        result[ep.direction.lower()] = data

    return jsonify(result)


# =====================================================
# AUTH
# =====================================================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(
            username=request.form["username"]
        ).first()

        if user and check_password_hash(
            user.password_hash,
            request.form["password"]
        ):
            login_user(user)
            return redirect("/admin")

    return render_template("login.html")


@app.route("/logout")
def logout():
    logout_user()
    return redirect("/")


# =====================================================
# ADMIN
# =====================================================

@app.route("/admin")
@login_required
def admin():
    apps = Application.query.all()
    return render_template("admin.html", applications=apps)


@app.route("/admin/application/add", methods=["POST"])
@login_required
def add_application():
    app_obj = Application(
        name=request.form["name"],
        environment=request.form["environment"],
        app_health_url=request.form["health_url"],
        active_users_url=request.form["users_url"],
        is_active=True
    )
    db.session.add(app_obj)
    db.session.commit()

    audit("CREATE", "Application", None, app_obj.name)
    return redirect("/admin")


@app.route("/admin/application/<int:app_id>/edit", methods=["GET", "POST"])
@login_required
def edit_application(app_id):
    app_obj = Application.query.get_or_404(app_id)

    if request.method == "POST":
        app_obj.name = request.form["name"]
        app_obj.environment = request.form["environment"]
        app_obj.app_health_url = request.form["health_url"]
        app_obj.active_users_url = request.form["users_url"]
        db.session.commit()

        audit("UPDATE", "Application", app_id, app_obj.name)
        return redirect("/admin")

    return render_template("application_form.html", application=app_obj)


@app.route("/admin/application/<int:app_id>/activate")
@login_required
def activate_application(app_id):
    app_obj = Application.query.get_or_404(app_id)
    app_obj.is_active = True
    db.session.commit()
    return redirect("/admin")


@app.route("/admin/application/<int:app_id>/deactivate")
@login_required
def deactivate_application(app_id):
    app_obj = Application.query.get_or_404(app_id)
    app_obj.is_active = False
    db.session.commit()
    return redirect("/admin")


# =====================================================
# INTERFACES
# =====================================================

@app.route("/admin/application/<int:app_id>/interfaces", methods=["GET", "POST"])
@login_required
def manage_interfaces(app_id):
    application = Application.query.get_or_404(app_id)

    if request.method == "POST":
        interface = Interface(
            source_app_id=app_id,
            target_system_name=request.form["target_system_name"],
            direction=request.form["direction"],
            is_active=True
        )
        db.session.add(interface)
        db.session.commit()

        return redirect(url_for("manage_interfaces", app_id=app_id))

    interfaces = Interface.query.filter_by(source_app_id=app_id).all()

    return render_template(
        "interface_form.html",
        application=application,
        interfaces=interfaces
    )


# =====================================================
# INTERFACE ENDPOINTS (FIXED)
# =====================================================

@app.route("/admin/interface/<int:interface_id>/endpoints", methods=["GET", "POST"])
@login_required
def interface_endpoints(interface_id):
    interface = Interface.query.get_or_404(interface_id)

    if request.method == "POST":
        direction = request.form["direction"]

        endpoint = InterfaceEndpoint.query.filter_by(
            interface_id=interface_id,
            direction=direction
        ).first()

        if endpoint:
            endpoint.connectivity_url = request.form["connectivity_url"]
            endpoint.transaction_count_url = request.form["transaction_count_url"]
            endpoint.error_count_url = request.form["error_count_url"]
        else:
            endpoint = InterfaceEndpoint(
                interface_id=interface_id,
                direction=direction,
                connectivity_url=request.form["connectivity_url"],
                transaction_count_url=request.form["transaction_count_url"],
                error_count_url=request.form["error_count_url"],
                is_active=True
            )
            db.session.add(endpoint)

        db.session.commit()

        return redirect(url_for("interface_endpoints", interface_id=interface_id))

    inbound = InterfaceEndpoint.query.filter_by(
        interface_id=interface_id,
        direction="INBOUND"
    ).first()

    outbound = InterfaceEndpoint.query.filter_by(
        interface_id=interface_id,
        direction="OUTBOUND"
    ).first()

    return render_template(
        "interface_endpoints.html",
        interface=interface,
        inbound=inbound,
        outbound=outbound
    )


# =====================================================
# AUDIT PAGE
# =====================================================

#@app.route("/audit")
#@login_required
#def audit_page():
#    logs = AuditLog.query.order_by(AuditLog.timestamp.desc()).all()
#    return render_template("audit.html", logs=logs)


# =====================================================
# MAIN
# =====================================================

if __name__ == "__main__":
    app.run(debug=True)
