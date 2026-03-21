from flask import (Blueprint, render_template, request,
                   session, redirect, url_for, flash)
from database import get_db, close_db
from utils.decorators import login_required, roles_required
from utils.helpers import save_photo

student_bp = Blueprint("student", __name__)


@student_bp.route("/students")
@login_required
def list_students():
    school_id    = session.get("school_id")
    search       = request.args.get("search", "").strip()
    class_filter = request.args.get("class_id", "")
    conn = get_db()
    cur  = conn.cursor()

    if session.get("role") == "super_admin":
        cur.execute(
            "SELECT c.id, c.name, c.school_id FROM classes c ORDER BY c.name")
    else:
        cur.execute(
            "SELECT id, name, school_id FROM classes WHERE school_id = ? ORDER BY name",
            (school_id,))
    classes = cur.fetchall()

    if session.get("role") == "super_admin":
        query  = """SELECT s.*, c.name AS class_name
            FROM students s
            LEFT JOIN classes c ON c.id = s.class_id
            WHERE s.is_active = 1"""
        params = []
    else:
        query  = """SELECT s.*, c.name AS class_name
            FROM students s
            LEFT JOIN classes c ON c.id = s.class_id
            WHERE s.school_id = ? AND s.is_active = 1"""
        params = [school_id]

    if search:
        query += " AND (s.first_name LIKE ? OR s.last_name LIKE ? OR s.admission_no LIKE ?)"
        params += [f"%{search}%", f"%{search}%", f"%{search}%"]
    if class_filter:
        query += " AND s.class_id = ?"
        params.append(class_filter)
    query += " ORDER BY s.first_name"
    cur.execute(query, params)
    students = cur.fetchall()
    close_db(conn)
    return render_template("students/list.html",
                           students=students,
                           classes=classes,
                           search=search,
                           selected_class=class_filter)


