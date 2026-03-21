from flask import (Blueprint, render_template, request,
                   session, redirect, url_for, flash)
from database import get_db, close_db
from werkzeug.security import check_password_hash, generate_password_hash

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard.index"))

    if request.method == "POST":
        email    = request.form.get("email", "").strip()
        password = request.form.get("password", "").strip()

        if not email or not password:
            flash("Email and password are required.", "danger")
            return render_template("auth/login.html")

        conn = get_db()
        cur  = conn.cursor()
        cur.execute(
            "SELECT * FROM users WHERE email = ? AND is_active = 1",
            (email,))
        user = cur.fetchone()
        close_db(conn)

        if user and check_password_hash(user["password"], password):
            session["user_id"]   = user["id"]
            session["user_name"] = user["name"]
            session["role"]      = user["role"]
            session["school_id"] = user["school_id"]
            flash(f"Welcome back, {user['name']}!", "success")
            return redirect(url_for("dashboard.index"))
        else:
            flash("Invalid email or password.", "danger")

    return render_template("auth/login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/change-password", methods=["GET", "POST"])
def change_password():
    if not session.get("user_id"):
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        current  = request.form.get("current_password", "").strip()
        new_pass = request.form.get("new_password", "").strip()
        confirm  = request.form.get("confirm_password", "").strip()

        if not current or not new_pass or not confirm:
            flash("All fields are required.", "danger")
            return render_template("auth/change_password.html")

        if new_pass != confirm:
            flash("New passwords do not match.", "danger")
            return render_template("auth/change_password.html")

        if len(new_pass) < 6:
            flash("Password must be at least 6 characters.", "danger")
            return render_template("auth/change_password.html")

        conn = get_db()
        cur  = conn.cursor()
        cur.execute(
            "SELECT * FROM users WHERE id = ?",
            (session["user_id"],))
        user = cur.fetchone()

        if not user or not check_password_hash(user["password"], current):
            flash("Current password is incorrect.", "danger")
            close_db(conn)
            return render_template("auth/change_password.html")

        hashed = generate_password_hash(new_pass)
        cur.execute(
            "UPDATE users SET password = ? WHERE id = ?",
            (hashed, session["user_id"]))
        conn.commit()
        close_db(conn)
        flash("Password changed successfully!", "success")
        return redirect(url_for("dashboard.index"))

    return render_template("auth/change_password.html")
