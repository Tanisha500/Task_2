"""SQLite persistence and assignment seed import."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from dataset import PATIENTS
from medlineplus import create_remarks
from validation import validate_patient

DB_PATH = Path(__file__).with_name("health_records.sqlite3")


@contextmanager
def connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def initialize():
    with connect() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            date_of_birth TEXT NOT NULL,
            email TEXT NOT NULL,
            glucose TEXT NOT NULL,
            haemoglobin TEXT NOT NULL,
            cholesterol TEXT NOT NULL,
            remarks TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT 'user',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS app_state (
            key TEXT PRIMARY KEY, value TEXT NOT NULL
        )""")
        exists = conn.execute("SELECT 1 FROM app_state WHERE key='dataset_imported'").fetchone()
        if not exists:
            for source_record in PATIENTS:
                cleaned, errors = validate_patient(source_record, assignment_date_format=True)
                if not errors:
                    remarks = create_remarks(cleaned["glucose"], cleaned["haemoglobin"], cleaned["cholesterol"])
                    insert_record(conn, cleaned, remarks, source="assignment")
            conn.execute("INSERT INTO app_state(key,value) VALUES('dataset_imported','yes')")


def insert_record(conn, patient, remarks, source="user"):
    conn.execute("""INSERT INTO patients
        (full_name,date_of_birth,email,glucose,haemoglobin,cholesterol,remarks,source)
        VALUES(?,?,?,?,?,?,?,?)""",
        (patient["full_name"], patient["date_of_birth"], patient["email"],
         patient["glucose"], patient["haemoglobin"], patient["cholesterol"], remarks, source))


def all_patients():
    with connect() as conn:
        return [dict(row) for row in conn.execute("SELECT * FROM patients ORDER BY id")]


def get_patient(patient_id):
    with connect() as conn:
        row = conn.execute("SELECT * FROM patients WHERE id=?", (patient_id,)).fetchone()
        return dict(row) if row else None


def save_patient(patient, remarks, patient_id=None):
    with connect() as conn:
        if patient_id is None:
            insert_record(conn, patient, remarks)
        else:
            conn.execute("""UPDATE patients SET full_name=?,date_of_birth=?,email=?,glucose=?,
                haemoglobin=?,cholesterol=?,remarks=? WHERE id=?""",
                (patient["full_name"], patient["date_of_birth"], patient["email"],
                 patient["glucose"], patient["haemoglobin"], patient["cholesterol"], remarks, patient_id))


def delete_patient(patient_id):
    with connect() as conn:
        conn.execute("DELETE FROM patients WHERE id=?", (patient_id,))


def rejected_assignment_rows():
    rejected = []
    for row in PATIENTS:
        _, errors = validate_patient(row, assignment_date_format=True)
        if errors:
            rejected.append({**row, "reasons": list(errors.values())})
    return rejected
