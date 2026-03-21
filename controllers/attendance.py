from flask import (Blueprint, render_template, request,
                   session, redirect, url_for, flash)
from database import get_db, close_db
from utils.decorators import login_required, roles_required
from datetime import date

attendance_bp = Blueprint("attendance", __name__)


@attendance_bp.route("/attendance")
@login_required
def index():
    school_id = session.get("school_id")
    conn = get_db()
    cur  = conn.cursor()

    if session.get("role") == "super_admin":
        cur.execute("""
            SELECT c.*, sc.name AS school_name
            FROM classes c
            JOIN schools sc ON sc.id = c.school_id
            ORDER BY sc.name, c.name
        """)
    else:
        cur.execute(
            "SELECT * FROM classes WHERE school_id = ? ORDER BY name",
            (school_id,))
    classes = cur.fetchall()

    today = str(date.today())
    if session.get("role") == "super_admin":
        cur.execute("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) AS present,
                SUM(CASE WHEN status = 'Absent'  THEN 1 ELSE 0 END) AS absent
            FROM attendance WHERE date = ?
        """, (today,))
    else:
        cur.execute("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) AS present,
                SUM(CASE WHEN status = 'Absent'  THEN 1 ELSE 0 END) AS absent
            FROM attendance WHERE school_id = ? AND date = ?
        """, (school_id, today))
    summary = cur.fetchone()

    if session.get("role") == "super_admin":
        cur.execute("""
            SELECT a.*, s.first_name, s.last_name,
                   c.name AS class_name
            FROM attendance a
            JOIN students s ON s.id = a.student_id
            JOIN classes c ON c.id = a.class_id
            ORDER BY a.date DESC LIMIT 20
        """)
    else:
        cur.execute("""
            SELECT a.*, s.first_name, s.last_name,
                   c.name AS class_name
            FROM attendance a
            JOIN students s ON s.id = a.student_id
            JOIN classes c ON c.id = a.class_id
            WHERE a.school_id = ?
            ORDER BY a.date DESC LIMIT 20
        """, (school_id,))
    records = cur.fetchall()

    close_db(conn)
    return render_template("attendance/index.html",
                           classes=classes,
                           summary=summary,
                           records=records,
                           today=today)


@attendance_bp.route("/attendance/mark", methods=["GET", "POST"])
@login_required
def mark():
    school_id = session.get("school_id")
    conn = get_db()
    cur  = conn.cursor()

    if session.get("role") == "super_admin":
        cur.execute("""
            SELECT c.*, sc.name AS school_name
            FROM classes c
            JOIN schools sc ON sc.id = c.school_id
            ORDER BY sc.name, c.name
        """)
    else:
        cur.execute(
            "SELECT * FROM classes WHERE school_id = ? ORDER BY name",
            (school_id,))
    classes = cur.fetchall()

    students       = []
    selected_class = None
    selected_date  = str(date.today())
    existing       = {}

    if request.method == "POST" and "load_students" in request.form:
        class_id      = request.form.get("class_id")
        selected_date = request.form.get("date", str(date.today()))

        cur.execute(
            "SELECT * FROM classes WHERE id = ?", (class_id,))
        selected_class = cur.fetchone()

        cur.execute("""
            SELECT id, first_name, last_name,
                   admission_no, photo, photo_url
            FROM students
            WHERE class_id = ? AND is_active = 1
            ORDER BY first_name
        """, (class_id,))
        students = cur.fetchall()

        cur.execute("""
            SELECT student_id, status FROM attendance
            WHERE class_id = ? AND date = ?
        """, (class_id, selected_date))
        for row in cur.fetchall():
            existing[row["student_id"]] = row["status"]

    elif request.method == "POST" and "save_attendance" in request.form:
        class_id      = request.form.get("class_id")
        selected_date = request.form.get("date", str(date.today()))
        user_id       = session.get("user_id")

        cur.execute(
            "SELECT school_id FROM classes WHERE id = ?", (class_id,))
        cls = cur.fetchone()

        if cls:
            att_school_id = cls["school_id"]

            cur.execute("""
                SELECT id FROM students
                WHERE class_id = ? AND is_active = 1
            """, (class_id,))
            all_students = cur.fetchall()

            saved = 0
            for s in all_students:
                sid    = s["id"]
                status = request.form.get(f"status_{sid}", "Absent")

                cur.execute("""
                    SELECT id FROM attendance
                    WHERE student_id = ? AND date = ?
                """, (sid, selected_date))
                existing_rec = cur.fetchone()

                if existing_rec:
                    cur.execute("""
                        UPDATE attendance SET status = ?
                        WHERE student_id = ? AND date = ?
                    """, (status, sid, selected_date))
                else:
                    cur.execute("""
                        INSERT INTO attendance
                        (school_id, class_id, student_id, date, status)
                        VALUES (?, ?, ?, ?, ?)
                    """, (att_school_id, class_id, sid,
                          selected_date, status))
                saved += 1

            conn.commit()
            flash(f"Attendance saved for {saved} student(s)!", "success")
            close_db(conn)
            return redirect(url_for("attendance.index"))

    close_db(conn)
    return render_template("attendance/mark.html",
                           classes=classes,
                           students=students,
                           selected_class=selected_class,
                           selected_date=selected_date,
                           existing=existing)


@attendance_bp.route("/attendance/report")
@login_required
def report():
    school_id  = session.get("school_id")
    class_id   = request.args.get("class_id", "")
    start_date = request.args.get("start_date", "")
    end_date   = request.args.get("end_date", "")

    conn = get_db()
    cur  = conn.cursor()

    if session.get("role") == "super_admin":
        cur.execute("""
            SELECT c.*, sc.name AS school_name
            FROM classes c
            JOIN schools sc ON sc.id = c.school_id
            ORDER BY sc.name, c.name
        """)
    else:
        cur.execute(
            "SELECT * FROM classes WHERE school_id = ? ORDER BY name",
            (school_id,))
    classes = cur.fetchall()

    report_data = []

    if class_id and start_date and end_date:
        cur.execute("""
            SELECT
                s.id, s.first_name, s.last_name, s.admission_no,
                COUNT(a.id) AS total_days,
                SUM(CASE WHEN a.status = 'Present' THEN 1 ELSE 0 END) AS present,
                SUM(CASE WHEN a.status = 'Absent'  THEN 1 ELSE 0 END) AS absent
            FROM students s
            LEFT JOIN attendance a ON a.student_id = s.id
                AND a.date BETWEEN ? AND ?
            WHERE s.class_id = ? AND s.is_active = 1
            GROUP BY s.id, s.first_name, s.last_name, s.admission_no
            ORDER BY s.first_name
        """, (start_date, end_date, class_id))
        report_data = cur.fetchall()

    close_db(conn)
    return render_template("attendance/report.html",
                           classes=classes,
                           report_data=report_data,
                           selected_class=class_id,
                           start_date=start_date,
                           end_date=end_date)

