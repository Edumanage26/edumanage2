import os
from flask import Flask, render_template, redirect, url_for
from dotenv import load_dotenv

load_dotenv()


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get(
        "SECRET_KEY", "dev-secret-key-123")
    app.config["UPLOAD_FOLDER"] = os.path.join("static", "uploads")
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    from controllers.auth       import auth_bp
    from controllers.dashboard  import dashboard_bp
    from controllers.student    import student_bp
    from controllers.school     import school_bp
    from controllers.class_ctrl import class_bp
    from controllers.attendance import attendance_bp
    from controllers.result     import result_bp
    from controllers.fee        import fee_bp
    from controllers.accounting import accounting_bp
    from controllers.export     import export_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(student_bp)
    app.register_blueprint(school_bp)
    app.register_blueprint(class_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(result_bp)
    app.register_blueprint(fee_bp)
    app.register_blueprint(accounting_bp)
    app.register_blueprint(export_bp)

    from database import close_db
    app.teardown_appcontext(close_db)

    @app.route("/")
    def index():
        return redirect(url_for("auth.login"))

    @app.route("/pricing")
    def pricing():
        return render_template("pricing.html")

    @app.errorhandler(404)
    def not_found(e):
        return render_template("404.html"), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("403.html"), 403

    with app.app_context():
        try:
            from database import init_db, get_db, close_db
            from werkzeug.security import generate_password_hash

            init_db()

            conn = get_db()
            cur  = conn.cursor()

            cur.execute(
                "SELECT id FROM users WHERE email = ?",
                ("admin@schoolplatform.com",))
            existing = cur.fetchone()

            if not existing:
                hashed = generate_password_hash("Admin@1234")
                cur.execute(
                    "INSERT INTO users (name, email, password, role) VALUES (?, ?, ?, ?)",
                    ("Super Admin", "admin@schoolplatform.com",
                     hashed, "super_admin"))
                conn.commit()
                print("Super admin created!")
            else:
                print("Super admin exists!")

            close_db(conn)
            print("App ready!")

        except Exception as e:
            print(f"Startup error: {e}")

    return app


application = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"EduManage Pro starting on http://0.0.0.0:{port}")
    application.run(debug=True, port=port, host="0.0.0.0")

