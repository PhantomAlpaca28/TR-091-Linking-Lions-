import sqlite3
import os

DATABASE_FILE = os.path.join(
    os.path.dirname(__file__),
    "tech_debt.db"
)


def init_db():

    conn = sqlite3.connect(DATABASE_FILE)

    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_score INTEGER
    )
    """)

    conn.commit()
    conn.close()


def save_scan(score):

    conn = sqlite3.connect(DATABASE_FILE)

    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO scans (project_score) VALUES (?)",
        (score,)
    )

    conn.commit()
    conn.close()