from flask import Blueprint, request, jsonify
from ..db import db
from ..models.user import User

users_bp = Blueprint("users", __name__)


@users_bp.route("/", methods=["GET"])
def get_users():
    users = User.query.all()
    return jsonify([{"id": u.id, "username": u.username, "email": u.email, "role": u.role} for u in users])


@users_bp.route("/<int:user_id>", methods=["GET"])
def get_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({"id": user.id, "username": user.username, "email": user.email, "role": user.role})


@users_bp.route("/", methods=["POST"])
def create_user():
    data = request.json
    # ⚠️ no input validation
    user = User(
        username=data["username"],
        email=data["email"],
        password=data["password"],  # ⚠️ no hashing
        role=data.get("role", "user"),
    )
    db.session.add(user)
    db.session.commit()
    return jsonify({"id": user.id, "username": user.username}), 201


@users_bp.route("/<int:user_id>", methods=["DELETE"])
def delete_user(user_id):
    # ⚠️ no auth check — anyone can delete any user
    user = User.query.get(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": "Deleted"})


@users_bp.route("/search", methods=["GET"])
def search_users():
    q = request.args.get("q", "")
    # ⚠️ raw string interpolation — SQL injection risk (illustrative with ORM workaround below)
    results = User.query.filter(User.username.like(f"%{q}%")).all()
    return jsonify([{"id": u.id, "username": u.username} for u in results])
