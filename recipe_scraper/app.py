from flask import Flask, request, jsonify, send_from_directory, g
from recipe_scrapers import scrape_me
import sqlite3
import json
import re
import os
import sys

# ── Path setup (works both in development and as a PyInstaller .exe) ──────────
# BASE_DIR  = where the bundled files live (read-only when frozen)
# DATA_DIR  = where we write user data (db, uploads) – always writable
if getattr(sys, "frozen", False):
    BASE_DIR = sys._MEIPASS                          # type: ignore[attr-defined]
    DATA_DIR = os.path.dirname(sys.executable)
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = BASE_DIR

DB_PATH     = os.path.join(DATA_DIR, "recipes.db")
UPLOADS_DIR = os.path.join(DATA_DIR, "static", "uploads")

app = Flask(__name__, static_folder=os.path.join(BASE_DIR, "static"))


# ── Database ──────────────────────────────────────────────────────────────────

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DB_PATH)
        db.row_factory = sqlite3.Row
    return db


@app.teardown_appcontext
def close_db(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS recipes (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                title              TEXT    NOT NULL,
                servings           TEXT,
                servings_num       REAL,
                ingredients        TEXT    DEFAULT '[]',
                instructions       TEXT    DEFAULT '[]',
                ingredient_groups  TEXT    DEFAULT NULL,
                instruction_groups TEXT    DEFAULT NULL,
                image              TEXT,
                total_time         TEXT,
                site_name          TEXT,
                source_url         TEXT,
                category           TEXT    DEFAULT NULL,
                view_count         INTEGER DEFAULT 0,
                created_at         TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        for col in ["ingredient_groups", "instruction_groups", "category TEXT DEFAULT NULL", "view_count INTEGER DEFAULT 0"]:
            try:
                conn.execute(f"ALTER TABLE recipes ADD COLUMN {col}")
            except Exception:
                pass
        conn.execute("""
            CREATE TABLE IF NOT EXISTS meals (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                name       TEXT NOT NULL,
                category   TEXT DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        try:
            conn.execute("ALTER TABLE meals ADD COLUMN category TEXT DEFAULT NULL")
        except Exception:
            pass
        conn.execute("""
            CREATE TABLE IF NOT EXISTS meal_recipes (
                meal_id    INTEGER NOT NULL,
                recipe_id  INTEGER NOT NULL,
                sort_order INTEGER DEFAULT 0,
                PRIMARY KEY (meal_id, recipe_id)
            )
        """)
        conn.commit()


def row_to_dict(row):
    d = dict(row)
    flat_ings = json.loads(d.get("ingredients") or "[]")
    flat_steps = json.loads(d.get("instructions") or "[]")
    d["ingredients"] = flat_ings
    d["instructions"] = flat_steps
    d["ingredient_groups"] = (
        json.loads(d["ingredient_groups"])
        if d.get("ingredient_groups")
        else [{"purpose": None, "ingredients": flat_ings}]
    )
    d["instruction_groups"] = (
        json.loads(d["instruction_groups"])
        if d.get("instruction_groups")
        else [{"purpose": None, "steps": flat_steps}]
    )
    return d


def flatten_groups(groups, key):
    return [item for g in (groups or []) for item in g.get(key, [])]


# Checkbox/square Unicode characters that some recipe sites prepend to ingredients
_CHECKBOX_CHARS = re.compile(r'^[\u25A1\u25A2\u25FB\u25FC\u2610\u2611\u2612\u2713\u2714\s]+')

def clean_ingredient(text):
    """Strip leading checkbox symbols and whitespace from ingredient strings."""
    return _CHECKBOX_CHARS.sub('', text).strip() if text else text


# ── Scraper helpers ───────────────────────────────────────────────────────────

def safe_call(fn):
    try:
        result = fn()
        return result if result else None
    except Exception:
        return None


def safe_list_call(fn):
    try:
        result = fn()
        return result if isinstance(result, list) else []
    except Exception:
        return []


def get_ingredient_groups(scraper):
    try:
        groups = scraper.ingredient_groups()
        if groups:
            result = [{"purpose": g.purpose, "ingredients": [clean_ingredient(i) for i in g.ingredients]} for g in groups]
            if any(g["purpose"] for g in result) or len(result) > 1:
                return result
    except Exception:
        pass
    return [{"purpose": None, "ingredients": [clean_ingredient(i) for i in safe_list_call(scraper.ingredients)]}]


def get_instruction_groups(scraper):
    steps = []
    try:
        steps = scraper.instructions_list()
        if not isinstance(steps, list):
            steps = []
    except Exception:
        pass
    if not steps:
        try:
            text = scraper.instructions()
            if text:
                steps = [s.strip() for s in text.split("\n") if s.strip()]
        except Exception:
            pass
    return parse_instruction_groups(steps)


def parse_instruction_groups(steps):
    groups, current_purpose, current_steps = [], None, []
    for step in steps:
        clean = step.strip()
        if not clean:
            continue
        if is_section_header(clean):
            if current_steps or current_purpose is not None:
                groups.append({"purpose": current_purpose, "steps": current_steps})
            current_purpose = clean.rstrip(":").strip()
            current_steps = []
        else:
            current_steps.append(clean)
    groups.append({"purpose": current_purpose, "steps": current_steps})
    return groups


def is_section_header(text):
    if len(text) > 80:
        return False
    if text.endswith(":") and "." not in text and "!" not in text and "?" not in text:
        return True
    return False


def parse_servings_num(s):
    if not s:
        return None
    m = re.search(r"\d+(?:\.\d+)?", str(s))
    return float(m.group()) if m else None


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory("static", "index.html")


@app.route("/scrape", methods=["POST"])
def scrape():
    data = request.get_json()
    url = data.get("url", "").strip()
    if not url:
        return jsonify({"error": "No URL provided"}), 400
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        scraper = scrape_me(url)
        servings = safe_call(scraper.yields)
        ingredient_groups = get_ingredient_groups(scraper)
        instruction_groups = get_instruction_groups(scraper)
        recipe = {
            "title": safe_call(scraper.title),
            "servings": servings,
            "servings_num": parse_servings_num(servings),
            "ingredients": flatten_groups(ingredient_groups, "ingredients"),
            "instructions": flatten_groups(instruction_groups, "steps"),
            "ingredient_groups": ingredient_groups,
            "instruction_groups": instruction_groups,
            "image": safe_call(scraper.image),
            "total_time": safe_call(scraper.total_time),
            "site_name": safe_call(scraper.site_name),
            "source_url": url,
        }
        if not recipe["title"] and not recipe["ingredients"]:
            return jsonify({"error": "Could not extract a recipe from this page."}), 422
        return jsonify(recipe)
    except Exception as e:
        return jsonify({"error": f"Failed to scrape recipe: {str(e)}"}), 500


@app.route("/recipes", methods=["GET"])
def list_recipes():
    rows = get_db().execute("SELECT * FROM recipes ORDER BY created_at DESC").fetchall()
    return jsonify([row_to_dict(r) for r in rows])


@app.route("/recipes", methods=["POST"])
def save_recipe():
    data = request.get_json()
    ig = data.get("ingredient_groups")
    sg = data.get("instruction_groups")
    db = get_db()
    cur = db.execute(
        """INSERT INTO recipes
           (title, servings, servings_num, ingredients, instructions,
            ingredient_groups, instruction_groups, image, total_time, site_name, source_url, category)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            data.get("title", "Untitled"),
            data.get("servings"),
            data.get("servings_num"),
            json.dumps(flatten_groups(ig, "ingredients") if ig else data.get("ingredients", [])),
            json.dumps(flatten_groups(sg, "steps") if sg else data.get("instructions", [])),
            json.dumps(ig) if ig else None,
            json.dumps(sg) if sg else None,
            data.get("image"),
            data.get("total_time"),
            data.get("site_name"),
            data.get("source_url"),
            data.get("category"),
        ),
    )
    db.commit()
    row = db.execute("SELECT * FROM recipes WHERE id=?", (cur.lastrowid,)).fetchone()
    return jsonify(row_to_dict(row)), 201


@app.route("/recipes/<int:rid>", methods=["GET"])
def get_recipe(rid):
    row = get_db().execute("SELECT * FROM recipes WHERE id=?", (rid,)).fetchone()
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row_to_dict(row))


