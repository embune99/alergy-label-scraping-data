import json
import os
from functools import wraps
from pathlib import Path

from flask import Flask, render_template, abort, request, redirect, url_for, session


BASE_DIR = Path(__file__).resolve().parent
PRODUCTS_DIR = BASE_DIR / "products"


app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-change-me")


USERNAME = "admin"
PASSWORD = "allergy@8386"


def login_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("login", next=request.path))
        return view_func(*args, **kwargs)

    return wrapped


def iter_category_dirs():
    if not PRODUCTS_DIR.exists():
        return []
    for entry in sorted(PRODUCTS_DIR.iterdir()):
        if entry.is_dir():
            yield entry


def load_category_meta(category_dir: Path):
    meta_path = category_dir / "_meta.json"
    if not meta_path.exists():
        return {
            "category_url": None,
            "slug": category_dir.name,
            "crawled_product_urls": None,
            "processed_count": None,
        }
    with meta_path.open(encoding="utf-8") as f:
        return json.load(f)


def load_product_file(category_dir: Path, product_id: str):
    product_path = category_dir / f"{product_id}.json"
    if not product_path.exists():
        return None
    with product_path.open(encoding="utf-8") as f:
        return json.load(f)


def load_all_products_for_category(category_dir: Path):
    products = []
    for entry in sorted(category_dir.glob("*.json")):
        if entry.name == "_meta.json":
            continue
        try:
            with entry.open(encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            continue

        product_info = data.get("product_information", {})
        additional_info = data.get("additional_information", {})
        inferred_info = data.get("inferred_information", {})

        products.append(
            {
                "id": additional_info.get("id") or entry.stem,
                "category": category_dir.name,
                "name": product_info.get("product_name"),
                "price": product_info.get("price"),
                "image": (product_info.get("images") or [None])[0],
                "product_category": inferred_info.get("product_category"),
            }
        )
    return products


@app.route("/")
@login_required
def index():
    categories = []
    for category_dir in iter_category_dirs():
        meta = load_category_meta(category_dir)
        categories.append(
            {
                "name": category_dir.name,
                "slug": meta.get("slug") or category_dir.name,
                "category_url": meta.get("category_url"),
                "product_count": meta.get("processed_count")
                or meta.get("crawled_product_urls"),
            }
        )
    return render_template("index.html", categories=categories)


@app.route("/category/<category_name>/")
@login_required
def category_view(category_name):
    category_dir = PRODUCTS_DIR / category_name
    if not category_dir.exists() or not category_dir.is_dir():
        abort(404)
    meta = load_category_meta(category_dir)
    products = load_all_products_for_category(category_dir)

    # view type: "table" (default) or "cards"
    view_type = request.args.get("view", "table")
    if view_type not in {"cards", "table"}:
        view_type = "table"

    # simple pagination: 20 items per page
    per_page = 20
    try:
        page = int(request.args.get("page", "1"))
    except ValueError:
        page = 1
    if page < 1:
        page = 1

    total = len(products)
    start = (page - 1) * per_page
    end = start + per_page
    page_items = products[start:end]

    total_pages = (total + per_page - 1) // per_page if total else 1

    return render_template(
        "category.html",
        category_name=category_name,
        meta=meta,
        products=page_items,
        page=page,
        per_page=per_page,
        total=total,
        total_pages=total_pages,
        view_type=view_type,
    )


@app.route("/product/<category_name>/<product_id>/")
@login_required
def product_view(category_name, product_id):
    category_dir = PRODUCTS_DIR / category_name
    if not category_dir.exists() or not category_dir.is_dir():
        abort(404)

    data = load_product_file(category_dir, product_id)
    if data is None:
        abort(404)

    product_info = data.get("product_information", {})
    inferred_info = data.get("inferred_information", {})
    additional_info = data.get("additional_information", {})

    return render_template(
        "product.html",
        category_name=category_name,
        product_id=product_id,
        product_info=product_info,
        inferred_info=inferred_info,
        additional_info=additional_info,
    )


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        if username == USERNAME and password == PASSWORD:
            session["logged_in"] = True
            session["username"] = username
            next_url = request.args.get("next") or url_for("index")
            return redirect(next_url)
        error = "Invalid username or password."

    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "5000"))
    app.run(debug=True, host="0.0.0.0", port=port)