@student_bp.route("/students/add", methods=["GET", "POST"])
@login_required
@roles_required("super_admin", "school_admin")
def add_student():
    school_id = session.get("school_id")
    conn = get_db()
    cur  = conn.cursor()

    if session.get("role") == "super_admin":
        cur.execute(
            "SELECT id, name, school_id FROM classes ORDER BY name")
        classes = cur.fetchall()
        cur.execute(
            "SELECT id, name FROM schools WHERE is_active = 1 ORDER BY name")
        schools = cur.fetchall()
    else:
        cur.execute(
            "SELECT id, name, school_id FROM classes WHERE school_id = ? ORDER BY name",
            (school_id,))
        classes = cur.fetchall()
        schools = []

    if request.method == "POST":
        first_name   = request.form.get("first_name", "").strip()
        last_name    = request.form.get("last_name", "").strip()
        admission_no = request.form.get("admission_no", "").strip()
        gender       = request.form.get("gender", "").strip()
        dob          = request.form.get("date_of_birth", "").strip()
        parent_phone = request.form.get("parent_phone", "").strip()
        parent_email = request.form.get("parent_email", "").strip()
        address      = request.form.get("address", "").strip()
        class_id     = request.form.get("class_id") or None

        if session.get("role") == "super_admin":
            sid = request.form.get("school_id") or school_id
        else:
            sid = school_id

        if not first_name or not last_name:
            flash("First name and last name are required.", "danger")
            close_db(conn)
            return render_template("students/add.html",
                                   classes=classes, schools=schools)

        photo     = None
        photo_url = None
        file = request.files.get("photo")
        if file and file.filename:
            try:
                photo, photo_url = save_photo(file)
            except Exception as e:
                print(f"Photo error: {e}")

        cur.execute("""
            INSERT INTO students
            (school_id, class_id, first_name, last_name,
             admission_no, gender, date_of_birth,
             parent_phone, parent_email, address,
             photo, photo_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (sid, class_id, first_name, last_name,
              admission_no, gender, dob,
              parent_phone, parent_email, address,
              photo, photo_url))
        conn.commit()
        close_db(conn)
        flash(f"Student {first_name} {last_name} added!", "success")
        return redirect(url_for("student.list_students"))

    close_db(conn)
    return render_template("students/add.html",
                           classes=classes, schools=schools)


@student_bp.route("/students/edit/<int:student_id>", methods=["GET", "POST"])
@login_required
@roles_required("super_admin", "school_admin")
def edit_student(student_id):
    school_id = session.get("school_id")
    conn = get_db()
    cur  = conn.cursor()

    cur.execute(
        "SELECT * FROM students WHERE id = ?", (student_id,))
    student = cur.fetchone()

    if not student:
        flash("Student not found.", "danger")
        close_db(conn)
        return redirect(url_for("student.list_students"))

    sid = student["school_id"] if student["school_id"] else school_id
    cur.execute(
        "SELECT id, name FROM classes WHERE school_id = ? ORDER BY name",
        (sid,))
    classes = cur.fetchall()

    if request.method == "POST":
        first_name   = request.form.get("first_name", "").strip()
        last_name    = request.form.get("last_name", "").strip()
        class_id     = request.form.get("class_id") or None
        gender       = request.form.get("gender", "").strip()
        admission_no = request.form.get("admission_no", "").strip()
        parent_phone = request.form.get("parent_phone", "").strip()
        parent_email = request.form.get("parent_email", "").strip()
        dob          = request.form.get("date_of_birth", "").strip()
        address      = request.form.get("address", "").strip()
        photo        = student["photo"]
        photo_url    = student["photo_url"] if "photo_url" in student.keys() else None

        file = request.files.get("photo")
        if file and file.filename:
            try:
                saved_name, saved_url = save_photo(file)
                if saved_name:
                    photo     = saved_name
                    photo_url = saved_url
            except Exception as e:
                print(f"Photo error: {e}")

        cur.execute("""
            UPDATE students
            SET first_name=?, last_name=?, class_id=?,
                gender=?, admission_no=?, parent_phone=?,
                parent_email=?, date_of_birth=?, address=?,
                photo=?, photo_url=?
            WHERE id=?
        """, (first_name, last_name, class_id,
              gender, admission_no, parent_phone,
              parent_email, dob, address,
              photo, photo_url, student_id))
        conn.commit()
        close_db(conn)
        flash("Student updated successfully!", "success")
        return redirect(url_for("student.list_students"))

    close_db(conn)
    return render_template("students/edit.html",
                           student=student, classes=classes)


@student_bp.route("/students/view/<int:student_id>")
@login_required
def view_student(student_id):
    conn = get_db()
    cur  = conn.cursor()

    cur.execute("""
        SELECT s.*, c.name AS class_name
        FROM students s
        LEFT JOIN classes c ON c.id = s.class_id
        WHERE s.id = ?
    """, (student_id,))
    student = cur.fetchone()

    if not student:
        flash("Student not found.", "danger")
        close_db(conn)
        return redirect(url_for("student.list_students"))

    cur.execute("""
        SELECT date, status FROM attendance
        WHERE student_id = ?
        ORDER BY date DESC LIMIT 30
    """, (student_id,))
    attendance = cur.fetchall()

    cur.execute("""
        SELECT r.*, sub.name AS subject_name
        FROM results r
        JOIN subjects sub ON sub.id = r.subject_id
        WHERE r.student_id = ?
        ORDER BY r.session DESC, r.term, sub.name
    """, (student_id,))
    results = cur.fetchall()

    close_db(conn)
    return render_template("students/view.html",
                           student=student,
                           attendance=attendance,
                           results=results)


@student_bp.route("/students/delete/<int:student_id>")
@login_required
@roles_required("super_admin", "school_admin")
def delete_student(student_id):
    conn = get_db()
    cur  = conn.cursor()
    cur.execute(
        "UPDATE students SET is_active = 0 WHERE id = ?",
        (student_id,))
    conn.commit()
    close_db(conn)
    flash("Student removed successfully!", "success")
    return redirect(url_for("student.list_students"))


