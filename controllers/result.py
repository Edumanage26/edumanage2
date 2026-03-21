from flask import (Blueprint, render_template, request,
                   session, redirect, url_for, flash)
from database import get_db, close_db
from utils.decorators import login_required, roles_required

result_bp = Blueprint("result", __name__)


def calculate_grade(score):
    if score >= 80: return "A"
    elif score >= 70: return "B"
    elif score >= 60: return "C"
    elif score >= 50: return "D"
    elif score >= 40: return "E"
    else: return "F"


@result_bp.route("/results")
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
    close_db(conn)

    terms    = ["First Term", "Second Term", "Third Term"]
    sessions = ["2024/2025", "2025/2026", "2026/2027"]
    return render_template("results/index.html",
                           classes=classes,
                           terms=terms,
                           sessions=sessions)


@result_bp.route("/results/subjects/<int:class_id>",
                 methods=["GET", "POST"])
@login_required
def subjects(class_id):
    school_id = session.get("school_id")
    conn = get_db()
    cur  = conn.cursor()

    cur.execute("SELECT * FROM classes WHERE id = ?", (class_id,))
    cls = cur.fetchone()

    if not cls:
        flash("Class not found.", "danger")
        close_db(conn)
        return redirect(url_for("result.index"))

    if request.method == "POST":
        action = request.form.get("action")
        if action == "add":
            name = request.form.get("name", "").strip()
            if name:
                sid = cls["school_id"] if cls else school_id
                cur.execute(
                    "SELECT id FROM subjects WHERE class_id = ? AND name = ?",
                    (class_id, name))
                if not cur.fetchone():
                    cur.execute(
                        "INSERT INTO subjects (school_id, class_id, name) VALUES (?, ?, ?)",
                        (sid, class_id, name))
                    conn.commit()
                    flash(f"Subject {name} added!", "success")
                else:
                    flash("Subject already exists.", "warning")
            else:
                flash("Subject name is required.", "danger")
        elif action == "delete":
            sub_id = request.form.get("subject_id")
            cur.execute("DELETE FROM subjects WHERE id = ?", (sub_id,))
            conn.commit()
            flash("Subject deleted.", "success")

    cur.execute(
        "SELECT * FROM subjects WHERE class_id = ? ORDER BY name",
        (class_id,))
    subjects_list = cur.fetchall()
    close_db(conn)
    return render_template("results/subjects.html",
                           cls=cls,
                           subjects=subjects_list)


@result_bp.route("/results/enter/<int:class_id>",
                 methods=["GET", "POST"])
