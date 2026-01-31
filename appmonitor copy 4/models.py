from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

# =====================================================
# USERS
# =====================================================

class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# =====================================================
# APPLICATIONS
# =====================================================

class Application(db.Model):
    __tablename__ = "applications"

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(120), nullable=False)
    environment = db.Column(db.String(30), nullable=False)

    # Application health
    app_health_url = db.Column(db.String(400), nullable=False)
    active_users_url = db.Column(db.String(400), nullable=False)

    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    interfaces = db.relationship(
        "Interface",
        backref="source_application",
        cascade="all, delete-orphan"
    )


# =====================================================
# INTERFACES (Application → External / Internal System)
# =====================================================

class Interface(db.Model):
    __tablename__ = "interfaces"

    id = db.Column(db.Integer, primary_key=True)

    source_app_id = db.Column(
        db.Integer,
        db.ForeignKey("applications.id"),
        nullable=False
    )

    # FREE TEXT (SAP, Primavera, Vendor API, etc.)
    target_system_name = db.Column(
        db.String(120),
        nullable=False
    )

    # INBOUND / OUTBOUND / BOTH
    direction = db.Column(db.String(20), nullable=False)

    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    endpoints = db.relationship(
        "InterfaceEndpoint",
        backref="interface",
        cascade="all, delete-orphan"
    )


# =====================================================
# INTERFACE ENDPOINTS (METRICS PER DIRECTION)
# =====================================================

class InterfaceEndpoint(db.Model):
    __tablename__ = "interface_endpoints"

    id = db.Column(db.Integer, primary_key=True)

    interface_id = db.Column(
        db.Integer,
        db.ForeignKey("interfaces.id"),
        nullable=False
    )

    # INBOUND or OUTBOUND
    direction = db.Column(db.String(20), nullable=False)

    connectivity_url = db.Column(db.String(400), nullable=False)
    transaction_count_url = db.Column(db.String(400), nullable=False)
    error_count_url = db.Column(db.String(400), nullable=False)

    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# =====================================================
# AUDIT LOGS
# =====================================================

class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)

    user = db.Column(db.String(50), nullable=False)
    action = db.Column(db.String(100), nullable=False)
    entity = db.Column(db.String(100), nullable=False)

    old_value = db.Column(db.Text)
    new_value = db.Column(db.Text)
    notes = db.Column(db.Text)

    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
