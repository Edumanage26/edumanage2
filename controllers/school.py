from flask import (Blueprint, render_template, request,
                   session, redirect, url_for, flash)
from database import get_db, close_db
from utils.decorators import login_required, roles_required
from utils.helpers import save_logo
from werkzeug.security import generate_password_hash

school_bp = Blueprint("school", __name__)


@school_bp.route("/schools")
@login_required
@roles_required("super_admin")
def list_schools():
    conn = get_db()
    cur  = conn.cursor()
    cur.execute("""
        SELECT sc.*,
            COUNT(DISTINCT s.id) AS student_count,
            COUNT(DISTINCT u.id) AS staff_count
        FROM schools sc
        LEFT JOIN students s ON s.school_id = sc.id AND s.is_active = 1
        LEFT JOIN users u ON u.school_id = sc.id AND u.is_active = 1
        GROUP BY sc.id
        ORDER BY sc.created_at DESC
    """)
    schools = cur.fetchall()
    close_db(conn)
    return render_template("schools/list.html", schools=schools)


@school_bp.route("/schools/add", methods=["GET", "POST"])
@login_required
@roles_required("super_admin")
def add_school():
    if request.method == "POST":
        name    = request.form.get("name", "").strip()
        address = request.form.get("address", "").strip()
        phone   = request.form.get("phone", "").strip()
        email   = request.form.get("email", "").strip()

        if not name:
            flash("School name is required.", "danger")
            return render_template("schools/add.html")

        logo     = None
        logo_url = None
        file = request.files.get("logo")
        if file and file.filename:
            try:
                logo, logo_url = save_logo(file)
            except Exception as e:
                print(f"Logo error: {e}")

        conn = get_db()
        cur  = conn.cursor()
        cur.execute("""
            INSERT INTO schools
            (name, address, phone, email, logo, logo_url)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, address, phone, email, logo, logo_url))
        conn.commit()
        close_db(conn)
        flash(f"School {name} added successfully!", "success")
        return redirect(url_for("school.list_schools"))

    return render_template("schools/add.html")


@school_bp.route("/schools/edit/<int:school_id>", methods=["GET", "POST"])
@login_required
@roles_required("super_admin")
def edit_school(school_id):
    conn = get_db()
    cur  = conn.cursor()

    cur.execute("SELECT * FROM schools WHERE id = ?", (school_id,))
    school = cur.fetchone()

    if not school:
        flash("School not found.", "danger")
        close_db(conn)
        return redirect(url_for("school.list_schools"))

    if request.method == "POST":
        name    = request.form.get("name", "").strip()
        address = request.form.get("address", "").strip()
        phone   = request.form.get("phone", "").strip()
        email   = request.form.get("email", "").strip()

        logo     = school["logo"]
        logo_url = school["logo_url"] if "logo_url" in school.keys() else None
        file = request.files.get("logo")
        if file and file.filename:
            try:
                saved_name, saved_url = save_logo(file)
                if saved_name:
                    logo     = saved_name
                    logo_url = saved_url
            except Exception as e:
                print(f"Logo error: {e}")

        cur.execute("""
            UPDATE schools
            SET name=?, address=?, phone=?, email=?,
                logo=?, logo_url=?
            WHERE id=?
        """, (name, address, phone, email,
              logo, logo_url, school_id))
        conn.commit()
        close_db(conn)
        flash("School updated successfully!", "success")
        return redirect(url_for("school.list_schools"))

    close_db(conn)
    return render_template("schools/edit.html", school=school)


@school_bp.route("/schools/toggle/<int:school_id>")
@login_required
@roles_required("super_admin")
def toggle_school(school_id):
    conn = get_db()
    cur  = conn.cursor()
    cur.execute(
        "SELECT is_active FROM schools WHERE id = ?", (school_id,))
    school = cur.fetchone()
    if school:
        new_status = 0 if school["is_active"] else 1
        cur.execute(
            "UPDATE schools SET is_active = ? WHERE id = ?",
            (new_status, school_id))
        conn.commit()
        status = "activated" if new_status else "deactivated"
        flash(f"School {status} successfully!", "success")
    close_db(conn)
    return redirect(url_for("school.list_schools"))


@school_bp.route("/schools/view/<int:school_id>")
@login_required
@roles_required("super_admin")
def view_school(school_id):
    conn = get_db()
    cur  = conn.cursor()

    cur.execute("SELECT * FROM schools WHERE id = ?", (school_id,))
    school = cur.fetchone()

    if not school:
        flash("School not found.", "danger")
        close_db(conn)
        return redirect(url_for("school.list_schools"))

    cur.execute("""
        SELECT id, name, email, role, is_active
        FROM users
        WHERE school_id = ? AND role != 'super_admin'
        ORDER BY name
    """, (school_id,))
    staff_list = cur.fetchall()
    close_db(conn)
    return render_template("schools/view.html",
                           school=school,
                           staff_list=staff_list)


@school_bp.route("/schools/<int:school_id>/add-staff",
                 methods=["GET", "POST"])
@login_required
@roles_required("super_admin")
def add_staff(school_id):
    conn = get_db()
    cur  = conn.cursor()

    cur.execute("SELECT * FROM schools WHERE id = ?", (school_id,))
    school = cur.fetchone()

    if not school:
        flash("School not found.", "danger")
        close_db(conn)
        return redirect(url_for("school.list_schools"))

    if request.method == "POST":
        name  = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        role  = request.form.get("role", "teacher")

        if not name or not email:
            flash("Name and email are required.", "danger")
            close_db(conn)
            return render_template("schools/add_staff.html",
                                   school=school)

        cur.execute(
            "SELECT id FROM users WHERE email = ?", (email,))
        if cur.fetchone():
            flash("Email already exists.", "warning")
            close_db(conn)
            return render_template("schools/add_staff.html",
                                   school=school)

        hashed = generate_password_hash("Admin@1234")
        cur.execute("""
            INSERT INTO users
            (school_id, name, email, password, role)
            VALUES (?, ?, ?, ?, ?)
        """, (school_id, name, email, hashed, role))
        conn.commit()
        close_db(conn)
        flash(f"Staff {name} added! Default password: Admin@1234", "success")
        return redirect(url_for("school.view_school",
                                school_id=school_id))

    close_db(conn)
    return render_template("schools/add_staff.html", school=school)


@school_bp.route("/schools/delete-staff/<int:user_id>")
@login_required
@roles_required("super_admin")
def delete_staff(user_id):
    conn = get_db()
    cur  = conn.cursor()

    cur.execute(
        "SELECT school_id, name, role FROM users WHERE id = ?",
        (user_id,))
    user = cur.fetchone()

    if not user:
        flash("Staff not found.", "danger")
        close_db(conn)
        return redirect(url_for("school.list_schools"))

    school_id = user["school_id"]

    cur.execute(
        "SELECT COUNT(*) AS cnt FROM users WHERE school_id = ? AND role = 'school_admin'",
        (school_id,))
    admin_count = cur.fetchone()["cnt"]

    if user["role"] == "school_admin" and admin_count <= 1:
        flash("Cannot delete the only school admin.", "danger")
        close_db(conn)
        return redirect(url_for("school.view_school",
                                school_id=school_id))

    cur.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    close_db(conn)
    flash(f"Staff {user['name']} removed successfully!", "success")
    return redirect(url_for("school.view_school",
                            school_id=school_id))

