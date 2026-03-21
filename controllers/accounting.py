from flask import (Blueprint, render_template, request,
                   session, redirect, url_for, flash)
from database import get_db, close_db
from utils.decorators import login_required, roles_required
from datetime import date

accounting_bp = Blueprint("accounting", __name__)


@accounting_bp.route("/accounting", methods=["GET", "POST"])
@login_required
@roles_required("super_admin", "school_admin", "accounts_officer")
def index():
    school_id = session.get("school_id")
    conn = get_db()
    cur  = conn.cursor()

    schools = []
    if session.get("role") == "super_admin":
        cur.execute(
            "SELECT id, name FROM schools WHERE is_active = 1 ORDER BY name")
        schools = cur.fetchall()

    if request.method == "POST":
        record_type = request.form.get("type")
        category    = request.form.get("category", "").strip()
        amount      = request.form.get("amount", 0)
        description = request.form.get("description", "").strip()
        rec_date    = request.form.get("date", str(date.today()))
        user_id     = session.get("user_id")

        if session.get("role") == "super_admin":
            sid = request.form.get("school_id") or school_id
        else:
            sid = school_id

        cur.execute("""
            INSERT INTO accounting
            (school_id, type, category, amount,
             description, date, recorded_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (sid, record_type, category, amount,
              description, rec_date, user_id))
        conn.commit()
        flash(f"{record_type} recorded successfully!", "success")

    if session.get("role") == "super_admin":
        cur.execute("""
            SELECT a.*, sc.name AS school_name
            FROM accounting a
            JOIN schools sc ON sc.id = a.school_id
            ORDER BY a.date DESC LIMIT 50
        """)
    else:
        cur.execute("""
            SELECT * FROM accounting
            WHERE school_id = ?
            ORDER BY date DESC LIMIT 50
        """, (school_id,))
    records = cur.fetchall()

    if session.get("role") == "super_admin":
        cur.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN type = 'Income'
                    THEN amount ELSE 0 END), 0) AS income,
                COALESCE(SUM(CASE WHEN type = 'Expense'
                    THEN amount ELSE 0 END), 0) AS expense
            FROM accounting
        """)
    else:
        cur.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN type = 'Income'
                    THEN amount ELSE 0 END), 0) AS income,
                COALESCE(SUM(CASE WHEN type = 'Expense'
                    THEN amount ELSE 0 END), 0) AS expense
            FROM accounting WHERE school_id = ?
        """, (school_id,))
    summary = cur.fetchone()

    close_db(conn)
    return render_template("accounting/index.html",
                           records=records,
                           summary=summary,
                           schools=schools,
                           today=str(date.today()))
