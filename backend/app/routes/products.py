from flask import Blueprint, request, jsonify
from ..db import db
from ..models.product import Product

products_bp = Blueprint("products", __name__)


@products_bp.route("/", methods=["GET"])
def get_products():
    products = Product.query.all()
    return jsonify([{"id": p.id, "name": p.name, "price": p.price, "stock": p.stock} for p in products])


@products_bp.route("/<int:product_id>", methods=["GET"])
def get_product(product_id):
    product = Product.query.get(product_id)
    if not product:
        return jsonify({"error": "Product not found"}), 404
    return jsonify({"id": product.id, "name": product.name, "price": product.price, "stock": product.stock})


@products_bp.route("/", methods=["POST"])
def create_product():
    data = request.json
    # ⚠️ no validation — price could be negative, stock could be negative
    product = Product(
        name=data["name"],
        price=data["price"],
        stock=data.get("stock", 0),
    )
    db.session.add(product)
    db.session.commit()
    return jsonify({"id": product.id, "name": product.name}), 201


@products_bp.route("/<int:product_id>", methods=["PUT"])
def update_product(product_id):
    product = Product.query.get(product_id)
    if not product:
        return jsonify({"error": "Product not found"}), 404
    data = request.json
    if "name" in data:
        product.name = data["name"]
    if "price" in data:
        product.price = data["price"]
    if "stock" in data:
        product.stock = data["stock"]
    db.session.commit()
    return jsonify({"id": product.id, "name": product.name, "price": product.price})


def apply_discount(price, discount):
    # ⚠️ no guard against discount > 100 or negative values
    return price - (price * discount / 100)


@products_bp.route("/<int:product_id>/discount", methods=["POST"])
def discount_product(product_id):
    product = Product.query.get(product_id)
    if not product:
        return jsonify({"error": "Product not found"}), 404
    discount = request.json.get("discount", 0)
    new_price = apply_discount(product.price, discount)
    product.price = new_price
    db.session.commit()
    return jsonify({"id": product.id, "new_price": product.price})
