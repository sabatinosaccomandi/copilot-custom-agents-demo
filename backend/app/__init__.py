from flask import Flask
from .db import db


def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///demo.db"
    app.config["SECRET_KEY"] = "hardcoded-secret-123"  # ⚠️ intentional issue

    db.init_app(app)

    from .routes.users import users_bp
    from .routes.products import products_bp

    app.register_blueprint(users_bp, url_prefix="/users")
    app.register_blueprint(products_bp, url_prefix="/products")

    with app.app_context():
        db.create_all()

    return app
