import os
import sqlite3
import urllib.parse as urlparse
from flask import g

try:
    import psycopg2
    import psycopg2.extras
    PSYCOPG2_AVAILABLE = True
except ImportError:
    PSYCOPG2_AVAILABLE = False

DB_PATH = "school.db"


def is_postgres():
    url = os.environ.get("DATABASE_URL", "")
    return bool(url) and "postgres" in url


class SmartCursor:
    def __init__(self, cursor, pg=False):
        self._cur = cursor
        self._pg  = pg

    def execute(self, query, params=None):
        if self._pg:
            query = query.replace("?", "%s")
        if params is not None:
            self._cur.execute(query, params)
        else:
            self._cur.execute(query)

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def __getattr__(self, name):
        return getattr(self._cur, name)


class SmartConnection:
    def __init__(self, conn, pg=False):
        self._conn = conn
        self._pg   = pg

    def cursor(self):
        return SmartCursor(self._conn.cursor(), self._pg)

    def commit(self):
        self._conn.commit()

    def rollback(self):
        try:
            self._conn.rollback()
        except Exception:
            pass

    def close(self):
        self._conn.close()

    def execute(self, query, params=None):
        cur = self.cursor()
        cur.execute(query, params)
        return cur

    def __getattr__(self, name):
        return getattr(self._conn, name)


def get_db():
    if "db" not in g:
        if is_postgres() and PSYCOPG2_AVAILABLE:
            try:
                url = os.environ.get("DATABASE_URL", "")
                if url.startswith("postgres://"):
                    url = url.replace("postgres://", "postgresql://", 1)

                result = urlparse.urlparse(url)
                host     = result.hostname
                port     = result.port or 5432
                database = result.path[1:]
                user     = result.username
                password = result.password

                print(f"Connecting to PostgreSQL: {host}:{port}/{database}")

                raw = psycopg2.connect(
                    host=host,
                    port=port,
                    database=database,
                    user=user,
                    password=password,
                    cursor_factory=psycopg2.extras.RealDictCursor,
                    sslmode="require",
                    connect_timeout=30
                )
                raw.autocommit = False
                g.db = SmartConnection(raw, pg=True)
                print("PostgreSQL connected!")

            except Exception as e:
                print(f"PostgreSQL connection failed: {e}")
                print("Falling back to SQLite...")
                raw = sqlite3.connect(
                    DB_PATH, timeout=30, check_same_thread=False
                )
                raw.row_factory = sqlite3.Row
                raw.execute("PRAGMA journal_mode=WAL")
                raw.execute("PRAGMA synchronous=NORMAL")
                g.db = SmartConnection(raw, pg=False)
        else:
            raw = sqlite3.connect(
                DB_PATH, timeout=30, check_same_thread=False
            )
            raw.row_factory = sqlite3.Row
            raw.execute("PRAGMA journal_mode=WAL")
            raw.execute("PRAGMA synchronous=NORMAL")
            g.db = SmartConnection(raw, pg=False)
    return g.db


def close_db(conn=None):
    db = g.pop("db", None)
    if db is not None:
        try:
            db.close()
        except Exception:
            pass


