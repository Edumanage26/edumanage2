from flask import (Blueprint, render_template, request,
                   session, redirect, url_for, flash)
from database import get_db, close_db
from utils.decorators import login_required, roles_required

class_bp = Blueprint("class_view", __name__)


@class_bp.route("/classes")
@login_required
def list_classes():
    school_id = session.get("school_id")
    conn = get_db()
    cur  = conn.cursor()

    if session.get("role") == "super_admin":
        cur.execute("""
            SELECT c.id, c.name, c.school_id, c.description,
                   c.created_at, sc.name AS school_name,
                   COUNT(DISTINCT s.id) AS student_count
            FROM classes c
            LEFT JOIN schools sc ON sc.id = c.school_id
            LEFT JOIN students s ON s.class_id = c.id
                AND s.is_active = 1
            GROUP BY c.id, c.name, c.school_id, c.description,
                     c.created_at, sc.name
            ORDER BY sc.name, c.name
        """)
    else:
        cur.execute("""
            SELECT c.id, c.name, c.school_id, c.description,
                   c.created_at,
                   COUNT(DISTINCT s.id) AS student_count
            FROM classes c
            LEFT JOIN students s ON s.class_id = c.id
                AND s.is_active = 1
            WHERE c.school_id = ?
            GROUP BY c.id, c.name, c.school_id, c.description,
                     c.created_at
            ORDER BY c.name
        """, (school_id,))
    classes = cur.fetchall()

    schools = []
    if session.get("role") == "super_admin":
        cur.execute(
            "SELECT id, name FROM schools WHERE is_active = 1 ORDER BY name")
        schools = cur.fetchall()

    close_db(conn)
    return render_template("classes/list.html",
                           classes=classes, schools=schools)


@class_bp.route("/classes/add", methods=["POST"])
@login_required
@roles_required("super_admin", "school_admin")
def add_class():
    school_id = session.get("school_id")
    name      = request.form.get("name", "").strip()

    if not name:
        flash("Class name is required.", "danger")
        return redirect(url_for("class_view.list_classes"))

    conn = get_db()
    cur  = conn.cursor()

    if session.get("role") == "super_admin":
        sid = request.form.get("school_id") or school_id
        if not sid:
            cur.execute(
                "SELECT id FROM schools WHERE is_active = 1 LIMIT 1")
            first = cur.fetchone()
            sid   = first["id"] if first else None
    else:
        sid = school_id

    if not sid:
        flash("No school found. Please register a school first.", "danger")
        close_db(conn)
        return redirect(url_for("class_view.list_classes"))

    cur.execute(
        "SELECT id FROM classes WHERE name = ? AND school_id = ?",
        (name, sid))
    if cur.fetchone():
        flash(f"Class {name} already exists.", "warning")
        close_db(conn)
        return redirect(url_for("class_view.list_classes"))

    cur.execute(
        "INSERT INTO classes (school_id, name) VALUES (?, ?)",
        (sid, name))
    conn.commit()
    close_db(conn)
    flash(f"Class {name} added successfully!", "success")
    return redirect(url_for("class_view.list_classes"))


@class_bp.route("/classes/edit/<int:class_id>", methods=["GET", "POST"])
@login_required
@roles_required("super_admin", "school_admin")
def edit_class(class_id):
    school_id = session.get("school_id")
    conn = get_db()
    cur  = conn.cursor()

    if session.get("role") == "super_admin":
        cur.execute(
            "SELECT * FROM classes WHERE id = ?", (class_id,))
    else:
        cur.execute(
            "SELECT * FROM classes WHERE id = ? AND school_id = ?",
            (class_id, school_id))
    cls = cur.fetchone()

    if not cls:
        flash("Class not found.", "danger")
        close_db(conn)
        return redirect(url_for("class_view.list_classes"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Class name is required.", "danger")
            close_db(conn)
            return redirect(url_for("class_view.list_classes"))
        cur.execute(
            "UPDATE classes SET name = ? WHERE id = ?",
            (name, class_id))
        conn.commit()
        close_db(conn)
        flash("Class updated successfully!", "success")
        return redirect(url_for("class_view.list_classes"))

    close_db(conn)
    return render_template("classes/edit.html", cls=cls)


@class_bp.route("/classes/delete/<int:class_id>")
@login_required
@roles_required("super_admin", "school_admin")
def delete_class(class_id):
    conn = get_db()
    cur  = conn.cursor()

    cur.execute(
        "SELECT COUNT(*) AS cnt FROM students WHERE class_id = ? AND is_active = 1",
        (class_id,))
    count = cur.fetchone()["cnt"]

    if count > 0:
        flash(f"Cannot delete — {count} student(s) are in this class.", "warning")
        close_db(conn)
        return redirect(url_for("class_view.list_classes"))

    cur.execute("DELETE FROM classes WHERE id = ?", (class_id,))
    conn.commit()
    close_db(conn)
    flash("Class deleted successfully.", "success")
    return redirect(url_for("class_view.list_classes"))


@class_bp.route("/classes/view/<int:class_id>")
@login_required
def view_class(class_id):
    conn = get_db()
    cur  = conn.cursor()

    cur.execute("SELECT * FROM classes WHERE id = ?", (class_id,))
    cls = cur.fetchone()

    if not cls:
        flash("Class not found.", "danger")
        close_db(conn)
        return redirect(url_for("class_view.list_classes"))

    cur.execute("""
        SELECT s.*, c.name AS class_name
        FROM students s
        LEFT JOIN classes c ON c.id = s.class_id
        WHERE s.class_id = ? AND s.is_active = 1
        ORDER BY s.first_name
    """, (class_id,))
    students = cur.fetchall()
    close_db(conn)
    return render_template("classes/view.html",
                           cls=cls, students=students)