@login_required
def enter(class_id):
    term       = request.args.get("term", "First Term")
    session_yr = request.args.get("session", "2024/2025")
    school_id  = session.get("school_id")

    conn = get_db()
    cur  = conn.cursor()

    cur.execute("""
        SELECT c.*, sc.name AS school_name,
               sc.logo AS school_logo,
               sc.logo_url AS school_logo_url,
               sc.address AS school_address,
               sc.phone AS school_phone,
               sc.email AS school_email
        FROM classes c
        JOIN schools sc ON sc.id = c.school_id
        WHERE c.id = ?
    """, (class_id,))
    cls = cur.fetchone()

    if not cls:
        flash("Class not found.", "danger")
        close_db(conn)
        return redirect(url_for("result.index"))

    cur.execute(
        "SELECT * FROM subjects WHERE class_id = ? ORDER BY name",
        (class_id,))
    subjects_list = cur.fetchall()

    cur.execute("""
        SELECT * FROM students
        WHERE class_id = ? AND is_active = 1
        ORDER BY first_name, last_name
    """, (class_id,))
    students = cur.fetchall()

    print(f"Class ID: {class_id}")
    print(f"Students found: {len(students)}")
    print(f"Subjects found: {len(subjects_list)}")

    if request.method == "POST":
        saved = 0
        for student in students:
            for subject in subjects_list:
                ca1_key  = f"ca1_{student['id']}_{subject['id']}"
                exam_key = f"exam_{student['id']}_{subject['id']}"
                ca1  = float(request.form.get(ca1_key, 0) or 0)
                exam = float(request.form.get(exam_key, 0) or 0)
                ca1  = min(ca1, 40)
                exam = min(exam, 60)
                total = ca1 + exam
                grade = calculate_grade(total)
                sid   = cls["school_id"] if cls else school_id

                cur.execute("""
                    SELECT id FROM results
                    WHERE student_id = ? AND subject_id = ?
                    AND term = ? AND session = ?
                """, (student["id"], subject["id"], term, session_yr))
                existing = cur.fetchone()

                if existing:
                    cur.execute("""
                        UPDATE results
                        SET ca1=?, exam=?, score=?, grade=?
                        WHERE student_id=? AND subject_id=?
                        AND term=? AND session=?
                    """, (ca1, exam, total, grade,
                          student["id"], subject["id"],
                          term, session_yr))
                else:
                    cur.execute("""
                        INSERT INTO results
                        (school_id, student_id, subject_id, class_id,
                         term, session, ca1, exam, score, grade)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (sid, student["id"], subject["id"],
                          class_id, term, session_yr,
                          ca1, exam, total, grade))
                saved += 1

        conn.commit()
        flash(f"Results saved for {len(students)} students!", "success")
        close_db(conn)
        return redirect(url_for("result.enter",
                                class_id=class_id,
                                term=term,
                                session=session_yr))

    results = {}
    for student in students:
        for subject in subjects_list:
            cur.execute("""
                SELECT ca1, exam, score, grade FROM results
                WHERE student_id = ? AND subject_id = ?
                AND term = ? AND session = ?
            """, (student["id"], subject["id"], term, session_yr))
            row = cur.fetchone()
            if row:
                results[(student["id"], subject["id"])] = row

    close_db(conn)

    terms    = ["First Term", "Second Term", "Third Term"]
    sessions = ["2024/2025", "2025/2026", "2026/2027"]
    return render_template("results/enter.html",
                           cls=cls,
                           subjects=subjects_list,
                           students=students,
                           results=results,
                           term=term,
                           session_yr=session_yr,
                           terms=terms,
                           sessions=sessions)


@result_bp.route("/results/reportcard/<int:class_id>")
@login_required
def reportcard(class_id):
    term             = request.args.get("term", "First Term")
    session_yr       = request.args.get("session", "2024/2025")
    selected_student = request.args.get("student_id", "")
    school_id        = session.get("school_id")

    conn = get_db()
    cur  = conn.cursor()

    cur.execute("""
        SELECT c.*, sc.name AS school_name,
               sc.logo AS school_logo,
               sc.logo_url AS school_logo_url,
               sc.address AS school_address,
               sc.phone AS school_phone,
               sc.email AS school_email
        FROM classes c
        JOIN schools sc ON sc.id = c.school_id
        WHERE c.id = ?
    """, (class_id,))
    cls = cur.fetchone()

    if not cls:
        flash("Class not found.", "danger")
        close_db(conn)
        return redirect(url_for("result.index"))

    cur.execute(
        "SELECT * FROM subjects WHERE class_id = ? ORDER BY name",
        (class_id,))
    subjects_list = cur.fetchall()

    cur.execute("""
        SELECT * FROM students
        WHERE class_id = ? AND is_active = 1
        ORDER BY first_name
    """, (class_id,))
    all_students = cur.fetchall()

    cur.execute(
        "SELECT COUNT(*) AS cnt FROM students WHERE class_id = ? AND is_active = 1",
        (class_id,))
    total_students = cur.fetchone()["cnt"]

    if selected_student:
        students = [s for s in all_students
                    if str(s["id"]) == selected_student]
    else:
        students = all_students

    all_totals = []
    for s in all_students:
        total_score = 0
        count = 0
        for sub in subjects_list:
            cur.execute("""
                SELECT score FROM results
                WHERE student_id = ? AND subject_id = ?
                AND term = ? AND session = ?
            """, (s["id"], sub["id"], term, session_yr))
            row = cur.fetchone()
            if row and row["score"] is not None:
                total_score += row["score"]
                count += 1
        all_totals.append({"id": s["id"], "total": total_score})

    sorted_totals = sorted(
        all_totals, key=lambda x: x["total"], reverse=True)
    positions = {item["id"]: i+1
                 for i, item in enumerate(sorted_totals)}

    report_data = []
    for s in students:
        subj_rows   = []
        total_score = 0
        count       = 0

        for sub in subjects_list:
            cur.execute("""
                SELECT ca1, exam, score, grade FROM results
                WHERE student_id = ? AND subject_id = ?
                AND term = ? AND session = ?
            """, (s["id"], sub["id"], term, session_yr))
            row = cur.fetchone()
            if row and row["score"] is not None:
                total_score += row["score"]
                count += 1
                subj_rows.append({
                    "subject": sub["name"],
                    "ca1":    row["ca1"]   or 0,
                    "exam":   row["exam"]  or 0,
                    "total":  row["score"] or 0,
                    "grade":  row["grade"] or "---",
                    "status": "Pass" if row["score"] >= 40 else "Fail"
                })
            else:
                subj_rows.append({
                    "subject": sub["name"],
                    "ca1": 0, "exam": 0,
                    "total": 0, "grade": "---", "status": "---"
                })

        average    = round(total_score / count, 1) if count else 0
        percentage = round(
            (total_score / (count * 100)) * 100, 1) if count else 0

        cur.execute("""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) AS present,
                   SUM(CASE WHEN status = 'Absent'  THEN 1 ELSE 0 END) AS absent
            FROM attendance
            WHERE student_id = ? AND class_id = ?
        """, (s["id"], class_id))
        att = cur.fetchone()

        if average >= 80:
            auto_comment      = "Excellent performance! Keep up the outstanding work."
            principal_comment = "Outstanding result. We are very proud of you!"
        elif average >= 70:
            auto_comment      = "Very good performance. Continue to put in great effort."
            principal_comment = "Very impressive. Keep working hard!"
        elif average >= 60:
            auto_comment      = "Good performance. There is room for improvement."
            principal_comment = "Good work. We encourage you to do even better."
        elif average >= 50:
            auto_comment      = "Average performance. More effort is needed."
            principal_comment = "Fair result. You can do better with more effort."
        elif average >= 40:
            auto_comment      = "Below average. Needs to work harder."
            principal_comment = "More seriousness is required. Please put in more effort."
        else:
            auto_comment      = "Poor performance. Urgent attention required."
            principal_comment = "This result is not acceptable. Serious improvement needed."

        report_data.append({
            "student":           s,
            "subjects":          subj_rows,
            "total_score":       round(total_score, 1),
            "average":           average,
            "percentage":        percentage,
            "auto_comment":      auto_comment,
            "principal_comment": principal_comment,
            "att_total":         att["total"]   or 0 if att else 0,
            "att_present":       att["present"] or 0 if att else 0,
            "att_absent":        att["absent"]  or 0 if att else 0,
        })

    close_db(conn)

    terms    = ["First Term", "Second Term", "Third Term"]
    sessions = ["2024/2025", "2025/2026", "2026/2027"]
    return render_template("results/reportcard.html",
                           cls=cls,
                           report_data=report_data,
                           positions=positions,
                           total_students=total_students,
                           students=all_students,
                           selected_student=selected_student,
                           term=term,
                           session_yr=session_yr,
                           terms=terms,
                           sessions=sessions)