def init_db():
    conn = get_db()
    cur  = conn.cursor()

    if is_postgres():
        tables = [
            """CREATE TABLE IF NOT EXISTS schools (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                address TEXT, phone TEXT, email TEXT,
                logo TEXT, logo_url TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                school_id INTEGER,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                role TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS classes (
                id SERIAL PRIMARY KEY,
                school_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS students (
                id SERIAL PRIMARY KEY,
                school_id INTEGER NOT NULL,
                class_id INTEGER,
                first_name TEXT NOT NULL,
                last_name TEXT NOT NULL,
                admission_no TEXT,
                gender TEXT,
                date_of_birth TEXT,
                parent_phone TEXT,
                parent_email TEXT,
                address TEXT,
                photo TEXT,
                photo_url TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS subjects (
                id SERIAL PRIMARY KEY,
                school_id INTEGER NOT NULL,
                class_id INTEGER NOT NULL,
                name TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS attendance (
                id SERIAL PRIMARY KEY,
                school_id INTEGER NOT NULL,
                class_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                date TEXT NOT NULL,
                status TEXT NOT NULL
            )""",
            """CREATE TABLE IF NOT EXISTS results (
                id SERIAL PRIMARY KEY,
                school_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                subject_id INTEGER NOT NULL,
                class_id INTEGER NOT NULL,
                term TEXT, session TEXT,
                ca1 REAL DEFAULT 0,
                exam REAL DEFAULT 0,
                score REAL DEFAULT 0,
                grade TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS fee_structure (
                id SERIAL PRIMARY KEY,
                school_id INTEGER NOT NULL,
                class_id INTEGER NOT NULL,
                term TEXT, session TEXT,
                amount REAL DEFAULT 0,
                description TEXT
            )""",
            """CREATE TABLE IF NOT EXISTS fee_payments (
                id SERIAL PRIMARY KEY,
                school_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                fee_structure_id INTEGER,
                amount_paid REAL NOT NULL,
                payment_method TEXT,
                receipt_no TEXT,
                payment_date TEXT,
                recorded_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TABLE IF NOT EXISTS accounting (
                id SERIAL PRIMARY KEY,
                school_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                category TEXT NOT NULL,
                amount REAL NOT NULL,
                description TEXT,
                date TEXT,
                recorded_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
        ]
        for table in tables:
            try:
                cur.execute(table)
                conn.commit()
            except Exception as e:
                print(f"Table error: {e}")
                conn.rollback()
    else:
        cur._cur.executescript("""
            CREATE TABLE IF NOT EXISTS schools (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL, address TEXT, phone TEXT,
                email TEXT, logo TEXT, logo_url TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                school_id INTEGER, name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL, password TEXT NOT NULL,
                role TEXT NOT NULL, is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS classes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                school_id INTEGER NOT NULL, name TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                school_id INTEGER NOT NULL, class_id INTEGER,
                first_name TEXT NOT NULL, last_name TEXT NOT NULL,
                admission_no TEXT, gender TEXT, date_of_birth TEXT,
                parent_phone TEXT, parent_email TEXT, address TEXT,
                photo TEXT, photo_url TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                school_id INTEGER NOT NULL,
                class_id INTEGER NOT NULL, name TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                school_id INTEGER NOT NULL,
                class_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                date TEXT NOT NULL, status TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                school_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                subject_id INTEGER NOT NULL,
                class_id INTEGER NOT NULL,
                term TEXT, session TEXT,
                ca1 REAL DEFAULT 0, exam REAL DEFAULT 0,
                score REAL DEFAULT 0, grade TEXT
            );
            CREATE TABLE IF NOT EXISTS fee_structure (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                school_id INTEGER NOT NULL,
                class_id INTEGER NOT NULL,
                term TEXT, session TEXT,
                amount REAL DEFAULT 0, description TEXT
            );
            CREATE TABLE IF NOT EXISTS fee_payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                school_id INTEGER NOT NULL,
                student_id INTEGER NOT NULL,
                fee_structure_id INTEGER,
                amount_paid REAL NOT NULL,
                payment_method TEXT, receipt_no TEXT,
                payment_date TEXT, recorded_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS accounting (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                school_id INTEGER NOT NULL,
                type TEXT NOT NULL, category TEXT NOT NULL,
                amount REAL NOT NULL, description TEXT,
                date TEXT, recorded_by INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()

    # Count existing records
    try:
        cur.execute("SELECT COUNT(*) AS cnt FROM users")
        users = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) AS cnt FROM schools")
        schools = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) AS cnt FROM students")
        students = cur.fetchone()["cnt"]
        print(f"Database ready! Users:{users} Schools:{schools} Students:{students}")
    except Exception as e:
        print(f"Database ready! Count error: {e}")
