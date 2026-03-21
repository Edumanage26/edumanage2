from flask import (Blueprint, render_template, request,
                   session, redirect, url_for, flash)
from database import get_db, close_db
from utils.decorators import login_required, roles_required
from datetime import date

fee_bp = Blueprint("fee", __name__)


@fee_bp.route("/fees")
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

    if session.get("role") == "super_admin":
        cur.execute(
            "SELECT COALESCE(SUM(amount_paid), 0) AS total FROM fee_payments")
    else:
        cur.execute(
            "SELECT COALESCE(SUM(amount_paid), 0) AS total FROM fee_payments WHERE school_id = ?",
            (school_id,))
    fee_total = cur.fetchone()

    if session.get("role") == "super_admin":
        cur.execute("""
            SELECT fp.*, s.first_name, s.last_name,
                   c.name AS class_name
            FROM fee_payments fp
            JOIN students s ON s.id = fp.student_id
            JOIN classes c ON c.id = s.class_id
            ORDER BY fp.created_at DESC LIMIT 10
        """)
    else:
        cur.execute("""
            SELECT fp.*, s.first_name, s.last_name,
                   c.name AS class_name
            FROM fee_payments fp
            JOIN students s ON s.id = fp.student_id
            JOIN classes c ON c.id = s.class_id
            WHERE fp.school_id = ?
            ORDER BY fp.created_at DESC LIMIT 10
        """, (school_id,))
    recent_payments = cur.fetchall()

    close_db(conn)
    return render_template("fees/index.html",
                           classes=classes,
                           fee_total=fee_total,
                           recent_payments=recent_payments)


@fee_bp.route("/fees/structure", methods=["GET", "POST"])
@login_required
@roles_required("super_admin", "school_admin", "accounts_officer")
def structure():
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

    if request.method == "POST":
        class_id    = request.form.get("class_id")
        term        = request.form.get("term")
        session_yr  = request.form.get("session", "2024/2025")
        amount      = request.form.get("amount", 0)
        description = request.form.get("description", "")

        cur.execute(
            "SELECT id FROM fee_structure WHERE class_id = ? AND term = ? AND session = ?",
            (class_id, term, session_yr))
        existing = cur.fetchone()

        if existing:
            cur.execute(
                "UPDATE fee_structure SET amount = ?, description = ? WHERE class_id = ? AND term = ? AND session = ?",
                (amount, description, class_id, term, session_yr))
        else:
            cur.execute("""
                INSERT INTO fee_structure
                (school_id, class_id, term, session, amount, description)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (school_id, class_id, term, session_yr,
                  amount, description))
        conn.commit()
        flash("Fee structure saved!", "success")

    cur.execute("""
        SELECT fs.*, c.name AS class_name
        FROM fee_structure fs
        JOIN classes c ON c.id = fs.class_id
        ORDER BY c.name, fs.term
    """)
    structures = cur.fetchall()
    close_db(conn)

    terms    = ["First Term", "Second Term", "Third Term"]
    sessions = ["2024/2025", "2025/2026", "2026/2027"]
    return render_template("fees/structure.html",
                           classes=classes,
                           structures=structures,
                           terms=terms,
                           sessions=sessions)


@fee_bp.route("/fees/pay", methods=["GET", "POST"])
@login_required
@roles_required("super_admin", "school_admin", "accounts_officer")
def pay():
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

    students = []
    if request.args.get("class_id"):
        cur.execute("""
            SELECT * FROM students
            WHERE class_id = ? AND is_active = 1
            ORDER BY first_name
        """, (request.args.get("class_id"),))
        students = cur.fetchall()

    if request.method == "POST":
        student_id     = request.form.get("student_id")
        amount_paid    = request.form.get("amount_paid", 0)
        payment_method = request.form.get("payment_method", "Cash")
        receipt_no     = request.form.get("receipt_no", "")
        payment_date   = request.form.get(
            "payment_date", str(date.today()))
        user_id = session.get("user_id")

        cur.execute(
            "SELECT school_id FROM students WHERE id = ?",
            (student_id,))
        stu = cur.fetchone()
        pay_school_id = stu["school_id"] if stu else school_id

        cur.execute("""
            INSERT INTO fee_payments
            (school_id, student_id, amount_paid,
             payment_method, receipt_no, payment_date, recorded_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (pay_school_id, student_id, amount_paid,
              payment_method, receipt_no, payment_date, user_id))
        conn.commit()
        flash("Payment recorded successfully!", "success")
        close_db(conn)
        return redirect(url_for("fee.report"))

    close_db(conn)
    return render_template("fees/pay.html",
                           classes=classes,
                           students=students)


@fee_bp.route("/fees/report")
@login_required
@roles_required("super_admin", "school_admin", "accounts_officer")
def report():
    school_id  = session.get("school_id")
    class_id   = request.args.get("class_id", "")
    term       = request.args.get("term", "First Term")
    session_yr = request.args.get("session", "2024/2025")

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
    fee_amount  = 0

    if class_id:
        cur.execute(
            "SELECT amount FROM fee_structure WHERE class_id = ? AND term = ? AND session = ?",
            (class_id, term, session_yr))
        fs = cur.fetchone()
        fee_amount = fs["amount"] if fs else 0

        cur.execute("""
            SELECT s.*,
                   COALESCE(SUM(fp.amount_paid), 0) AS amount_paid
            FROM students s
            LEFT JOIN fee_payments fp ON fp.student_id = s.id
            WHERE s.class_id = ? AND s.is_active = 1
            GROUP BY s.id
            ORDER BY s.first_name
        """, (class_id,))
        report_data = cur.fetchall()

    close_db(conn)

    terms    = ["First Term", "Second Term", "Third Term"]
    sessions = ["2024/2025", "2025/2026", "2026/2027"]
    return render_template("fees/report.html",
                           classes=classes,
                           report_data=report_data,
                           fee_amount=fee_amount,
                           selected_class=class_id,
                           term=term,
                           session_yr=session_yr,
                           terms=terms,
                           sessions=sessions)

