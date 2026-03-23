from flask import (Blueprint, render_template, session)
from database import get_db, close_db
from utils.decorators import login_required
from datetime import date

dashboard_bp = Blueprint("dashboard", __name__)


def fix_row(row):
    if not row:
        return None
    r = dict(row)
    for key, val in r.items():
        if hasattr(val, 'strftime'):
            r[key] = str(val)[:10]
    return r


def fix_rows(rows):
    return [fix_row(r) for r in rows]


@dashboard_bp.route("/dashboard")
@login_required
def index():
    school_id = session.get("school_id")
    role      = session.get("role")
    conn = get_db()
    cur  = conn.cursor()

    school = None
    if school_id:
        cur.execute(
            "SELECT * FROM schools WHERE id = ?", (school_id,))
        school = fix_row(cur.fetchone())

    if role == "super_admin":
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM students WHERE is_active = 1")
    else:
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM students WHERE school_id = ? AND is_active = 1",
            (school_id,))
    total_students = cur.fetchone()["cnt"]

    if role == "super_admin":
        cur.execute("SELECT COUNT(*) AS cnt FROM classes")
    else:
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM classes WHERE school_id = ?",
            (school_id,))
    total_classes = cur.fetchone()["cnt"]

    today = str(date.today())
    if role == "super_admin":
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM attendance WHERE date = ? AND status = 'Present'",
            (today,))
    else:
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM attendance WHERE school_id = ? AND date = ? AND status = 'Present'",
            (school_id, today))
    present_today = cur.fetchone()["cnt"]

    if role == "super_admin":
        cur.execute(
            "SELECT COALESCE(SUM(amount_paid), 0) AS total FROM fee_payments")
    else:
        cur.execute(
            "SELECT COALESCE(SUM(amount_paid), 0) AS total FROM fee_payments WHERE school_id = ?",
            (school_id,))
    fees_total = cur.fetchone()["total"]

    if role == "super_admin":
        cur.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN type = 'Income' THEN amount ELSE 0 END), 0) AS income,
                COALESCE(SUM(CASE WHEN type = 'Expense' THEN amount ELSE 0 END), 0) AS expense
            FROM accounting
        """)
    else:
        cur.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN type = 'Income' THEN amount ELSE 0 END), 0) AS income,
                COALESCE(SUM(CASE WHEN type = 'Expense' THEN amount ELSE 0 END), 0) AS expense
            FROM accounting WHERE school_id = ?
        """, (school_id,))
    acc_summary = cur.fetchone()

    if role == "super_admin":
        cur.execute("""
            SELECT date,
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) AS present
            FROM attendance
            GROUP BY date ORDER BY date DESC LIMIT 7
        """)
    else:
        cur.execute("""
            SELECT date,
                COUNT(*) AS total,
                SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) AS present
            FROM attendance WHERE school_id = ?
            GROUP BY date ORDER BY date DESC LIMIT 7
        """, (school_id,))
    chart_data = fix_rows(cur.fetchall())

    if role == "super_admin":
        cur.execute("""
            SELECT s.id, s.first_name, s.last_name,
                   s.gender, s.photo, s.photo_url,
                   s.created_at,
                   c.name AS class_name,
                   sc.name AS school_name
            FROM students s
            LEFT JOIN classes c ON c.id = s.class_id
            LEFT JOIN schools sc ON sc.id = s.school_id
            WHERE s.is_active = 1
            ORDER BY s.created_at DESC LIMIT 5
        """)
    else:
        cur.execute("""
            SELECT s.id, s.first_name, s.last_name,
                   s.gender, s.photo, s.photo_url,
                   s.created_at,
                   c.name AS class_name
            FROM students s
            LEFT JOIN classes c ON c.id = s.class_id
            WHERE s.school_id = ? AND s.is_active = 1
            ORDER BY s.created_at DESC LIMIT 5
        """, (school_id,))
    recent_students = fix_rows(cur.fetchall())

    schools = []
    if role == "super_admin":
        cur.execute("""
            SELECT sc.id, sc.name, sc.logo, sc.logo_url,
                   sc.address, sc.is_active, sc.created_at,
                   COUNT(DISTINCT s.id) AS student_count
            FROM schools sc
            LEFT JOIN students s ON s.school_id = sc.id
                AND s.is_active = 1
            GROUP BY sc.id, sc.name, sc.logo, sc.logo_url,
                     sc.address, sc.is_active, sc.created_at
            ORDER BY sc.created_at DESC LIMIT 5
        """)
        schools = fix_rows(cur.fetchall())

    close_db(conn)
    return render_template("dashboard/index.html",
                           school=school,
                           total_students=total_students,
                           total_classes=total_classes,
                           present_today=present_today,
                           fees_total=fees_total,
                           acc_summary=acc_summary,
                           chart_data=chart_data,
                           recent_students=recent_students,
                           schools=schools,
                           today=today)
