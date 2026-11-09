import os
import random
import sqlite3
from functools import wraps

from flask import Flask, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "users.db")

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


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create the table and seed 5 demo users with random details (first run only)."""
    db = sqlite3.connect(DB_PATH)
    db.execute(
        """CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            full_name TEXT, email TEXT, phone TEXT, city TEXT, occupation TEXT,
            balance REAL, savings REAL, monthly_income REAL, monthly_expenses REAL, debt REAL
        )"""
    )
    if db.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        for i in range(1, 6):
            first, last = random.choice(FIRST), random.choice(LAST)
            income = random.randint(20, 200) * 1000
            db.execute(
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
    db.commit()
    db.close()


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
        user = get_db().execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
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
    user = get_db().execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
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
        db.execute(f"UPDATE users SET {sets} WHERE id = ?", (*values.values(), session["user_id"]))
        db.commit()
        flash("Details saved.", "ok")
        return redirect(url_for("dashboard"))
    user = db.execute("SELECT * FROM users WHERE id = ?", (session["user_id"],)).fetchone()
    return render_template("edit.html", user=user, fields=EDITABLE_FIELDS)


init_db()

if __name__ == "__main__":
    app.run(debug=os.environ.get("FLASK_DEBUG") == "1", port=5050)