@app.route("/recipes/<int:rid>", methods=["PUT"])
def update_recipe(rid):
    data = request.get_json()
    ig = data.get("ingredient_groups")
    sg = data.get("instruction_groups")
    db = get_db()
    db.execute(
        """UPDATE recipes
           SET title=?, servings=?, servings_num=?, ingredients=?, instructions=?,
               ingredient_groups=?, instruction_groups=?, image=?, total_time=?, site_name=?, category=?
           WHERE id=?""",
        (
            data.get("title"),
            data.get("servings"),
            data.get("servings_num"),
            json.dumps(flatten_groups(ig, "ingredients") if ig else data.get("ingredients", [])),
            json.dumps(flatten_groups(sg, "steps") if sg else data.get("instructions", [])),
            json.dumps(ig) if ig else None,
            json.dumps(sg) if sg else None,
            data.get("image"),
            data.get("total_time"),
            data.get("site_name"),
            data.get("category"),
            rid,
        ),
    )
    db.commit()
    row = db.execute("SELECT * FROM recipes WHERE id=?", (rid,)).fetchone()
    return jsonify(row_to_dict(row))


@app.route("/static/uploads/<path:filename>")
def serve_upload(filename):
    """Serve uploaded images from the writable DATA_DIR (works when frozen)."""
    return send_from_directory(UPLOADS_DIR, filename)


