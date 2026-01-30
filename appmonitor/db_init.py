from app import app
from models import db, User
from werkzeug.security import generate_password_hash

with app.app_context():
    db.drop_all()
    db.create_all()

    admin = User(
        username="admin",
        password_hash=generate_password_hash("admin123")
    )

    db.session.add(admin)
    db.session.commit()

    print("DB initialized")
    print("Login → admin / admin123")
