from flask import (
    Flask, render_template, redirect, request,
    jsonify, session, url_for
)
from flask_login import (
    LoginManager, login_user, login_required,
    logout_user, current_user
)
from werkzeug.security import check_password_hash
import requests
import os

from datetime import datetime


from models import (
    db, User,
    Application, Interface, InterfaceEndpoint,
    AuditLog
)

# =====================================================
# APP INIT
# =====================================================

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
# COMMON HELPERS
# =====================================================

def audit(action, entity, old=None, new=None, notes=None):
    if not current_user.is_authenticated:
        return

    log = AuditLog(
        user=current_user.username,
        action=action,
        entity=entity,
        old_value=str(old) if old else "",
        new_value=str(new) if new else "",
        notes=notes or ""
    )
    db.session.add(log)
    db.session.commit()


def check_url(url):
    """Generic URL health check"""
    try:
        r = requests.get(
            url,
            timeout=5,
            verify=False,
            headers={"User-Agent": "Monitoring-Portal"}
        )
        return r.status_code < 400
    except Exception:
        return False


def fetch_number(url):
    """Fetch numeric metric from API"""
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
        return redirect(url_for("home"))

    return render_template("select_app.html", applications=apps)


@app.route("/change-app")
def change_app():
    session.pop("selected_app_id", None)
    return redirect(url_for("select_application"))


# =====================================================
# HOME DASHBOARD
# =====================================================

@app.route("/home")
def home():
    app_id = session.get("selected_app_id")
    if not app_id:
        return redirect(url_for("select_application"))

    app_obj = Application.query.get_or_404(app_id)

    interfaces = Interface.query.filter_by(
        source_app_id=app_id,
        is_active=True
    ).all()

    return render_template(
        "home.html",
        app=app_obj,
        interfaces=interfaces
    )


# =====================================================
# DASHBOARD APIs (AJAX)
# =====================================================

@app.route("/api/app-health/<int:app_id>")
def api_app_health(app_id):
    app_obj = Application.query.get_or_404(app_id)

    ok = check_url(app_obj.app_health_url)
    users = fetch_number(app_obj.active_users_url)

    return jsonify({
        "healthy": ok,
        "active_users": users
    })


@app.route("/api/interface-health/<int:interface_id>")
def api_interface_health(interface_id):
    interface = Interface.query.get_or_404(interface_id)

    endpoints = InterfaceEndpoint.query.filter_by(
        interface_id=interface_id
    ).all()

    result = {
        "inbound": None,
        "outbound": None
    }

    for ep in endpoints:
        data = {
            "reachable": check_url(ep.connectivity_url),
            "total": fetch_number(ep.transaction_count_url),
            "failed": fetch_number(ep.error_count_url)
        }

        if ep.direction == "INBOUND":
            result["inbound"] = data
        elif ep.direction == "OUTBOUND":
            result["outbound"] = data

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
# ADMIN – APPLICATIONS
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
        active_users_url=request.form["users_url"]
    )
    db.session.add(app_obj)
    db.session.commit()

    audit("CREATE", "Application", None, app_obj.name)
    return redirect("/admin")


# =====================================================
# ADMIN – INTERFACES
# =====================================================

@app.route("/admin/interface/add", methods=["POST"])
@login_required
class Interface(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    source_app_id = db.Column(
        db.Integer,
        db.ForeignKey("application.id"),
        nullable=False
    )

    target_app_name = db.Column(
        db.String(120),
        nullable=False
    )

    direction = db.Column(
        db.String(20),  # INBOUND / OUTBOUND / BOTH
        nullable=False
    )

    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)





@app.route("/admin/application/<int:app_id>/edit", methods=["GET", "POST"])
@login_required
def edit_application(app_id):
    app_obj = Application.query.get_or_404(app_id)

    if request.method == "POST":
        old = {
            "name": app_obj.name,
            "environment": app_obj.environment,
            "health_url": app_obj.app_health_url,
            "users_url": app_obj.active_users_url
        }

        app_obj.name = request.form["name"]
        app_obj.environment = request.form["environment"]
        app_obj.app_health_url = request.form["health_url"]
        app_obj.active_users_url = request.form["users_url"]

        db.session.commit()

        audit(
            action="UPDATE",
            entity="Application",
            old=old,
            new={
                "name": app_obj.name,
                "environment": app_obj.environment
            }
        )

        return redirect("/admin")

    return render_template(
        "application_form.html",
        application=app_obj,
        mode="edit"
    )

@app.route("/admin/application/<int:app_id>/interfaces")
@login_required
def application_interfaces(app_id):
    app_obj = Application.query.get_or_404(app_id)

    interfaces = Interface.query.filter(
        (Interface.source_app_id == app_id) |
        (Interface.target_app_id == app_id)
    ).all()

    applications = Application.query.filter_by(is_active=True).all()

    return render_template(
        "interface_form.html",
        application=app_obj,
        interfaces=interfaces,
        applications=applications
    )


# ==========================
# INTERFACE MANAGEMENT
# ==========================

@app.route("/admin/application/<int:app_id>/interfaces", methods=["GET"])
@login_required
def interface_form(app_id):
    app_obj = Application.query.get_or_404(app_id)

    interfaces = Interface.query.filter_by(
        source_app_id=app_id
    ).all()

    return render_template(
        "interface_form.html",
        app=app_obj,
        interfaces=interfaces
    )


@app.route("/admin/application/<int:app_id>/interfaces", methods=["POST"])
@login_required
def create_interface(app_id):
    interface = Interface(
        source_app_id=app_id,
        target_app_name=request.form["target_app_name"],
        direction=request.form["direction"]
    )

    db.session.add(interface)
    db.session.commit()

    audit(
        "CREATE",
        "Interface",
        None,
        f"{interface.target_app_name} ({interface.direction})"
    )

    return redirect(
        url_for("interface_form", app_id=app_id)
    )



# =====================================================
# MAIN
# =====================================================

if __name__ == "__main__":
    app.run(debug=True)