@app.route("/recipes/<int:rid>/image", methods=["POST"])
def update_image(rid):
    db = get_db()
    if "file" in request.files:
        f = request.files["file"]
        if f and f.filename:
            ext = os.path.splitext(f.filename)[1].lower()
            os.makedirs(UPLOADS_DIR, exist_ok=True)
            filename = f"{rid}{ext}"
            f.save(os.path.join(UPLOADS_DIR, filename))
            url = f"/static/uploads/{filename}"
            db.execute("UPDATE recipes SET image=? WHERE id=?", (url, rid))
            db.commit()
            return jsonify({"image": url})
    data = request.get_json(silent=True) or {}
    url = data.get("url", "").strip()
    if url:
        db.execute("UPDATE recipes SET image=? WHERE id=?", (url, rid))
        db.commit()
        return jsonify({"image": url})
    return jsonify({"error": "No image provided"}), 400


@app.route("/recipes/<int:rid>/view", methods=["POST"])
def increment_view(rid):
    db = get_db()
    db.execute("UPDATE recipes SET view_count = view_count + 1 WHERE id=?", (rid,))
    db.commit()
    return jsonify({"ok": True})


@app.route("/recipes/<int:rid>", methods=["DELETE"])
def delete_recipe(rid):
    db = get_db()
    db.execute("DELETE FROM recipes WHERE id=?", (rid,))
    db.commit()
    return jsonify({"ok": True})


@app.route("/meals", methods=["GET"])
def list_meals():
    db = get_db()
    meals = db.execute("SELECT * FROM meals ORDER BY created_at DESC").fetchall()
    result = []
    for m in meals:
        recipes = db.execute(
            """SELECT r.id, r.title, r.servings, r.servings_num, r.image
               FROM meal_recipes mr JOIN recipes r ON r.id = mr.recipe_id
               WHERE mr.meal_id = ? ORDER BY mr.sort_order""",
            (m["id"],)
        ).fetchall()
        result.append({**dict(m), "recipes": [dict(r) for r in recipes]})
    return jsonify(result)


@app.route("/meals", methods=["POST"])
def create_meal():
    data = request.get_json()
    db = get_db()
    cur = db.execute("INSERT INTO meals (name) VALUES (?)", (data.get("name", "New Meal"),))
    db.commit()
    meal_id = cur.lastrowid
    return jsonify({"id": meal_id, "name": data.get("name", "New Meal"), "recipes": []}), 201


@app.route("/meals/<int:mid>", methods=["PUT"])
def update_meal(mid):
    data = request.get_json()
    db = get_db()
    db.execute("UPDATE meals SET name=?, category=? WHERE id=?",
               (data.get("name"), data.get("category"), mid))
    db.commit()
    return jsonify({"ok": True})


@app.route("/meals/<int:mid>", methods=["DELETE"])
def delete_meal(mid):
    db = get_db()
    db.execute("DELETE FROM meal_recipes WHERE meal_id=?", (mid,))
    db.execute("DELETE FROM meals WHERE id=?", (mid,))
    db.commit()
    return jsonify({"ok": True})


@app.route("/meals/<int:mid>/recipes", methods=["POST"])
def add_recipe_to_meal(mid):
    data = request.get_json()
    rid = data.get("recipe_id")
    db = get_db()
    try:
        db.execute("INSERT OR IGNORE INTO meal_recipes (meal_id, recipe_id) VALUES (?,?)", (mid, rid))
        db.commit()
    except Exception:
        pass
    return jsonify({"ok": True})


@app.route("/meals/<int:mid>/recipes/<int:rid>", methods=["DELETE"])
def remove_recipe_from_meal(mid, rid):
    db = get_db()
    db.execute("DELETE FROM meal_recipes WHERE meal_id=? AND recipe_id=?", (mid, rid))
    db.commit()
    return jsonify({"ok": True})


if __name__ == "__main__":
    os.makedirs(os.path.join(BASE_DIR, "static"), exist_ok=True)
    init_db()
    app.run(debug=True, port=5000)
