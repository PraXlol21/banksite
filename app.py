import os
import random
import sqlite3
from functools import wraps

from flask import Flask, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "users.db")


def load_env_file(path):
    """Read KEY=VALUE lines from a local .env file into os.environ (never committed)."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())


load_env_file(os.path.join(BASE_DIR, ".env"))

# MySQL is used when MYSQL_HOST is set (locally, via .env). Otherwise SQLite (e.g. on Render).
USE_MYSQL = bool(os.environ.get("MYSQL_HOST"))
if USE_MYSQL:
    import pymysql
    import pymysql.cursors

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# Fields a user can edit on their profile: (column, label, input type)
EDITABLE_FIELDS = [
    ("full_name", "Full name", "text"),
    ("email", "Email", "email"),
    ("phone", "Phone", "text"),
    ("city", "City", "text"),
    ("occupation", "Occupation", "text"),
    ("balance", "Account balance (₹)", "number"),
    ("savings", "Savings (₹)", "number"),
    ("monthly_income", "Monthly income (₹)", "number"),
    ("monthly_expenses", "Monthly expenses (₹)", "number"),
    ("debt", "Debt (₹)", "number"),
]
MONEY_FIELDS = {"balance", "savings", "monthly_income", "monthly_expenses", "debt"}

FIRST = ["Aarav", "Diya", "Rohan", "Meera", "Kabir", "Ananya", "Vikram", "Isha", "Arjun", "Sneha"]
LAST = ["Sharma", "Iyer", "Patel", "Reddy", "Nair", "Gupta", "Khan", "Das", "Menon", "Singh"]
CITIES = ["Chennai", "Mumbai", "Bengaluru", "Delhi", "Hyderabad", "Pune", "Kolkata", "Vellore"]
JOBS = ["Student", "Engineer", "Designer", "Teacher", "Doctor", "Analyst", "Freelancer", "Manager"]

CREATE_MYSQL = """CREATE TABLE IF NOT EXISTS users (
    id               INT AUTO_INCREMENT PRIMARY KEY,
    username         VARCHAR(50)  NOT NULL UNIQUE,
    password_hash    VARCHAR(255) NOT NULL,
    full_name        VARCHAR(100),
    email            VARCHAR(100),
    phone            VARCHAR(20),
    city             VARCHAR(50),
    occupation       VARCHAR(50),
    balance          DECIMAL(14,2),
    savings          DECIMAL(14,2),
    monthly_income   DECIMAL(14,2),
    monthly_expenses DECIMAL(14,2),
    debt             DECIMAL(14,2)
)"""

CREATE_SQLITE = """CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    full_name TEXT, email TEXT, phone TEXT, city TEXT, occupation TEXT,
    balance REAL, savings REAL, monthly_income REAL, monthly_expenses REAL, debt REAL
)"""


def connect():
    if USE_MYSQL:
        return pymysql.connect(
            host=os.environ["MYSQL_HOST"],
            port=int(os.environ.get("MYSQL_PORT", "3306")),
            user=os.environ["MYSQL_USER"],
            password=os.environ["MYSQL_PASSWORD"],
            database=os.environ["MYSQL_DATABASE"],
            cursorclass=pymysql.cursors.DictCursor,
            charset="utf8mb4",
        )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def run(conn, sql, params=()):
    """Execute SQL written with ? placeholders on either database; return all rows."""
    if USE_MYSQL:
        sql = sql.replace("?", "%s")
    cur = conn.cursor()
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    return rows


def get_db():
    if "db" not in g:
        g.db = connect()
    return g.db


def query_one(sql, params=()):
    rows = run(get_db(), sql, params)
    return rows[0] if rows else None


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create the table and seed 5 demo users with random details (first run only)."""
    conn = connect()
    run(conn, CREATE_MYSQL if USE_MYSQL else CREATE_SQLITE)
    count = run(conn, "SELECT COUNT(*) AS n FROM users")[0]
    if count["n"] == 0:
        for i in range(1, 6):
            first, last = random.choice(FIRST), random.choice(LAST)
            income = random.randint(20, 200) * 1000
            run(
                conn,
                """INSERT INTO users (username, password_hash, full_name, email, phone, city,
                   occupation, balance, savings, monthly_income, monthly_expenses, debt)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    f"user{i}",
                    generate_password_hash(f"pass{i}"),
                    f"{first} {last}",
                    f"{first.lower()}.{last.lower()}@example.com",
                    f"+91 9{random.randint(100000000, 999999999)}",
                    random.choice(CITIES),
                    random.choice(JOBS),
                    random.randint(1000, 500000),
                    random.randint(0, 2000000),
                    income,
                    random.randint(int(income * 0.3), int(income * 0.9)),
                    random.choice([0, 0, random.randint(10000, 800000)]),
                ),
            )
    conn.commit()
    conn.close()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)
    return wrapped


@app.template_filter("money")
def money(value):
    return f"₹{value:,.2f}" if value is not None else "—"


@app.route("/")
def index():
    return redirect(url_for("dashboard" if "user_id" in session else "login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = query_one("SELECT * FROM users WHERE username = ?", (username,))
        if user and check_password_hash(user["password_hash"], password):
            session.clear()
            session["user_id"] = user["id"]
            return redirect(url_for("dashboard"))
        flash("Wrong username or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    user = query_one("SELECT * FROM users WHERE id = ?", (session["user_id"],))
    if user is None:
        session.clear()
        return redirect(url_for("login"))
    net_worth = (user["balance"] or 0) + (user["savings"] or 0) - (user["debt"] or 0)
    left_over = (user["monthly_income"] or 0) - (user["monthly_expenses"] or 0)
    return render_template("dashboard.html", user=user, net_worth=net_worth, left_over=left_over)


@app.route("/edit", methods=["GET", "POST"])
@login_required
def edit():
    db = get_db()
    if request.method == "POST":
        values = {}
        for col, label, _ in EDITABLE_FIELDS:
            raw = request.form.get(col, "").strip()
            if col in MONEY_FIELDS:
                try:
                    values[col] = float(raw or 0)
                except ValueError:
                    flash(f"{label} must be a number.", "error")
                    return redirect(url_for("edit"))
            else:
                values[col] = raw
        sets = ", ".join(f"{c} = ?" for c in values)  # column names come from the fixed list above
        run(db, f"UPDATE users SET {sets} WHERE id = ?", (*values.values(), session["user_id"]))
        db.commit()
        flash("Details saved.", "ok")
        return redirect(url_for("dashboard"))
    user = query_one("SELECT * FROM users WHERE id = ?", (session["user_id"],))
    return render_template("edit.html", user=user, fields=EDITABLE_FIELDS)


init_db()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1", port=5050)
